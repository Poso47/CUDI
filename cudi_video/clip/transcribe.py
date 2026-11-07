"""Spracherkennung: faster-whisper, Audio per ffmpeg als numpy-Array (nicht als Pfad – pyav-Inkompatibilität)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np

from . import ClipError

SR = 16000
MODELL = os.environ.get("CUDI_CLIP_MODELL", "small")


def dekodiere_audio(video: Path, start: float = 0.0, ende: float | None = None) -> np.ndarray:
    """16 kHz mono float32 (ggf. nur der Bereich start..ende)."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    if ende is not None:
        cmd += ["-t", f"{max(0.1, ende - start):.3f}"]
    cmd += ["-i", str(video), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0 or not res.stdout:
        raise ClipError("Audio konnte nicht gelesen werden: " + res.stderr.decode("utf-8", "replace")[-200:])
    return np.frombuffer(res.stdout, dtype=np.float32).copy()


def erkenne(audio: np.ndarray, sprache: str | None) -> list[dict]:
    """Wörter mit start/ende (Sekunden relativ zum Audio). Einziger Ort, an dem das Modell läuft (Tests ersetzen ihn)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise ClipError("faster-whisper fehlt (pip install faster-whisper).") from exc
    model = WhisperModel(MODELL, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio, language=None if sprache in (None, "auto") else sprache,
                                       word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": round(float(w.start), 3), "e": round(float(w.end), 3),
                          "p": round(float(getattr(w, "probability", 1.0)), 3)})
    return [w for w in words if w["w"]]


def transkribiere(video: Path, arbeit: Path, sprache: str | None = "de", start: float = 0.0,
                  ende: float | None = None) -> tuple[list[dict], np.ndarray, float]:
    """Gibt (Wörter in Quellzeit, Audio ab `offset`, offset) zurück; Wörter werden als JSON zwischengespeichert."""
    st = video.stat()
    roh = f"{video.name}|{st.st_size}|{int(st.st_mtime)}|{MODELL}|{sprache}|{start}|{ende}"
    cache = arbeit / f"woerter_{hashlib.sha1(roh.encode()).hexdigest()[:12]}.json"
    audio = dekodiere_audio(video, start, ende)
    if cache.exists():
        words = json.loads(cache.read_text("utf-8"))
    else:
        words = erkenne(audio, sprache)
        for w in words:
            w["s"] = round(w["s"] + start, 3)
            w["e"] = round(w["e"] + start, 3)
        arbeit.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(words, ensure_ascii=False), "utf-8")
    if not words:
        raise ClipError("Keine Sprache erkannt – Clips brauchen gesprochene Inhalte.")
    return words, audio, start


def lautstaerke(audio: np.ndarray, schritt: float = 0.1) -> np.ndarray:
    """RMS je `schritt` Sekunden."""
    n = int(SR * schritt)
    k = len(audio) // n
    if k == 0:
        return np.zeros(1)
    return np.sqrt((audio[: k * n].reshape(k, n) ** 2).mean(axis=1))
