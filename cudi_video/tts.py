"""KI-Stimme mit edge-tts (kostenlos) inklusive Wort-Zeitstempeln für die Untertitel."""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import subprocess
import wave
from pathlib import Path

import numpy as np

import edge_tts
import edge_tts.communicate

from . import config
from .models import Script

log = logging.getLogger(__name__)

# edge-tts nutzt fest das certifi-Bundle. Hinter Firmen-/Cloud-Proxys mit eigenem
# Zertifikat (SSL_CERT_FILE) muss dieses verwendet werden.
if os.environ.get("SSL_CERT_FILE"):
    edge_tts.communicate._SSL_CTX = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])

TICKS_PER_SECOND = 10_000_000  # edge-tts liefert Offsets in 100-ns-Einheiten


async def _synthesize(text: str, voice: str, out_path: Path, rate: str) -> list[dict]:
    words: list[dict] = []
    for attempt in range(3):
        words.clear()
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
            with open(out_path, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / TICKS_PER_SECOND
                        words.append({
                            "text": chunk["text"],
                            "start": round(start, 3),
                            "end": round(start + chunk["duration"] / TICKS_PER_SECOND, 3),
                        })
            if out_path.stat().st_size > 0:
                return words
        except Exception as exc:  # Netzwerkfehler -> erneut versuchen
            log.warning("TTS-Versuch %d fehlgeschlagen: %s", attempt + 1, exc)
        await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Sprachausgabe fehlgeschlagen für: {text[:60]}…")


SAMPLE_RATE = 48_000
MAX_PAUSE = 0.28        # edge-tts pausiert nach jedem Punkt ~1 s – für Shorts zu langsam
SILENCE_RMS = 0.01      # ~ -40 dB


def tighten_pauses(mp3: Path, words: list[dict], wav: Path) -> tuple[list[dict], float]:
    """Lange Pausen kürzen und die Wort-Zeitstempel entsprechend verschieben."""
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(mp3), "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    win = SAMPLE_RATE // 100                                    # 10-ms-Fenster
    n_win = len(audio) // win
    rms = np.sqrt(np.mean(audio[: n_win * win].reshape(n_win, win) ** 2, axis=1))
    silent = rms < SILENCE_RMS
    keep = np.ones(len(audio), dtype=bool)
    cuts: list[tuple[float, float]] = []                       # (Zeitpunkt, entfernte Sekunden)
    max_win = int(MAX_PAUSE * 100)
    i = 0
    while i < n_win:
        if silent[i]:
            j = i
            while j < n_win and silent[j]:
                j += 1
            if j - i > max_win and i > 0 and j < n_win:         # nur Pausen zwischen Wörtern
                a = (i + max_win // 2) * win
                b = (j - max_win // 2) * win
                keep[a:b] = False
                cuts.append((a / SAMPLE_RATE, (b - a) / SAMPLE_RATE))
            i = j
        else:
            i += 1

    def shift(t: float) -> float:
        return t - sum(removed for at, removed in cuts if at < t)

    new_words = [{**w, "start": round(shift(w["start"]), 3), "end": round(shift(w["end"]), 3)} for w in words]
    pcm = (np.clip(audio[keep], -1, 1) * 32767).astype(np.int16)
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())
    return new_words, len(pcm) / SAMPLE_RATE


async def _voice_script(script: Script, out_dir: Path, voice: str, rate: str, parallel: int = 4) -> None:
    sem = asyncio.Semaphore(parallel)

    async def one(i, seg):
        async with sem:
            mp3 = out_dir / f"{i:02d}_{seg.kind}.mp3"
            words = await _synthesize(seg.text, voice, mp3, rate)
            wav = mp3.with_suffix(".wav")
            seg.words, seg.duration = tighten_pauses(mp3, words, wav)
            seg.audio_path = str(wav)

    await asyncio.gather(*(one(i, seg) for i, seg in enumerate(script.segments)))


def voice_script(script: Script, out_dir: Path, voice: str | None = None, rate: str | None = None) -> Script:
    out_dir.mkdir(parents=True, exist_ok=True)
    voice = voice or config.VOICES[script.lang]
    asyncio.run(_voice_script(script, out_dir, voice, rate or config.VOICE_RATE))
    return script
