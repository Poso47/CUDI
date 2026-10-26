"""Zentrale Werkzeugregistrierung.

Jedes Werkzeug hat Namen, Beschreibung, Parameter (JSON-Schema), Berechtigungsstufe,
Voraussetzungsprüfung, Fehlerbehandlung und wird protokolliert. Nur hier registrierte
Werkzeuge kann der Orchestrator ausführen.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("cudi.tools")

_TYPE_CHECKS = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


@dataclass
class ToolOutput:
    ok: bool
    content: str            # Ergebnis für das Sprachmodell
    summary: str = ""        # kurze Statuszeile für den Nutzer
    data: Any = None
    sources: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.summary:
            self.summary = self.content if len(self.content) <= 160 else self.content[:157] + "…"


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    level: int
    handler: Callable[..., ToolOutput]
    # Liefert einen Grund, wenn das Werkzeug gerade nicht verfügbar ist
    requires: Optional[Callable[[], Optional[str]]] = None
    # Dynamische Stufe abhängig von den Argumenten (z. B. Pfad außerhalb des Arbeitsordners)
    level_for: Optional[Callable[[Dict[str, Any]], int]] = None
    # Text für die Bestätigungsfrage
    describe_call: Optional[Callable[[Dict[str, Any]], str]] = None

    def effective_level(self, args: Dict[str, Any]) -> int:
        if self.level_for:
            try:
                return max(self.level, int(self.level_for(args)))
            except Exception:  # pragma: no cover - defensiv
                return self.level
        return self.level

    def unavailable_reason(self) -> Optional[str]:
        if not self.requires:
            return None
        try:
            return self.requires()
        except Exception as e:  # pragma: no cover - defensiv
            return f"Prüfung fehlgeschlagen: {e}"

    def spec(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}

    def call_text(self, args: Dict[str, Any]) -> str:
        if self.describe_call:
            try:
                return self.describe_call(args)
            except Exception:  # pragma: no cover - defensiv
                pass
        return f"{self.name}({json.dumps(args, ensure_ascii=False)})"


def call_signature(name: str, args: Dict[str, Any]) -> str:
    raw = name + json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        # Hook nach jeder Ausführung: (tool, args, output, dauer_ms)
        self.on_executed: Optional[Callable[[Tool, Dict[str, Any], ToolOutput, int], None]] = None
        # Liefert Hinweis auf frühere identische Fehlschläge: (signatur) -> Text oder None
        self.previous_failure: Optional[Callable[[str], Optional[str]]] = None

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Werkzeug doppelt registriert: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all(self) -> List[Tool]:
        return list(self._tools.values())

    def availability(self) -> List[Tuple[Tool, Optional[str]]]:
        return [(t, t.unavailable_reason()) for t in self._tools.values()]

    def specs(self) -> List[Dict[str, Any]]:
        """Werkzeugbeschreibungen für das Sprachmodell (nur verfügbare Werkzeuge)."""
        return [t.spec() for t, reason in self.availability() if reason is None]

    @staticmethod
    def normalize(tool: Tool, args: Dict[str, Any]) -> Dict[str, Any]:
        """Modelle senden optionale Felder oft als null und Zahlen manchmal als Text."""
        props = tool.parameters.get("properties", {})
        clean: Dict[str, Any] = {}
        for name, value in args.items():
            if value is None:
                continue
            kind = props.get(name, {}).get("type")
            if kind == "integer" and isinstance(value, str) and value.strip().lstrip("#").isdigit():
                value = int(value.strip().lstrip("#"))
            elif kind == "integer" and isinstance(value, float) and value.is_integer():
                value = int(value)
            clean[name] = value
        return clean

    @staticmethod
    def validate(tool: Tool, args: Dict[str, Any]) -> Optional[str]:
        if not isinstance(args, dict):
            return "Parameter müssen ein Objekt sein"
        props = tool.parameters.get("properties", {})
        for name in tool.parameters.get("required", []):
            if name not in args or args[name] in (None, ""):
                return f"Pflichtparameter fehlt: {name}"
        for name, value in args.items():
            if name not in props:
                return f"Unbekannter Parameter: {name}"
            expected = _TYPE_CHECKS.get(props[name].get("type"))
            if expected and not isinstance(value, expected):
                return f"Parameter '{name}' hat den falschen Typ"
            if isinstance(value, bool) and props[name].get("type") in ("integer", "number"):
                return f"Parameter '{name}' hat den falschen Typ"
        return None

    def execute(self, name: str, args: Optional[Dict[str, Any]] = None) -> ToolOutput:
        args = dict(args or {})
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutput(False, f"Unbekanntes Werkzeug: {name}")
        reason = tool.unavailable_reason()
        if reason:
            output = ToolOutput(False, f"Werkzeug '{name}' ist nicht verfügbar: {reason}")
            self._after(tool, args, output, 0)
            return output
        args = self.normalize(tool, args)
        problem = self.validate(tool, args)
        if problem:
            output = ToolOutput(False, f"Ungültiger Aufruf von '{name}': {problem}")
            self._after(tool, args, output, 0)
            return output

        start = time.perf_counter()
        try:
            output = tool.handler(**args)
            if not isinstance(output, ToolOutput):
                output = ToolOutput(True, str(output))
        except Exception as e:
            log.exception("Werkzeug %s fehlgeschlagen", name)
            output = ToolOutput(False, f"Fehler in '{name}': {type(e).__name__}: {e}")
        duration = int((time.perf_counter() - start) * 1000)

        if not output.ok and self.previous_failure:
            hint = self.previous_failure(call_signature(name, args))
            if hint:
                output.content += f"\nHinweis: {hint}"
        self._after(tool, args, output, duration)
        return output

    def _after(self, tool: Tool, args: Dict[str, Any], output: ToolOutput, duration: int) -> None:
        log.info("Werkzeug %s ok=%s (%d ms): %s", tool.name, output.ok, duration, output.summary)
        if self.on_executed:
            try:
                self.on_executed(tool, args, output, duration)
            except Exception:  # pragma: no cover - Protokollierung darf nie stören
                log.exception("on_executed-Hook fehlgeschlagen")
