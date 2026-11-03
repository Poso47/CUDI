"""System-Werkzeuge: Diagnose, Sicherung, Wiederherstellung, Export, Altbestand-Import."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..core.permissions import Level
from ..diagnostics.health import report
from .registry import Tool, ToolOutput, ToolRegistry

if TYPE_CHECKING:  # pragma: no cover
    from ..core.application import Application


def legacy_sources(base_dir: Path) -> List[Path]:
    sources = []
    kb = base_dir / "config" / "knowledge_base.json"
    if kb.exists():
        sources.append(kb)
    sources += sorted(base_dir.glob("CUDI_BACKUPS/*/databases/cudi_autonomous_knowledge.db"))
    return sources


def read_legacy(path: Path) -> List[Tuple[str, str, str]]:
    """Liefert (thema, inhalt, quelle) aus alten Wissensspeichern; Platzhalter werden verworfen."""
    items: List[Tuple[str, str, str]] = []
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        for topic, entry in (data or {}).items():
            definition = (entry or {}).get("definition", "")
            if not definition or "Recherche-Fehler" in definition or entry.get("source") == "fallback":
                continue
            items.append((topic, definition, f"altbestand:{path.name}"))
    elif path.suffix == ".db":
        conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        try:
            rows = conn.execute("SELECT topic, content, source FROM knowledge_base").fetchall()
        finally:
            conn.close()
        for topic, content, source in rows:
            if content and "läuft" not in content[:80]:
                items.append((topic, content.strip(), f"altbestand:{path.name} ({source})"))
    return items


def register(registry: ToolRegistry, app: "Application") -> None:
    s = app.settings

    def system_diagnosis() -> ToolOutput:
        text = report(app)
        return ToolOutput(True, text, summary=text.splitlines()[0])

    def create_backup() -> ToolOutput:
        path = app.db.backup(s.backup_dir, keep=s.backups_keep)
        return ToolOutput(True, f"Sicherung erstellt: {path}", summary=f"Sicherung {path.name}")

    def list_backups() -> ToolOutput:
        files = sorted(s.backup_dir.glob("cudi_brain_*.db"), reverse=True)
        if not files:
            return ToolOutput(True, "Es gibt noch keine Sicherungen.", summary="keine Sicherungen")
        return ToolOutput(True, "\n".join(f"{f.name} ({f.stat().st_size // 1024} KB)" for f in files),
                          summary=f"{len(files)} Sicherungen")

    def restore_backup(file: str) -> ToolOutput:
        path = Path(file)
        if not path.is_absolute():
            path = s.backup_dir / path.name
        if not path.is_file():
            return ToolOutput(False, f"Sicherung nicht gefunden: {path.name}")
        try:
            safety = app.db.restore(path, s.backup_dir)
        except ValueError as e:
            return ToolOutput(False, str(e))
        return ToolOutput(True, f"{path.name} wiederhergestellt. Der vorherige Stand wurde als {safety.name} gesichert.",
                          summary=f"{path.name} wiederhergestellt")

    def export_data() -> ToolOutput:
        export_dir = s.data_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        target = export_dir / f"cudi_export_{datetime.now():%Y%m%d_%H%M%S}.json"
        payload = {"exportiert_am": datetime.now().isoformat(timespec="seconds"),
                   "erinnerungen": app.memory.export(), **app.projects.export(),
                   "dokumente": app.knowledge.documents()}
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return ToolOutput(True, f"Export gespeichert: {target}", summary=f"Export {target.name}")

    def import_legacy_knowledge() -> ToolOutput:
        sources = legacy_sources(s.base_dir)
        if not sources:
            return ToolOutput(True, "Kein Altbestand gefunden.", summary="kein Altbestand")
        stored = dupes = 0
        for src in sources:
            for topic, content, source in read_legacy(src):
                result = app.memory.add(f"{topic}: {content}", source=source, category="knowledge",
                                        status="tentative", confidence=0.5, check_conflicts=False)
                if result.status == "stored":
                    stored += 1
                else:
                    dupes += 1
        return ToolOutput(True, f"{stored} Einträge aus dem Altbestand als „vorläufig“ übernommen, "
                                f"{dupes} waren schon vorhanden. Quellen: {', '.join(p.name for p in sources)}",
                          summary=f"{stored} Alt-Einträge übernommen (vorläufig)")

    registry.register(Tool("system_diagnosis", "Führt die Selbstdiagnose aus (Datenbank, Modelle, Werkzeuge, Pakete).",
                           {"type": "object", "properties": {}}, Level.READ, system_diagnosis))
    registry.register(Tool("create_backup", "Erstellt eine Sicherung des Digitalen Gehirns.",
                           {"type": "object", "properties": {}}, Level.SUGGEST, create_backup))
    registry.register(Tool("list_backups", "Listet vorhandene Sicherungen.",
                           {"type": "object", "properties": {}}, Level.READ, list_backups))
    registry.register(Tool("restore_backup",
                           "Stellt das Digitale Gehirn aus einer Sicherung wieder her (aktueller Stand wird vorher gesichert).",
                           {"type": "object", "properties": {"file": {"type": "string", "description": "Dateiname der Sicherung"}},
                            "required": ["file"]}, Level.CHANGE, restore_backup,
                           describe_call=lambda a: f"Sicherung '{a.get('file')}' wiederherstellen (ersetzt aktuellen Stand)"))
    registry.register(Tool("export_data", "Exportiert Erinnerungen, Projekte, Aufgaben und Dokumentliste als JSON.",
                           {"type": "object", "properties": {}}, Level.SUGGEST, export_data))
    registry.register(Tool("import_legacy_knowledge",
                           "Übernimmt Wissen aus alten CUDI-Speichern (knowledge_base.json, Backup-Datenbank) als „vorläufig“.",
                           {"type": "object", "properties": {}}, Level.PREPARE, import_legacy_knowledge,
                           describe_call=lambda a: "Altes CUDI-Wissen als „vorläufig“ ins Gedächtnis übernehmen"))
