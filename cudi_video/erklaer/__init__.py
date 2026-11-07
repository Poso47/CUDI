"""Erklärvideo: ruhiges Hochformat-Video im Buchlook (Stil „manuskript“) aus einem Szenen-Skript (JSON).

Je Szene: Kapitel-Pille, Sprechertext (erscheint Wort für Wort zur Stimme), betonte Wörter (fett-kursiv) und eine
Linien-Grafik (`render/linien.py`) oder Zitat-Karte. Der Text kommt nur aus dem Skript – nichts wird erfunden.

    python -m cudi_video erklaer examples/erklaer_goldener_schnitt.json
"""

from .render import render_erklaerung
from .skript import load_script, validate_script

__all__ = ["load_script", "render_erklaerung", "validate_script"]
