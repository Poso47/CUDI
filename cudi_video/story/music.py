"""Stimmungsmusik, komplett selbst erzeugt (keine Lizenzfragen, keine Downloads).

Bewusst schlicht und leise – sie liegt unter der Stimme und wird beim Sprechen weiter abgesenkt.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44_100


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def _lowpass(signal: np.ndarray, cutoff: float) -> np.ndarray:
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(len(signal), 1 / SR)
    spectrum *= 1 / (1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spectrum, len(signal))


def _highpass(signal: np.ndarray, cutoff: float) -> np.ndarray:
    return signal - _lowpass(signal, cutoff)


def _note(freq: float, seconds: float, decay: float, harmonics=(1.0, 0.5, 0.25), attack: float = 0.005) -> np.ndarray:
    t = _t(seconds)
    tone = sum(a * np.sin(2 * np.pi * freq * (k + 1) * t) for k, a in enumerate(harmonics))
    env = np.minimum(1, t / attack) * np.exp(-t / decay)
    return tone * env


def _place(track: np.ndarray, sound: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    if i >= len(track):
        return
    n = min(len(sound), len(track) - i)
    track[i:i + n] += sound[:n] * gain


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def drone(seconds: float, rnd: np.random.Generator) -> np.ndarray:
    """Grusel: tiefes, schwebendes Dröhnen, Wind und ein gelegentlicher dumpfer Herzschlag."""
    t = _t(seconds)
    base = (0.5 * np.sin(2 * np.pi * 55 * t) + 0.4 * np.sin(2 * np.pi * 55.6 * t)
            + 0.22 * np.sin(2 * np.pi * 82.4 * t + 0.7)) * (0.65 + 0.35 * np.sin(2 * np.pi * 0.05 * t))
    wind = _lowpass(rnd.standard_normal(len(t)), 500) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t + 1)) * 0.35
    eerie = 0.035 * np.sin(2 * np.pi * 1318.5 * t + 4 * np.sin(2 * np.pi * 0.27 * t)) * np.clip(np.sin(2 * np.pi * 0.031 * t), 0, 1)
    track = base + wind + eerie
    beat = _note(48, 0.45, 0.12, (1.0, 0.3))
    at = 4.0
    while at < seconds:
        _place(track, beat, at, 0.9)
        _place(track, beat, at + 0.32, 0.6)          # „bum-bum“
        at += rnd.uniform(7, 11)
    return track


def pulse(seconds: float, rnd: np.random.Generator) -> np.ndarray:
    """Spannung: pulsierender Bass in Achteln, langsam anschwellend."""
    track = np.zeros(len(_t(seconds)))
    step = 60 / 100 / 2
    roots = [45, 45, 41, 43]                          # A – A – F – G
    i, at = 0, 0.0
    while at < seconds:
        root = roots[(i // 16) % len(roots)]
        _place(track, _note(_hz(root), step * 0.95, 0.18, (1.0, 0.6, 0.4, 0.25)), at, 0.8 if i % 4 == 0 else 0.55)
        if i % 8 == 4:
            _place(track, _highpass(rnd.standard_normal(int(0.05 * SR)), 6000) * np.exp(-_t(0.05) / 0.01), at, 0.25)
        at += step
        i += 1
    swell = 0.6 + 0.4 * np.clip(_t(seconds) / max(seconds, 1), 0, 1)
    return _lowpass(track, 1800) * swell


def pluck(seconds: float, rnd: np.random.Generator) -> np.ndarray:
    """Lustig: verspielte, gezupfte Töne (Pentatonik) und ein hüpfender Bass."""
    track = np.zeros(len(_t(seconds)))
    scale = [60, 62, 64, 67, 69, 72, 74, 76]
    step = 60 / 118 / 2
    at, i = 0.0, 0
    while at < seconds:
        if rnd.random() < 0.7:
            note = scale[rnd.integers(len(scale))]
            _place(track, _note(_hz(note), 0.35, 0.09, (1.0, 0.35, 0.12)), at, 0.45)
        if i % 4 == 0:
            bass = [48, 48, 53, 55][(i // 16) % 4]
            _place(track, _note(_hz(bass), 0.25, 0.08, (1.0, 0.4)), at, 0.6)
        at += step
        i += 1
    return track


def _pad(seconds: float, chords: list[list[int]], chord_len: float, bright: float) -> np.ndarray:
    track = np.zeros(len(_t(seconds)))
    at, i = 0.0, 0
    while at < seconds:
        notes = chords[i % len(chords)]
        t = _t(chord_len + 1.5)
        env = np.minimum(1, t / 1.2) * np.minimum(1, np.maximum(0, (chord_len + 1.5 - t) / 1.5))
        for n in notes:
            f = _hz(n)
            tone = sum(a * np.sin(2 * np.pi * f * k * t * (1 + d)) for k, a, d in
                       ((1, 1.0, 0), (1, 0.6, 0.004), (2, 0.25, 0), (3, 0.08 * bright, 0)))
            _place(track, tone * env, at, 0.22)
        at += chord_len
        i += 1
    return _lowpass(track, 900 + 1500 * bright)


def pad(seconds: float, rnd: np.random.Generator) -> np.ndarray:
    """Drama: ruhige Moll-Flächen (Am – F – C – G)."""
    return _pad(seconds, [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], 4.0, 0.3)


def warm(seconds: float, rnd: np.random.Generator) -> np.ndarray:
    """Herzerwärmend: warme Dur-Akkorde mit leisen Glöckchen."""
    track = _pad(seconds, [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]], 4.0, 0.6)
    at = 1.0
    while at < seconds:
        f = _hz([72, 76, 79, 84][rnd.integers(4)])
        bell = _note(f, 1.6, 0.5, (1.0,)) + 0.4 * _note(f * 2.76, 1.6, 0.25, (1.0,))
        _place(track, bell, at, 0.12)
        at += rnd.uniform(1.5, 3.5)
    return track


def beat(seconds: float, rnd: np.random.Generator) -> np.ndarray:
    """Rache: lässiger Beat mit Bass."""
    track = np.zeros(len(_t(seconds)))
    step = 60 / 95 / 2
    kt = _t(0.35)
    kick = np.sin(2 * np.pi * (50 + 70 * np.exp(-kt / 0.04)) * kt) * np.exp(-kt / 0.12)
    snare = (_highpass(rnd.standard_normal(len(kt)), 1500) * 0.6 + np.sin(2 * np.pi * 185 * kt)) * np.exp(-kt / 0.06)
    hat = _highpass(rnd.standard_normal(int(0.05 * SR)), 7000) * np.exp(-_t(0.05) / 0.012)
    at, i = 0.0, 0
    while at < seconds:
        if i % 8 in (0, 5):
            _place(track, kick, at, 0.9)
        if i % 8 == 4:
            _place(track, snare, at, 0.5)
        _place(track, hat, at, 0.15)
        if i % 2 == 0:
            _place(track, _note(_hz([36, 36, 39, 41][(i // 16) % 4]), step * 1.8, 0.2, (1.0, 0.5, 0.3)), at, 0.45)
        at += step
        i += 1
    return track


STYLES = {"drone": drone, "pulse": pulse, "pluck": pluck, "pad": pad, "warm": warm, "beat": beat}


def make_music(style: str, seconds: float, path: Path, seed: int = 1) -> Path:
    """Stereo-WAV der gewünschten Länge, sanft ein- und ausgeblendet, Spitze bei −6 dBFS."""
    rnd = np.random.default_rng(seed)
    mono = STYLES[style](seconds, rnd)
    fade = min(len(mono) // 4, int(1.5 * SR))
    if fade:
        mono[:fade] *= np.linspace(0, 1, fade)
        mono[-fade:] *= np.linspace(1, 0, fade)
    mono = mono / (np.max(np.abs(mono)) or 1) * 0.5
    delay = int(0.012 * SR)                                      # etwas Breite
    right = np.concatenate([np.zeros(delay), mono[:-delay]]) if len(mono) > delay else mono
    stereo = np.stack([mono, 0.85 * right + 0.15 * mono], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    return path
