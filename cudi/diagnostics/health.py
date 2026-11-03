"""Selbstdiagnose: unterscheidet kritische Fehler, Warnungen und optionale Einschränkungen."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:  # pragma: no cover
    from ..core.application import Application

OK, WARNING, CRITICAL, OPTIONAL = "ok", "warnung", "kritisch", "optional"
ICONS = {OK: "✅", WARNING: "⚠️", CRITICAL: "❌", OPTIONAL: "➖"}


@dataclass
class Check:
    component: str
    level: str
    message: str
    fix: str = ""

    def line(self) -> str:
        text = f"{ICONS[self.level]} {self.component}: {self.message}"
        return text + (f"\n     → {self.fix}" if self.fix else "")


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _writable(path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return True
    except OSError:
        return False


def run_checks(app: "Application") -> List[Check]:
    s = app.settings
    checks: List[Check] = []

    version = sys.version_info
    if version < (3, 9):
        checks.append(Check("Python", CRITICAL, f"Version {version.major}.{version.minor} ist zu alt",
                            "Python 3.10 oder neuer installieren"))
    else:
        checks.append(Check("Python", OK, f"Version {version.major}.{version.minor}.{version.micro}"))

    for label, path in (("Datenordner", s.data_dir), ("Arbeitsordner", s.workspace_dir),
                        ("Importordner", s.import_dir), ("Protokollordner", s.log_dir)):
        if _writable(path):
            checks.append(Check(label, OK, str(path)))
        else:
            checks.append(Check(label, CRITICAL, f"{path} ist nicht beschreibbar", "Ordnerrechte prüfen"))

    try:
        integrity = app.db.integrity_ok()
        checks.append(Check("Datenbank", OK if integrity else CRITICAL,
                            f"{s.db_path.name}, Schema v{app.db.schema_version}, "
                            f"{app.memory.count()} Erinnerungen, {len(app.knowledge.documents())} Dokumente"
                            if integrity else "Integritätsprüfung fehlgeschlagen",
                            "" if integrity else "Sicherung wiederherstellen (/wiederherstellen)"))
        if not app.db.fts_enabled:
            checks.append(Check("Volltextsuche", WARNING, "SQLite ohne FTS5 – Suche ist langsamer/ungenauer",
                                "neuere Python-Version verwenden"))
    except Exception as e:
        checks.append(Check("Datenbank", CRITICAL, f"nicht erreichbar: {e}"))

    any_model = False
    for name, ok, info in app.models.status():
        any_model = any_model or ok
        checks.append(Check(f"Modell {name}", OK if ok else OPTIONAL, info))
    if not any_model:
        checks.append(Check("Sprachmodell", WARNING,
                            "kein Sprachmodell verfügbar – CUDI arbeitet eingeschränkt (Befehle, Gedächtnis, "
                            "Dokumentsuche funktionieren; freie Antworten nicht)",
                            "Ollama installieren oder API-Schlüssel in .env eintragen (siehe docs/user_guide.md)"))

    unavailable = [(t.name, r) for t, r in app.tools.availability() if r]
    checks.append(Check("Werkzeuge", OK if not unavailable else WARNING,
                        f"{len(app.tools.all()) - len(unavailable)} von {len(app.tools.all())} verfügbar"
                        + ("" if not unavailable else ": " + "; ".join(f"{n} ({r})" for n, r in unavailable))))

    for module, label, fix in (("pypdf", "PDF-Import", "pip install pypdf"),
                               ("docx", "DOCX-Import", "pip install python-docx"),
                               ("PySide6", "Desktop-Oberfläche", "pip install PySide6"),
                               ("requests", "Netzwerkzugriff (Ollama/OpenAI)", "pip install requests")):
        if _has_module(module):
            checks.append(Check(label, OK, f"Paket '{module}' vorhanden"))
        else:
            level = WARNING if module in ("requests", "PySide6") else OPTIONAL
            checks.append(Check(label, level, f"Paket '{module}' fehlt", fix))

    checks.append(Check("Sprachsteuerung", OPTIONAL, "noch nicht integriert (geplant, siehe docs/implementation_plan.md)"))
    checks.append(Check("Cloud-Synchronisierung", OPTIONAL, "nicht verfügbar (nicht implementiert)"))
    return checks


def report(app: "Application") -> str:
    checks = run_checks(app)
    critical = sum(c.level == CRITICAL for c in checks)
    warnings = sum(c.level == WARNING for c in checks)
    head = (f"Diagnosebericht {datetime.now():%d.%m.%Y %H:%M} – "
            f"{critical} kritisch, {warnings} Warnungen")
    return head + "\n" + "\n".join(c.line() for c in checks)
