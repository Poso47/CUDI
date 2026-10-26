"""Berechtigungsstufen für Werkzeuge.

1 Lesen/Analysieren · 2 Vorschläge erstellen · 3 Änderungen vorbereiten
4 lokale Änderungen ausführen · 5 externe oder irreversible Aktionen
"""

from __future__ import annotations

from enum import IntEnum
from typing import Set


class Level(IntEnum):
    READ = 1
    SUGGEST = 2
    PREPARE = 3
    CHANGE = 4
    EXTERNAL = 5


LEVEL_LABELS = {
    Level.READ: "Lesen/Analysieren",
    Level.SUGGEST: "Vorschlag erstellen",
    Level.PREPARE: "Änderung vorbereiten",
    Level.CHANGE: "Lokale Änderung",
    Level.EXTERNAL: "Externe/irreversible Aktion",
}


class PermissionManager:
    def __init__(self, auto_approve_level: int = 2):
        self.auto_approve_level = min(int(auto_approve_level), int(Level.CHANGE))
        self._session_grants: Set[str] = set()

    def needs_confirmation(self, tool_name: str, level: int) -> bool:
        if level >= Level.EXTERNAL:
            return True  # niemals automatisch
        if level <= self.auto_approve_level:
            return False
        return tool_name not in self._session_grants

    def grant_for_session(self, tool_name: str) -> None:
        self._session_grants.add(tool_name)

    def revoke_all(self) -> None:
        self._session_grants.clear()

    @property
    def session_grants(self) -> Set[str]:
        return set(self._session_grants)
