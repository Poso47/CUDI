"""Szenen-Skript des Erklärvideos laden und prüfen."""

from __future__ import annotations

import json
from pathlib import Path

from ..render.linien import POSES, VISUALS


class ScriptError(ValueError):
    """Fehler im Szenen-Skript (Meldung auf Deutsch)."""


def validate_script(data: dict) -> dict:
    """Prüft und normalisiert das Skript: {"id", "titel", "sprache", "szenen": [...]}."""
    if not isinstance(data, dict) or not isinstance(data.get("szenen"), list) or not data["szenen"]:
        raise ScriptError("Das Skript braucht eine nichtleere Liste „szenen“.")
    out = {"id": str(data.get("id") or "erklaerung"), "titel": str(data.get("titel") or "Erklärvideo"),
           "sprache": str(data.get("sprache") or "de"), "szenen": []}
    for i, sz in enumerate(data["szenen"], start=1):
        sz = sz if isinstance(sz, dict) else {}
        text = str(sz.get("text") or "").strip()
        if not text:
            raise ScriptError(f"Szene {i}: „text“ (Sprechertext) fehlt.")
        visual = dict(sz.get("visual") or {"typ": "beschriftung"})
        typ = visual.get("typ")
        if typ not in VISUALS:
            raise ScriptError(f"Szene {i}: unbekannte Grafik „{typ}“ – erlaubt: {', '.join(VISUALS)}.")
        if typ == "figur" and visual.get("pose", "stehen") not in POSES:
            raise ScriptError(f"Szene {i}: unbekannte Pose „{visual.get('pose')}“ – erlaubt: {', '.join(POSES)}.")
        if typ == "zitatkarte" and not str(visual.get("zitat") or "").strip():
            raise ScriptError(f"Szene {i}: Zitat-Karte ohne „zitat“.")
        betont = [str(w) for w in (sz.get("betont") or [])]
        out["szenen"].append({"kapitel": str(sz.get("kapitel") or ""), "text": text, "betont": betont, "visual": visual})
    return out


def load_script(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScriptError(f"Skript nicht lesbar: {exc}") from exc
    return validate_script(data)
