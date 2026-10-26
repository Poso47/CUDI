"""Datei-Werkzeuge. Schreiben nur im Arbeitsordner, mit Sicherung vor dem Überschreiben."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..brain.database import copy_file_backup
from ..core.permissions import Level
from .registry import Tool, ToolOutput, ToolRegistry

if TYPE_CHECKING:  # pragma: no cover
    from ..core.application import Application

MAX_READ_BYTES = 200_000

# Dateien, die nie gelesen oder importiert werden (Zugangsdaten)
_SENSITIVE = re.compile(r"(^\.env(\..*)?$|\.pem$|\.key$|\.p12$|\.pfx$|^id_(rsa|dsa|ecdsa|ed25519)|"
                        r"^credentials|^\.netrc$|^\.pypirc$)", re.I)


def is_sensitive(path: Path) -> bool:
    if path.name.lower() == ".env.example":
        return False
    return bool(_SENSITIVE.search(path.name)) or ".git" in path.parts or ".ssh" in path.parts


def _inside(path: Path, roots) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def register(registry: ToolRegistry, app: "Application") -> None:
    s = app.settings

    def resolve_read(path: str) -> Path:
        p = Path(path).expanduser()
        if p.is_absolute():
            return p.resolve()
        in_ws = (s.workspace_dir / p).resolve()
        return in_ws if in_ws.exists() else (s.base_dir / p).resolve()

    def resolve_write(path: str) -> Optional[Path]:
        p = Path(path).expanduser()
        target = (p if p.is_absolute() else s.workspace_dir / p).resolve()
        return target if _inside(target, [s.workspace_dir.resolve()]) else None

    def read_level(args) -> int:
        target = resolve_read(args.get("path", "."))
        return Level.READ if _inside(target, s.read_roots()) else Level.PREPARE

    def list_files(path: str = ".") -> ToolOutput:
        target = resolve_read(path)
        if not target.exists():
            return ToolOutput(False, f"Ordner nicht gefunden: {target}")
        if target.is_file():
            target = target.parent
        entries = []
        for child in sorted(target.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower()))[:200]:
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            entries.append(f"{child.name}/" if child.is_dir() else f"{child.name} ({child.stat().st_size} Bytes)")
        listing = "\n".join(entries) or "(leer)"
        return ToolOutput(True, f"Inhalt von {target}:\n{listing}", summary=f"{len(entries)} Einträge in {target.name or target}")

    def read_file(path: str) -> ToolOutput:
        target = resolve_read(path)
        if is_sensitive(target):
            return ToolOutput(False, f"{target.name} enthält möglicherweise Zugangsdaten und wird aus Sicherheitsgründen nicht gelesen.")
        if not target.is_file():
            return ToolOutput(False, f"Datei nicht gefunden: {target}")
        data = target.read_bytes()[:MAX_READ_BYTES + 1]
        if b"\x00" in data[:4096]:
            return ToolOutput(False, f"{target.name} ist eine Binärdatei und kann nicht als Text gelesen werden.")
        text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        truncated = len(data) > MAX_READ_BYTES
        app.working.note_file(str(target))
        note = f"\n[… gekürzt nach {MAX_READ_BYTES} Bytes]" if truncated else ""
        return ToolOutput(True, f"Inhalt von {target}:\n{text}{note}",
                          summary=f"{target.name} gelesen ({len(text)} Zeichen{', gekürzt' if truncated else ''})")

    def write_file(path: str, content: str) -> ToolOutput:
        target = resolve_write(path)
        if target is None:
            return ToolOutput(False, f"Schreiben ist nur im Arbeitsordner erlaubt ({s.workspace_dir}).")
        backup = None
        if target.exists():
            backup = copy_file_backup(target, s.backup_dir / "dateien")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        app.working.note_file(str(target))
        extra = f" (vorherige Version gesichert: {backup.name})" if backup else ""
        return ToolOutput(True, f"Datei geschrieben: {target}{extra}",
                          summary=f"{target.relative_to(s.workspace_dir)} gespeichert{extra}",
                          data={"path": str(target)})

    def describe_write(args) -> str:
        target = resolve_write(args.get("path", ""))
        if target is None:
            return f"Datei '{args.get('path')}' schreiben (außerhalb des Arbeitsordners – wird abgelehnt)"
        action = "überschreiben (Sicherung wird angelegt)" if target.exists() else "neu anlegen"
        return f"Datei '{target.relative_to(s.workspace_dir)}' im Arbeitsordner {action} ({len(args.get('content', ''))} Zeichen)"

    registry.register(Tool(
        name="list_files",
        description="Listet Dateien und Ordner auf. Relative Pfade beziehen sich auf den Arbeitsordner.",
        parameters={"type": "object", "properties": {
            "path": {"type": "string", "description": "Ordnerpfad, Standard: Arbeitsordner"}}},
        level=Level.READ, handler=list_files, level_for=read_level,
        describe_call=lambda a: f"Ordner '{a.get('path', '.')}' auflisten",
    ))
    registry.register(Tool(
        name="read_file",
        description="Liest eine Textdatei (z. B. Code, Notizen). Relative Pfade: zuerst Arbeitsordner, dann Projektordner.",
        parameters={"type": "object", "properties": {
            "path": {"type": "string", "description": "Dateipfad"}}, "required": ["path"]},
        level=Level.READ, handler=read_file, level_for=read_level,
        describe_call=lambda a: f"Datei '{a.get('path')}' lesen (außerhalb der freigegebenen Ordner)",
    ))
    registry.register(Tool(
        name="write_file",
        description=("Schreibt eine Textdatei in den Arbeitsordner (z. B. erzeugten Code). Bestehende Dateien "
                     "werden vorher gesichert. Nur verwenden, wenn der Nutzer eine Datei haben möchte."),
        parameters={"type": "object", "properties": {
            "path": {"type": "string", "description": "Pfad relativ zum Arbeitsordner, z. B. 'projekt/main.py'"},
            "content": {"type": "string", "description": "Vollständiger Dateiinhalt"}},
            "required": ["path", "content"]},
        level=Level.CHANGE, handler=write_file, describe_call=describe_write,
    ))
