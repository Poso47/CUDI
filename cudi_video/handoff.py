"""Schreibaufträge an Claude in der Auftrags-Sitzung der CUDI-App (kostenlos, ohne Sprachmodell-Schlüssel).

Der Code bereitet eine Aufgabe als Datei vor (Anleitung + geprüfte Daten), die Sitzung schreibt das Ergebnis
als „antwort“ hinein und startet `--weiter`. Der Code prüft jede Antwort streng (Zahlen, Format) und fällt
bei Zweifeln auf seine Textbausteine bzw. den Stichwort-Planer zurück – ein Auftrag scheitert nie daran.

Aktiv nur, wenn die Umgebungsvariable CUDI_SCHREIBEN=1 gesetzt ist (die Auftrags-Sitzung kann antworten)
und CUDI_SCHREIBEN_ORDNER auf den Auftragsordner zeigt (setzt job.run_order).

Notbetrieb (Claude-Nutzungslimit erreicht, Web-App im Hugging-Face-Space): Ist CUDI_SCHREIBEN nicht gesetzt, aber ein
freies Sprachmodell konfiguriert (CUDI_LLM_BASE_URL/_MODEL, z. B. Google Gemini), beantwortet dieses dieselben
Aufgaben mit derselben Anleitung. Alle Prüfungen laufen unverändert; bei Netzfehler oder ungültigem JSON gilt
„keine Antwort“ (None) und damit der Textbaustein-Ausweichweg. Claude bleibt der Motor, das Modell springt nur ein.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger(__name__)

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


def llm_mode() -> bool:
    """Notbetrieb: kein Claude in der Sitzung, aber ein freies Sprachmodell ist konfiguriert."""
    from . import llm

    return not enabled() and llm.available()


def active() -> bool:
    """Schreibaufgaben werden beantwortet – von Claude (Auftrags-Sitzung) oder im Notbetrieb vom Sprachmodell."""
    return enabled() or llm_mode()


def parse_json_answer(text: str):
    """JSON aus einer Modellantwort holen: Codeblöcke und Vor-/Nachtext entfernen. None, wenn nichts Brauchbares."""
    text = re.sub(r"```(?:json|JSON)?", "", text or "").strip()
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[{\[]", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        return value
    return None


LLM_SYSTEM = ("Du bist ein sorgfältiger Redakteur für Kurzvideos. Folge der Anleitung genau. Antworte ausschließlich "
              "mit gültigem JSON im verlangten Format – ohne Erklärtext, ohne Markdown.")


def _ask_llm(task: str, instructions: str, data: dict):
    from . import llm

    if preferences():
        instructions, data = instructions + PREFS_NOTE, {**data, "vorlieben": preferences()}
    user = "ANLEITUNG:\n" + instructions + "\n\nDATEN (JSON):\n" + json.dumps(data, ensure_ascii=False)
    try:
        answer = parse_json_answer(llm.chat(LLM_SYSTEM, user, temperature=0.3, timeout=180))
    except Exception as exc:                      # noqa: BLE001 – Netz, Limit, Format: dann gelten die Textbausteine
        log.warning("Notbetrieb-Sprachmodell (%s) fehlgeschlagen: %s: %s", task, type(exc).__name__, str(exc)[:200])
        return None
    return answer if answer not in ("", [], {}) else None


def task_file(task: str) -> Path:
    return Path(os.environ[DIR_ENV]) / f"schreiben_{task}.json"


def request(task: str, instructions: str, data: dict):
    """Antwort von Claude oder None (nicht aktiv / nicht beantwortet). Fehlt die Antwort noch, wird die
    Aufgabe abgelegt und WritingNeeded geworfen. Jede Aufgabe wird höchstens einmal gestellt."""
    if not enabled():
        if not llm_mode():
            return None
        return _llm_cached(task, instructions, data)
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


def _llm_cached(task: str, instructions: str, data: dict):
    """Notbetrieb: Sprachmodell fragen; mit Auftragsordner wird die Antwort in derselben Aufgabendatei gemerkt
    (ein Weiterlauf oder Neustart fragt nicht noch einmal). Fehlgeschlagene Anfragen werden nicht gemerkt."""
    folder = os.environ.get(DIR_ENV)
    path = task_file(task) if folder and Path(folder).is_dir() else None
    if path and path.exists():
        try:
            cached = json.loads(path.read_text("utf-8")).get("antwort")
        except (OSError, ValueError, AttributeError):
            cached = None
        if cached not in (None, "", [], {}):
            return cached
    answer = _ask_llm(task, instructions, data)
    if answer is not None and path:
        try:
            path.write_text(json.dumps({"aufgabe": task, "anleitung": instructions, "daten": data, "antwort": answer,
                                        "von": "sprachmodell"}, ensure_ascii=False, indent=1), "utf-8")
        except OSError:
            pass
    return answer
