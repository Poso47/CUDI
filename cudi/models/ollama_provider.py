"""Lokale Sprachmodelle über Ollama (http://localhost:11434). Daten bleiben auf dem Rechner."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .base import ModelProvider, ModelResponse, ProviderError, ToolCall, parse_arguments

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class OllamaProvider(ModelProvider):
    name = "ollama"
    external = False

    def __init__(self, host: str, model: str, timeout: int = 120, session=None):
        self.host = host.rstrip("/")
        self.configured_model = model
        self.timeout = timeout
        self.session = session or requests
        self._resolved_model: Optional[str] = None
        self._status_cache: Optional[Tuple[float, Tuple[bool, str]]] = None
        self._tools_unsupported = False

    @property
    def model_name(self) -> str:
        return self._resolved_model or self.configured_model

    def status(self) -> Tuple[bool, str]:
        if self._status_cache and time.time() - self._status_cache[0] < 30:
            return self._status_cache[1]
        result = self._check()
        self._status_cache = (time.time(), result)
        return result

    def _check(self) -> Tuple[bool, str]:
        if self.session is None:
            return False, "Paket 'requests' fehlt"
        try:
            resp = self.session.get(f"{self.host}/api/tags", timeout=2)
            resp.raise_for_status()
            names = [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception:
            return False, f"Ollama nicht erreichbar unter {self.host} (läuft Ollama? https://ollama.com)"
        if not names:
            return False, f"Ollama läuft, aber kein Modell installiert – im Terminal: ollama pull {self.configured_model}"
        wanted = self.configured_model
        for n in names:
            if n == wanted or n.split(":")[0] == wanted or n == f"{wanted}:latest":
                self._resolved_model = n
                return True, f"Ollama bereit mit Modell {n}"
        self._resolved_model = names[0]
        return True, (f"Modell '{wanted}' nicht installiert – verwende stattdessen '{names[0]}' "
                      f"(installieren mit: ollama pull {wanted})")

    def _convert(self, system: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "tool":
                out.append({"role": "tool", "content": m["content"], "tool_name": m.get("name", "")})
            elif m["role"] == "assistant":
                msg: Dict[str, Any] = {"role": "assistant", "content": m.get("content", "")}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {"function": {"name": c["name"], "arguments": c["arguments"]}} for c in m["tool_calls"]
                    ]
                out.append(msg)
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    def chat(self, system, messages, tools=None) -> ModelResponse:
        ok, info = self.status()
        if not ok:
            raise ProviderError(info)
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": self._convert(system, messages),
            "stream": False,
        }
        if tools and not self._tools_unsupported:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        try:
            resp = self.session.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            if resp.status_code == 400 and "tools" in payload and "support" in resp.text.lower():
                # Modell kann keine Werkzeuge – ohne Werkzeuge erneut fragen
                self._tools_unsupported = True
                payload.pop("tools")
                resp = self.session.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except ProviderError:
            raise
        except Exception as e:
            self._status_cache = None
            raise ProviderError(f"Ollama-Anfrage fehlgeschlagen: {e}") from e

        message = data.get("message", {}) or {}
        calls = [
            ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=c.get("function", {}).get("name", ""),
                     arguments=parse_arguments(c.get("function", {}).get("arguments")))
            for c in message.get("tool_calls") or []
        ]
        return ModelResponse(
            text=message.get("content", "") or "",
            tool_calls=calls,
            provider=self.name,
            model=self.model_name,
            external=False,
            stop_reason=data.get("done_reason", ""),
            usage={"input_tokens": data.get("prompt_eval_count") or 0,
                   "output_tokens": data.get("eval_count") or 0},
        )
