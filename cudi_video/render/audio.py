"""Gemeinsamer Mixer: selbst erzeugte Hintergrundmusik, Ducking unter der Stimme, Akzent-Sound bei Enthüllungen.

Alles wird lokal synthetisiert (story/music.py) – keine Downloads, keine Lizenzfragen. Abschaltbar: CUDI_MUSIK=0.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

SR = 48_000
MUSIC_BELOW_SPEECH_DB = -12.0     # Musik unter dem Sprech-Pegel, solange niemand spricht
DUCK_GAIN = 0.3                   # beim Sprechen zusätzlich auf 30 % (ca. -10 dB)

KIND_STYLE = {"ranking": "pulse", "numbers": "pulse", "facts": "pluck", "erklaer": "pad"}
FORMAT_STYLE = {"manuskript": "pad", "polaroid": "warm", "magazin": "pad"}
TOPIC_STYLE = (
    ("warm", ("tier", "animal", "natur", "nature", "ocean", "meer", "fluss", "river", "wald", "forest", "baby", "liebe")),
    ("pluck", ("sport", "spiel", "game", "essen", "food", "candy", "fun", "film", "musik")),
    ("drone", ("krieg", "war", "crime", "verbrech", "unfall", "disaster", "katastroph", "tief", "deep")),
)


def enabled() -> bool:
    return os.environ.get("CUDI_MUSIK", "1").strip().lower() not in ("0", "aus", "off", "false", "nein")


def music_style(kind: str, fmt: str = "", topic: str = "") -> str | None:
    """Stimmung je Videoart, Format und Thema (None = ohne Musik)."""
    if not enabled():
        return None
    style = KIND_STYLE.get(kind, "pad")
    if fmt in FORMAT_STYLE:
        style = FORMAT_STYLE[fmt]
    low = topic.lower()
    for name, words in TOPIC_STYLE:
        if any(w in low for w in words):
            return name
    return style


def moving_average(x: np.ndarray, width: int) -> np.ndarray:
    """Gleitender Mittelwert in linearer Zeit (wie np.convolve(..., mode="same") / width).

    Über kumulierte Summen statt width-facher Rechenarbeit je Sample (3 Minuten bei 48 kHz)."""
    n = len(x)
    half = (width - 1) // 2
    sums = np.concatenate(([0.0], np.cumsum(x, dtype=np.float64)))
    idx = np.arange(n)
    hi = np.minimum(idx + half + 1, n)
    lo = np.maximum(idx - (width - 1 - half), 0)
    return ((sums[hi] - sums[lo]) / width).astype(np.float32)


def duck_curve(voice: np.ndarray, rate: int = SR) -> np.ndarray:
    """Verstärkung der Musik: 1.0 in Sprechpausen, DUCK_GAIN beim Sprechen, weich (ca. 0,25 s) übergeblendet."""
    env = moving_average(np.abs(voice), max(2, int(0.1 * rate)))
    gate = np.where(env > 0.008, DUCK_GAIN, 1.0).astype(np.float32)
    return moving_average(gate, max(2, int(0.25 * rate)))


def accent(rate: int = SR) -> np.ndarray:
    """Leiser Akzent-Ton („Plopp“ mit hellem Glöckchen) für Platz-/Zahl-Enthüllungen."""
    from ..story.music import _hz
    t = np.arange(int(0.7 * rate)) / rate
    bell = 0.7 * np.sin(2 * np.pi * _hz(84) * t) * np.exp(-t / 0.18) + 0.3 * np.sin(2 * np.pi * _hz(91) * t) * np.exp(-t / 0.12)
    thump = np.sin(2 * np.pi * (70 + 90 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.09)
    out = (0.6 * bell + 0.8 * thump).astype(np.float32)
    n = int(0.004 * rate)
    out[:n] *= np.linspace(0, 1, n)
    return out / (np.abs(out).max() + 1e-9)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def generate_music(style: str, seconds: float, work: Path, seed_key: str, decode) -> np.ndarray | None:
    from ..story.music import STYLES, make_music
    if style not in STYLES:
        return None
    seed = int(hashlib.sha1(seed_key.encode()).hexdigest()[:6], 16)
    path = make_music(style, seconds, work / "music_gen.wav", seed=seed)
    track = decode(str(path))
    return track if len(track) else None


def mix_music(voice: np.ndarray, music: np.ndarray | None) -> np.ndarray:
    """Musik auf festen Abstand zur Sprech-Lautstärke bringen und unter der Stimme absenken."""
    if music is None or len(music) == 0:
        return np.zeros_like(voice)
    if len(music) < len(voice):
        music = np.tile(music, int(np.ceil(len(voice) / len(music))))
    music = music[:len(voice)]
    speech = rms(voice[np.abs(voice) > 0.01]) or 0.1
    gain = speech * 10 ** (MUSIC_BELOW_SPEECH_DB / 20) / (rms(music) or 1.0)
    return (music * gain * duck_curve(voice)).astype(np.float32)


def place_accents(track: np.ndarray, times: list[float], level: float, rate: int = SR) -> None:
    snd = accent(rate) * level
    for t in times:
        s = int(t * rate)
        if 0 <= s < len(track):
            track[s:s + len(snd)] += snd[: len(track) - s]
