"""Werkzeuge für das Gedächtnis: merken, suchen, korrigieren, vergessen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..brain.memory import CATEGORIES
from ..core.permissions import Level
from .registry import Tool, ToolOutput, ToolRegistry

if TYPE_CHECKING:  # pragma: no cover
    from ..core.application import Application


def register(registry: ToolRegistry, app: "Application") -> None:
    memory = app.memory

    def remember(content: str, category: str = "fact", subject: Optional[str] = None) -> ToolOutput:
        project = app.projects.active()
        result = memory.add(content, source="nutzer (Chat)", category=category, subject=subject,
                            project_id=project["id"] if project else None)
        if result.status == "duplicate":
            return ToolOutput(True, f"Bereits gespeichert als #{result.memory.id}: {result.memory.content}",
                              summary=f"schon bekannt (#{result.memory.id})")
        if result.status == "conflict":
            olds = "; ".join(f"#{m.id} „{m.content}“" for m in result.conflicts)
            return ToolOutput(
                False,
                f"Widerspruch zu bestehender Erinnerung: {olds}. Nichts gespeichert. Frage den Nutzer, ob die "
                f"neue Angabe die alte ersetzen soll; falls ja, nutze replace_memory.",
                summary=f"Widerspruch zu {olds} – Rückfrage nötig",
                data={"conflicts": [m.id for m in result.conflicts]},
            )
        return ToolOutput(True, f"Gespeichert als #{result.memory.id}: {result.memory.content}",
                          summary=f"gemerkt (#{result.memory.id}): {result.memory.content}")

    def search_memory(query: str) -> ToolOutput:
        hits = memory.search(query, limit=10)
        if not hits:
            return ToolOutput(True, f"Keine Erinnerungen zu „{query}“ gefunden.", summary="nichts gefunden")
        memory.touch(hits)
        return ToolOutput(True, "\n".join(m.line() for m in hits), summary=f"{len(hits)} Treffer")

    def replace_memory(memory_id: int, content: str) -> ToolOutput:
        new = memory.correct(memory_id, content, source="nutzer (Korrektur)")
        if not new:
            return ToolOutput(False, f"Erinnerung #{memory_id} gibt es nicht.")
        return ToolOutput(True, f"#{memory_id} ersetzt durch #{new.id}: {new.content}",
                          summary=f"#{memory_id} → #{new.id}: {new.content}")

    def forget_memory(memory_id: int) -> ToolOutput:
        old = memory.get(memory_id)
        if not old:
            return ToolOutput(False, f"Erinnerung #{memory_id} gibt es nicht.")
        memory.forget(memory_id)
        return ToolOutput(True, f"Erinnerung #{memory_id} gelöscht: {old.content}", summary=f"#{memory_id} gelöscht")

    registry.register(Tool(
        name="remember",
        description=("Speichert eine Information dauerhaft im Gedächtnis. Nur verwenden, wenn der Nutzer etwas "
                     "behalten/merken lassen möchte oder eine dauerhafte Vorliebe äußert. Formuliere als Aussage "
                     "über den Nutzer, z. B. 'Mein Lieblingseditor ist VS Code'."),
        parameters={"type": "object", "properties": {
            "content": {"type": "string", "description": "Die Information als vollständiger Satz"},
            "category": {"type": "string", "enum": list(CATEGORIES), "description": "Art der Information"},
            "subject": {"type": "string", "description": "Kurzes Thema zur Widerspruchserkennung, z. B. 'lieblingseditor'"}},
            "required": ["content"]},
        level=Level.SUGGEST, handler=remember,
    ))
    registry.register(Tool(
        name="search_memory",
        description="Durchsucht das Langzeitgedächtnis nach gespeicherten Informationen.",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        level=Level.READ, handler=search_memory,
    ))
    registry.register(Tool(
        name="replace_memory",
        description="Ersetzt eine gespeicherte Erinnerung (z. B. nach einer Korrektur durch den Nutzer). Die alte wird als veraltet markiert.",
        parameters={"type": "object", "properties": {
            "memory_id": {"type": "integer"}, "content": {"type": "string"}}, "required": ["memory_id", "content"]},
        level=Level.SUGGEST, handler=replace_memory,
    ))
    registry.register(Tool(
        name="forget_memory",
        description="Löscht eine Erinnerung endgültig. Nur auf ausdrücklichen Wunsch des Nutzers.",
        parameters={"type": "object", "properties": {"memory_id": {"type": "integer"}}, "required": ["memory_id"]},
        level=Level.CHANGE, handler=forget_memory,
        describe_call=lambda a: f"Erinnerung #{a.get('memory_id')} endgültig löschen",
    ))
