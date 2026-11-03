"""Werkzeuge für Dokumente und Wissensdatenbank."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..brain.knowledge import SUPPORTED, ImportErrorCUDI
from ..core.permissions import Level
from .file_tools import _inside, is_sensitive
from .registry import Tool, ToolOutput, ToolRegistry

if TYPE_CHECKING:  # pragma: no cover
    from ..core.application import Application


def register(registry: ToolRegistry, app: "Application") -> None:
    s = app.settings
    knowledge = app.knowledge

    def resolve(path: str) -> Path:
        p = Path(path.strip().strip('"')).expanduser()
        if p.is_absolute():
            return p.resolve()
        for base in (s.import_dir, s.workspace_dir, s.base_dir):
            candidate = (base / p).resolve()
            if candidate.exists():
                return candidate
        return (s.import_dir / p).resolve()

    def import_level(args) -> int:
        return Level.SUGGEST if _inside(resolve(args.get("path", "")), s.read_roots()) else Level.PREPARE

    def import_document(path: str) -> ToolOutput:
        target = resolve(path)
        if is_sensitive(target):
            return ToolOutput(False, f"{target.name} enthält möglicherweise Zugangsdaten und wird nicht importiert.")
        try:
            status, doc = knowledge.import_file(target)
        except ImportErrorCUDI as e:
            return ToolOutput(False, str(e))
        if status == "duplicate":
            return ToolOutput(True, f"{target.name} ist bereits importiert (als „{doc['name']}“ am "
                                    f"{doc['imported_at'][:10]}). Nichts doppelt gespeichert.",
                              summary=f"{target.name} war bereits importiert")
        app.episodes.record("document_import", f"{doc['name']} importiert ({doc['chunk_count']} Abschnitte)", ok=True)
        return ToolOutput(True, f"{doc['name']} importiert: {doc['chunk_count']} Abschnitte durchsuchbar.",
                          summary=f"{doc['name']} importiert ({doc['chunk_count']} Abschnitte)")

    def import_folder() -> ToolOutput:
        files = [f for f in sorted(s.import_dir.rglob("*"))
                 if f.is_file() and f.suffix.lower() in SUPPORTED and not is_sensitive(f)]
        if not files:
            return ToolOutput(True, f"Im Importordner ({s.import_dir}) liegen keine unterstützten Dateien.",
                              summary="Importordner leer")
        done, dupes, failed = [], [], []
        for f in files:
            try:
                status, _ = knowledge.import_file(f)
                (done if status == "imported" else dupes).append(f.name)
            except ImportErrorCUDI as e:
                failed.append(f"{f.name}: {e}")
        lines = [f"Neu importiert: {', '.join(done) or '–'}", f"Bereits vorhanden: {', '.join(dupes) or '–'}"]
        if failed:
            lines.append("Fehlgeschlagen:\n  " + "\n  ".join(failed))
        return ToolOutput(not failed or bool(done), "\n".join(lines),
                          summary=f"{len(done)} neu, {len(dupes)} vorhanden, {len(failed)} Fehler")

    def search_documents(query: str) -> ToolOutput:
        hits = knowledge.search(query, limit=5)
        if not hits:
            return ToolOutput(True, f"In den importierten Dokumenten nichts zu „{query}“ gefunden.",
                              summary="nichts gefunden")
        body = "\n\n".join(f'<dokument name="{h.document}" fundstelle="{h.location}">\n{h.text}\n</dokument>'
                           for h in hits)
        return ToolOutput(True, body, summary=f"{len(hits)} Fundstellen", sources=[h.source for h in hits])

    def list_documents() -> ToolOutput:
        docs = knowledge.documents()
        if not docs:
            return ToolOutput(True, "Es sind noch keine Dokumente importiert.", summary="keine Dokumente")
        return ToolOutput(True, "\n".join(f"#{d['id']} {d['name']} ({d['file_type']}, {d['chunk_count']} Abschnitte, "
                                          f"importiert {d['imported_at'][:10]})" for d in docs),
                          summary=f"{len(docs)} Dokumente")

    registry.register(Tool(
        name="import_document",
        description=f"Importiert ein Dokument in die Wissensdatenbank. Unterstützt: {', '.join(SUPPORTED)}.",
        parameters={"type": "object", "properties": {"path": {"type": "string", "description": "Dateipfad"}},
                    "required": ["path"]},
        level=Level.SUGGEST, handler=import_document, level_for=import_level,
        describe_call=lambda a: f"Datei '{a.get('path')}' (außerhalb der freigegebenen Ordner) lesen und importieren",
    ))
    registry.register(Tool(
        name="import_folder",
        description="Importiert alle unterstützten Dateien aus dem Importordner (bereits importierte werden übersprungen).",
        parameters={"type": "object", "properties": {}}, level=Level.SUGGEST, handler=import_folder,
    ))
    registry.register(Tool(
        name="search_documents",
        description="Durchsucht importierte Dokumente und liefert Textstellen mit Fundstelle (Dokument, Seite/Abschnitt).",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        level=Level.READ, handler=search_documents,
    ))
    registry.register(Tool(
        name="list_documents", description="Listet alle importierten Dokumente.",
        parameters={"type": "object", "properties": {}}, level=Level.READ, handler=list_documents,
    ))
