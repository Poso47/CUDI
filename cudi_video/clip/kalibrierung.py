"""Gewichte der Clip-Auswahl aus Urteilen lernen (👍/👎 aus der App, Urteile des Nutzers).

Jeder fertige Clip trägt seine Signale (`clip.json` → `signale`). Gewichte ändern sich erst, wenn es je Seite
(gut/schlecht) mindestens `MIN_JE_SEITE` Urteile gibt – davor gilt der Standard. Datei: `firma_daten/clip_kalibrierung.json`.
"""

from __future__ import annotations

import json

from .erlaubnis import daten_ordner

MIN_JE_SEITE = 20
SIGNALE = ("dichte", "einstieg", "pointe", "laenge", "titel", "szene", "offen")
STANDARD = {s: 1.0 for s in SIGNALE}
DATEI = "clip_kalibrierung.json"


def gewichte() -> dict[str, float]:
    """Gewichte je Signal (Standard 1.0); nur aus belastbaren Urteilen abweichend."""
    try:
        d = json.loads((daten_ordner() / DATEI).read_text("utf-8"))
    except (OSError, ValueError):
        return dict(STANDARD)
    if not isinstance(d, dict) or not d.get("belastbar"):
        return dict(STANDARD)
    w = d.get("gewichte") or {}
    return {s: min(1.5, max(0.5, float(w.get(s, 1.0)))) for s in SIGNALE}


def berechne(zeilen: list[dict]) -> dict:
    """zeilen: [{"urteil": "gut"|"schlecht", "signale": {...}}]. Gibt das Dokument für die Datei zurück."""
    gut = [z["signale"] for z in zeilen if z.get("urteil") == "gut" and z.get("signale")]
    schlecht = [z["signale"] for z in zeilen if z.get("urteil") == "schlecht" and z.get("signale")]
    belastbar = min(len(gut), len(schlecht)) >= MIN_JE_SEITE

    def mittel(rows, k):
        v = [float(r[k]) for r in rows if k in r]
        return sum(v) / len(v) if v else 0.0

    w = dict(STANDARD)
    if belastbar:
        for k in SIGNALE:
            g, s = mittel(gut, k), mittel(schlecht, k)
            w[k] = round(min(1.5, max(0.5, 1.0 + 0.5 * (g - s) / (abs(g) + abs(s) + 1e-6))), 3)
    return {"gut": len(gut), "schlecht": len(schlecht), "belastbar": belastbar, "mindestens": MIN_JE_SEITE,
            "gewichte": w}


def schreibe(zeilen: list[dict]) -> dict:
    doc = berechne(zeilen)
    ziel = daten_ordner() / DATEI
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    return doc
