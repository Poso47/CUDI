"""KI-Stimme mit edge-tts (kostenlos) inklusive Wort-Zeitstempeln für die Untertitel.

Fällt der Gratis-Dienst aus, spricht Piper (quelloffen, offline, ebenfalls kostenlos) das ganze Video."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import ssl
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

import edge_tts
import edge_tts.communicate

from . import config, net
from .models import Script

log = logging.getLogger(__name__)

# edge-tts nutzt fest das certifi-Bundle. Hinter Firmen-/Cloud-Proxys mit eigenem
# Zertifikat (SSL_CERT_FILE) muss dieses verwendet werden.
if os.environ.get("SSL_CERT_FILE"):
    edge_tts.communicate._SSL_CTX = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])

TICKS_PER_SECOND = 10_000_000  # edge-tts liefert Offsets in 100-ns-Einheiten


TTS_ATTEMPTS = 6        # der Gratis-Dienst liefert zeitweise „No audio was received“ – meist klappt es kurz danach


async def _synthesize(text: str, voice: str, out_path: Path, rate: str, pitch: str = "+0Hz") -> list[dict]:
    words: list[dict] = []
    last = "keine Audiodaten"
    for attempt in range(TTS_ATTEMPTS):
        if attempt:
            await asyncio.sleep(min(2 ** attempt, 30))     # 2, 4, 8, 16, 30 s ≈ 1 Minute Geduld
        words.clear()
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
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
            last = "keine Audiodaten"
        except Exception as exc:  # Netzwerk-/Dienstfehler -> erneut versuchen
            last = f"{type(exc).__name__}: {exc}"
            log.warning("TTS-Versuch %d fehlgeschlagen: %s", attempt + 1, exc)
    raise RuntimeError(f"Sprachausgabe fehlgeschlagen für: {text[:60]}… ({last[:160]})")


SAMPLE_RATE = 48_000
MAX_PAUSE = 0.28        # edge-tts pausiert nach jedem Punkt ~1 s – für Shorts zu langsam
SILENCE_RMS = 0.01      # ~ -40 dB


def tighten_pauses(mp3: Path, words: list[dict], wav: Path, max_pause: float = MAX_PAUSE) -> tuple[list[dict], float]:
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
    max_win = int(max_pause * 100)
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


# --------------------------------------------------------------------------- Ersatzstimme (Piper)
# Kostenlose, quelloffene Stimmen, die offline laufen (Modell einmalig von Hugging Face, ~60 MB).
# Ein Video bekommt dann durchgehend die Ersatzstimme – kein Stimmwechsel mitten im Video.
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
PIPER_VOICES = {("de", "m"): "de/de_DE/thorsten/medium/de_DE-thorsten-medium",
                ("de", "f"): "de/de_DE/kerstin/low/de_DE-kerstin-low",
                ("en", "m"): "en/en_US/ryan/medium/en_US-ryan-medium",
                ("en", "f"): "en/en_US/amy/medium/en_US-amy-medium"}
FEMALE_VOICES = ("amala", "katja", "seraphina", "aria", "emma", "ava", "jenny", "michelle", "sonia", "libby")
PUNCT = ".,!?;:…\"'„“”«»()–-"
NOTES: list[str] = []            # Hinweise fürs Ergebnis (z. B. Ersatzstimme) – abholen mit take_notes()
_piper_cache: dict = {}


def take_notes() -> list[str]:
    notes = list(dict.fromkeys(NOTES))
    NOTES.clear()
    return notes


def piper_key(edge_voice: str) -> tuple[str, str]:
    """Sprache und Geschlecht der edge-Stimme (z. B. de-DE-KatjaNeural -> ("de", "f"))."""
    lang = "de" if edge_voice.lower().startswith("de-") else "en"
    return lang, ("f" if edge_voice.split("-")[-1].lower().startswith(FEMALE_VOICES) else "m")


def _pip_install(package: str) -> None:
    for extra in ([], ["--break-system-packages"]):
        if subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *extra,
                           package], capture_output=True).returncode == 0:
            return


def _piper_voice(key: tuple[str, str]):
    if key in _piper_cache:
        return _piper_cache[key]
    try:
        from piper import PiperVoice
    except ImportError:                                   # nur bei Bedarf installieren
        _pip_install("piper-tts")
        from piper import PiperVoice
    folder = config.OUTPUT_DIR / "_piper"
    folder.mkdir(parents=True, exist_ok=True)
    name = PIPER_VOICES[key]
    model = folder / (Path(name).name + ".onnx")
    for path, url in ((model, PIPER_BASE + name + ".onnx"),
                      (model.with_name(model.name + ".json"), PIPER_BASE + name + ".onnx.json")):
        if not path.exists() or path.stat().st_size < 1000:
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(net.get(url, timeout=300, retries=4).content)
            tmp.replace(path)
    _piper_cache[key] = PiperVoice.load(str(model))
    return _piper_cache[key]


def _piper_config(length_scale: float):
    from piper import SynthesisConfig
    return SynthesisConfig(length_scale=length_scale)


def _percent(value: str) -> float:
    m = re.match(r"\s*([+-]?\d+(?:\.\d+)?)\s*%", value or "")
    return float(m.group(1)) if m else 0.0


def piper_synthesize(text: str, edge_voice: str, out_wav: Path, rate: str = "+0%") -> list[dict]:
    """Text mit Piper vertonen. Wortzeiten: je Satz exakt, im Satz nach Wortlänge verteilt."""
    voice = _piper_voice(piper_key(edge_voice))
    cfg = _piper_config(min(2.0, max(0.5, 1.0 / (1.0 + _percent(rate) / 100))))
    sample_rate = voice.config.sample_rate
    pcm, words, t = [], [], 0.0
    for sentence in (s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()):
        audio = b"".join(c.audio_int16_bytes for c in voice.synthesize(sentence, syn_config=cfg))
        duration = len(audio) / 2 / sample_rate
        tokens = [w.strip(PUNCT) for w in sentence.split() if w.strip(PUNCT)]
        weights = [len(w) + 2 for w in tokens]
        total, pos = sum(weights) or 1, t
        for word, weight in zip(tokens, weights):
            part = duration * weight / total
            words.append({"text": word, "start": round(pos, 3), "end": round(pos + 0.9 * part, 3)})
            pos += part
        pcm.append(audio)
        t += duration
    if not pcm or not any(pcm):
        raise RuntimeError(f"Ersatzstimme lieferte nichts für: {text[:60]}…")
    with wave.open(str(out_wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(b"".join(pcm))
    return words


async def _speak_all(texts: list[str], out_dir: Path, voice: str, rate: str, pitch: str,
                     parallel: int = 2) -> list[tuple[Path, list[dict]]]:
    """Alle Texte mit edge-tts; liefert ein Text nichts, alle mit der Ersatzstimme (einheitlicher Klang)."""
    sem = asyncio.Semaphore(parallel)

    async def one(i: int, text: str):
        async with sem:
            mp3 = out_dir / f"{i:03d}.mp3"
            return mp3, await _synthesize(text, voice, mp3, rate, pitch)

    tasks = [asyncio.create_task(one(i, t)) for i, t in enumerate(texts)]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    failed = next((t.exception() for t in done if t.exception() is not None), None)
    if failed is None:
        return [t.result() for t in tasks]
    for t in pending:                                       # Dienst ist aus: nicht auf jeden Abschnitt warten
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    log.warning("edge-tts liefert nichts (%s) – Ersatzstimme Piper für alle Abschnitte", failed)
    try:
        spoken = []
        for i, text in enumerate(texts):
            path = out_dir / f"{i:03d}.piper.wav"
            spoken.append((path, piper_synthesize(text, voice, path, rate)))
    except Exception as exc:
        raise RuntimeError(f"Sprachausgabe fehlgeschlagen ({failed}); Ersatzstimme ebenfalls: "
                           f"{type(exc).__name__}: {exc}"[:400]) from exc
    NOTES.append("Ersatzstimme (Piper) verwendet: Der kostenlose Microsoft-Sprachdienst antwortete gerade nicht.")
    return spoken


async def _voice_script(script: Script, out_dir: Path, voice: str, rate: str, parallel: int = 2) -> None:
    spoken = await _speak_all([seg.text for seg in script.segments], out_dir, voice, rate, "+0Hz", parallel)
    for i, (seg, (src, words)) in enumerate(zip(script.segments, spoken)):
        wav = out_dir / f"{i:02d}_{seg.kind}.wav"
        seg.words, seg.duration = tighten_pauses(src, words, wav)
        seg.audio_path = str(wav)


def voice_script(script: Script, out_dir: Path, voice: str | None = None, rate: str | None = None) -> Script:
    out_dir.mkdir(parents=True, exist_ok=True)
    voice = voice or config.VOICES[script.lang]
    asyncio.run(_voice_script(script, out_dir, voice, rate or config.VOICE_RATE))
    return script


async def _voice_texts(texts: list[str], out_dir: Path, voice: str, rate: str, pitch: str, max_pause: float,
                       parallel: int = 2) -> list[tuple[Path, list[dict], float]]:
    spoken = await _speak_all(texts, out_dir, voice, rate, pitch, parallel)
    result = []
    for i, (src, words) in enumerate(spoken):
        wav = out_dir / f"{i:03d}.wav"
        new_words, duration = tighten_pauses(src, words, wav, max_pause)
        result.append((wav, new_words, duration))
    return result


def voice_texts(texts: list[str], out_dir: Path, voice: str, rate: str = "+0%", pitch: str = "+0Hz",
                max_pause: float = MAX_PAUSE) -> list[tuple[Path, list[dict], float]]:
    """Mehrere Texte vertonen (z. B. Story-Szenen): je Text (WAV, Wort-Zeitstempel, Dauer)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_voice_texts(texts, out_dir, voice, rate, pitch, max_pause))
