"""Schreibaufträge an Claude in der Auftrags-Sitzung der CUDI-App (kostenlos, ohne Sprachmodell-Schlüssel).

Der Code bereitet eine Aufgabe als Datei vor (Anleitung + geprüfte Daten), die Sitzung schreibt das Ergebnis
als „antwort“ hinein und startet `--weiter`. Der Code prüft jede Antwort streng (Zahlen, Format) und fällt
bei Zweifeln auf seine Textbausteine bzw. den Stichwort-Planer zurück – ein Auftrag scheitert nie daran.

Aktiv nur, wenn die Umgebungsvariable CUDI_SCHREIBEN=1 gesetzt ist (die Auftrags-Sitzung kann antworten)
und CUDI_SCHREIBEN_ORDNER auf den Auftragsordner zeigt (setzt job.run_order).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ENV = "CUDI_SCHREIBEN"
DIR_ENV = "CUDI_SCHREIBEN_ORDNER"
PREFS_ENV = "CUDI_VORLIEBEN"          # Bewertungen aus der App (gut/schlecht) – Claude lernt daraus
PREFS_NOTE = (" Beachte außerdem „vorlieben“: So hat der Nutzer frühere Videos bewertet (gut / schlecht, mit Notiz). "
              "Übernimm, was ihm gefiel, und vermeide, was ihm nicht gefiel – bei Themenwahl, Blickwinkel, Stil, Länge "
              "und Bildideen. Die Prüfregeln oben (nichts erfinden, Belege, Zahlen) haben immer Vorrang.")


def preferences() -> dict:
    try:
        prefs = json.loads(os.environ.get(PREFS_ENV) or "{}")
    except ValueError:
        return {}
    return prefs if isinstance(prefs, dict) else {}


class WritingNeeded(Exception):
    """Claude soll eine Textaufgabe erledigen; danach geht es mit `--weiter` an derselben Stelle weiter."""

    def __init__(self, path: Path):
        super().__init__(f"Schreibaufgabe für Claude: {path}")
        self.path = path


def enabled() -> bool:
    return os.environ.get(ENV) == "1" and bool(os.environ.get(DIR_ENV))


def task_file(task: str) -> Path:
    return Path(os.environ[DIR_ENV]) / f"schreiben_{task}.json"


def request(task: str, instructions: str, data: dict):
    """Antwort von Claude oder None (nicht aktiv / nicht beantwortet). Fehlt die Antwort noch, wird die
    Aufgabe abgelegt und WritingNeeded geworfen. Jede Aufgabe wird höchstens einmal gestellt."""
    if not enabled():
        return None
    path = task_file(task)
    if path.exists():
        try:
            answer = json.loads(path.read_text("utf-8")).get("antwort")
        except (OSError, ValueError, AttributeError):
            return None
        return answer if answer not in ("", [], {}) else None
    prefs = preferences()
    if prefs:
        instructions, data = instructions + PREFS_NOTE, {**data, "vorlieben": prefs}
    path.write_text(json.dumps({"aufgabe": task, "anleitung": instructions, "daten": data, "antwort": None},
                               ensure_ascii=False, indent=1), "utf-8")
    raise WritingNeeded(path)
