"""Visuelle Bildprüfung: Zeigt der Clip/das Foto wirklich das Motiv? (kostenloses CLIP-Modell, CPU)

Tags und Titel lügen oft („shark“ im Tag, im Bild nur Wasser). Darum werden je Kandidat 3 Bilder (20/50/80 % der
Clipdauer, bei Fotos das Bild) mit dem Motiv („a photo of shark teeth“) und Gegenproben („the ocean“, „a person“,
„text“ …) verglichen. Ein Bild zählt, wenn das Motiv vorn liegt und eine Mindest-Wahrscheinlichkeit erreicht; ein
Kandidat zählt, wenn mindestens 2 von 3 Bildern zählen. Unter den passenden gewinnt der mit dem höchsten Mittelwert.

Das Modell (open_clip ViT-B-32, OpenAI-Gewichte) wird einmal geladen und liegt danach im Cache
(`video_output/_models`). Fällt es aus (kein Netz, kein Speicher, nicht installierbar), meldet `available()` False
und alle Aufrufer bleiben still beim Tag-Abgleich – nie ein Fehlschlag. Abschalten: `CUDI_BILDPRUEFUNG=0`.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

FRACTIONS = (0.2, 0.5, 0.8)
MIN_PROB = 0.5               # so viel Wahrscheinlichkeit muss das Motiv (gegen die Gegenproben) mindestens haben
MIN_FRAMES = 2               # von 3 Bildern
MAX_CANDIDATES = 8           # Kandidaten je Suche
BUDGET_SECONDS = 9.0         # Zeitbudget je Suche für die Kandidatenprüfung (danach: bester bisher)
GOOD_ENOUGH = 0.9            # ab diesem Wert wird nicht weiter gesucht
COUNTERS = ("a photo of the ocean", "a photo of a person", "a photo of text", "a blurry photo of nothing in particular")

_state: dict = {"model": None, "failed": False}


def enabled() -> bool:
    return os.environ.get("CUDI_BILDPRUEFUNG", "1") != "0" and not _state["failed"]


def _pip_install(*args: str) -> bool:
    for extra in ([], ["--break-system-packages"]):
        try:
            done = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *extra,
                                   *args], capture_output=True, timeout=900)
        except (OSError, subprocess.SubprocessError):
            return False
        if done.returncode == 0:
            return True
    return False


def _load():
    try:
        import open_clip
        import torch
    except Exception:                                    # nicht installiert (oder kaputt) – einmal versuchen
        cpu = ["--index-url", "https://download.pytorch.org/whl/cpu"]
        if not (_pip_install("torch", *cpu) and _pip_install("--force-reinstall", "--no-deps", "torchvision", *cpu)
                and _pip_install("open_clip_torch")):
            raise
        import open_clip
        import torch
    cache = config.OUTPUT_DIR / "_models"
    cache.mkdir(parents=True, exist_ok=True)
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32-quickgelu", pretrained="openai", cache_dir=str(cache))
    model.eval()
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    return model, preprocess, open_clip.get_tokenizer("ViT-B-32-quickgelu"), torch


def model():
    """(model, preprocess, tokenizer, torch) oder None, wenn das Modell nicht verfügbar ist (dann nur Tag-Abgleich)."""
    if not enabled():
        return None
    if _state["model"] is None:
        started = time.time()
        try:
            _state["model"] = _load()
            log.info("Bildprüfung (CLIP) geladen in %.1fs", time.time() - started)
        except Exception as exc:
            _state["failed"] = True
            log.warning("Bildprüfung nicht verfügbar – es bleibt beim Tag-Abgleich: %s", exc)
            return None
    return _state["model"]


def available() -> bool:
    return model() is not None


def prompts(motif: str) -> list[str]:
    """Motiv gegen Gegenproben (Ozean, Person, Text, Unscharfes)."""
    return [f"a photo of {motif}", *COUNTERS]


def probabilities(motif: str, images: list) -> list[float]:
    """Wahrscheinlichkeit des Motivs je Bild (PIL-Bilder oder Pfade), gegen die Gegenproben."""
    from PIL import Image

    loaded = model()
    if loaded is None or not images:
        return []
    mdl, preprocess, tokenizer, torch = loaded
    pics = []
    for img in images:
        try:
            pics.append(img if hasattr(img, "convert") else Image.open(img))
            pics[-1] = pics[-1].convert("RGB")
        except Exception:
            continue
    if not pics:
        return []
    with torch.no_grad():
        feats = mdl.encode_image(torch.stack([preprocess(p) for p in pics]))
        text = mdl.encode_text(tokenizer(prompts(motif)))
        feats = feats / feats.norm(dim=-1, keepdim=True)
        text = text / text.norm(dim=-1, keepdim=True)
        probs = (100.0 * feats @ text.T).softmax(dim=-1)[:, 0]
    return [float(p) for p in probs]


def judge(motif: str, images: list) -> tuple[bool, float]:
    """(zählt der Kandidat?, Mittelwert der Motiv-Wahrscheinlichkeit). Ohne Modell/Bilder: (False, 0.0)."""
    probs = probabilities(motif, images)
    if not probs:
        return False, 0.0
    need = min(MIN_FRAMES, len(probs))
    good = sum(p >= MIN_PROB for p in probs)
    return good >= need, sum(probs) / len(probs)


def video_frames(path, duration: float = 0.0, fractions=FRACTIONS) -> list:
    """Drei Bilder (20/50/80 % der Dauer) aus einer Videodatei als PIL-Bilder."""
    import io

    from PIL import Image

    if not duration:
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                  "default=nw=1:nk=1", str(path)], capture_output=True, timeout=30, text=True).stdout
            duration = float(out.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            duration = 5.0
    frames = []
    for fraction in fractions:
        try:
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{duration * fraction:.2f}", "-i", str(path),
                                  "-frames:v", "1", "-vf", "scale=-2:360", "-f", "image2pipe", "-vcodec", "png", "-"],
                                 capture_output=True, timeout=30).stdout
            frames.append(Image.open(io.BytesIO(raw)).convert("RGB"))
        except Exception:
            continue
    return frames


def spread(items: list, fractions=FRACTIONS) -> list:
    """Drei Einträge einer Bilderliste bei 20/50/80 % (Pexels liefert Vorschaubilder über die ganze Dauer)."""
    if not items:
        return []
    return [items[min(len(items) - 1, int(f * len(items)))] for f in fractions]
