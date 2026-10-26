"""Anbieter-unabhängige Schnittstelle für Sprachmodelle.

Internes Nachrichtenformat (wird von jedem Anbieter umgewandelt):
* {"role": "user", "content": str}
* {"role": "assistant", "content": str, "tool_calls": [ToolCall-dict], "raw": {"provider": name, "data": ...}}
* {"role": "tool", "tool_call_id": str, "name": str, "content": str, "is_error": bool}
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelResponse:
    text: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    external: bool = False
    stop_reason: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Any = None  # anbieterspezifische Antwort zum unveränderten Zurückspielen

    def label(self) -> str:
        where = "extern" if self.external else "lokal"
        return f"{self.provider}/{self.model} ({where})"

    def as_message(self) -> Dict[str, Any]:
        msg: Dict[str, Any] = {"role": "assistant", "content": self.text,
                               "tool_calls": [c.to_dict() for c in self.tool_calls]}
        if self.raw is not None:
            msg["raw"] = {"provider": self.provider, "data": self.raw}
        return msg


class ProviderError(Exception):
    """Anbieter konnte nicht antworten (Netzwerk, Schlüssel, Modell fehlt …)."""


def parse_arguments(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class ModelProvider(ABC):
    name: str = "base"
    external: bool = False

    @abstractmethod
    def status(self) -> Tuple[bool, str]:
        """(verfügbar?, Beschreibung) – darf keine kostenpflichtige Anfrage auslösen."""

    @abstractmethod
    def chat(self, system: str, messages: List[Dict[str, Any]],
             tools: Optional[List[Dict[str, Any]]] = None) -> ModelResponse:
        """Eine Modellantwort erzeugen. Wirft ProviderError bei Problemen."""

    @property
    def model_name(self) -> str:
        return ""
