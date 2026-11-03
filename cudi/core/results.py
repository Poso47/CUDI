"""Einheitliche Ergebnisobjekte, die der Orchestrator an GUI/CLI zurückgibt."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Arten von Ergebnissen
ANSWER = "answer"          # normale Antwort
QUESTION = "question"      # CUDI braucht eine Angabe/Entscheidung des Nutzers
CONFIRM = "confirm"        # eine Aktion wartet auf Bestätigung (pending_id gesetzt)
ERROR = "error"            # Aufgabe konnte nicht ausgeführt werden


@dataclass
class Action:
    """Eine tatsächlich ausgeführte (oder abgelehnte) Werkzeug-Aktion."""

    tool: str
    ok: bool
    summary: str
    status: str = "ausgeführt"  # ausgeführt | fehlgeschlagen | abgelehnt

    def line(self) -> str:
        icon = {"ausgeführt": "✅", "fehlgeschlagen": "❌", "abgelehnt": "⛔"}.get(self.status, "•")
        return f"{icon} {self.tool}: {self.summary}"


@dataclass
class Result:
    kind: str
    text: str
    actions: List[Action] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    model: Optional[str] = None
    pending_id: Optional[str] = None
    details: Optional[str] = None  # technische Details (auf Wunsch anzeigbar)

    @property
    def ok(self) -> bool:
        return self.kind != ERROR

    def render(self, with_actions: bool = True) -> str:
        """Text für Chat-Anzeige: Antwort + tatsächlicher Aktionsstatus + Quellen."""
        parts = [self.text.strip()]
        if with_actions and self.actions:
            # Erfolgreiche Aktionen, deren Ergebnis schon im Text steht, nicht doppelt zeigen;
            # Fehler und Ablehnungen immer zeigen.
            lines = [a.line() for a in self.actions
                     if a.status != "ausgeführt" or a.summary.strip() not in self.text]
            if lines:
                parts.append("\n".join(lines))
        if self.sources:
            parts.append("Quellen: " + "; ".join(dict.fromkeys(self.sources)))
        return "\n\n".join(p for p in parts if p)
