"""Cache (24 h) und Begrenzung (Seiten/Suchen je Lauf) der Recherche – schnell und sparsam, nichts wird doppelt geladen."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from .. import config

STUNDEN = 24.0
_lock = threading.Lock()
_zaehler = {"seiten": 0, "suchen": 0}


def verzeichnis() -> Path:
    return Path(os.environ.get("CUDI_RECHERCHE_CACHE_DIR") or (config.OUTPUT_DIR / "_cache" / "recherche"))


def _datei(art: str, key: str) -> Path:
    return verzeichnis() / art / (hashlib.sha256(key.encode("utf-8")).hexdigest()[:32] + ".json")


def lade(art: str, key: str, stunden: float = STUNDEN):
    if os.environ.get("CUDI_RECHERCHE_CACHE") == "0":
        return None
    p = _datei(art, key)
    try:
        if time.time() - p.stat().st_mtime > stunden * 3600:
            return None
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def speichere(art: str, key: str, wert) -> None:
    if os.environ.get("CUDI_RECHERCHE_CACHE") == "0":
        return
    p = _datei(art, key)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(wert, ensure_ascii=False), "utf-8")
        tmp.replace(p)
    except OSError:
        pass


def limit(art: str) -> int:
    standard = {"seiten": 10, "suchen": 12}[art]
    try:
        return max(0, int(os.environ.get(f"CUDI_RECHERCHE_{art.upper()}", standard)))
    except ValueError:
        return standard


def verbrauche(art: str) -> bool:
    """True, wenn noch Budget da ist (und zählt es ab)."""
    with _lock:
        if _zaehler[art] >= limit(art):
            return False
        _zaehler[art] += 1
        return True


def rest(art: str) -> int:
    with _lock:
        return max(0, limit(art) - _zaehler[art])


def neuer_lauf() -> None:
    with _lock:
        _zaehler.update(seiten=0, suchen=0)
