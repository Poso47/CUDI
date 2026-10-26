"""OpenAI-kompatible Chat-Completions-API (extern). Schlüssel nur über OPENAI_API_KEY."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .base import ModelProvider, ModelResponse, ProviderError, ToolCall, parse_arguments

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class OpenAIProvider(ModelProvider):
    name = "openai"
    external = True

    def __init__(self, api_key: str, model: str, base_url: str, timeout: int = 120, session=None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests

    @property
    def model_name(self) -> str:
        return self.model

    def status(self) -> Tuple[bool, str]:
        if self.session is None:
            return False, "Paket 'requests' fehlt"
        if not self.api_key:
            return False, "kein OPENAI_API_KEY gesetzt"
        if not self.model:
            return False, "kein Modell konfiguriert (openai_model)"
        return True, f"konfiguriert mit Modell {self.model} (externer Dienst)"

    @staticmethod
    def _convert(system: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            elif m["role"] == "assistant":
                msg: Dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                        for c in m["tool_calls"]
                    ]
                out.append(msg)
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    def chat(self, system, messages, tools=None) -> ModelResponse:
        ok, info = self.status()
        if not ok:
            raise ProviderError(info)
        payload: Dict[str, Any] = {"model": self.model, "messages": self._convert(system, messages)}
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        try:
            resp = self.session.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload, timeout=self.timeout,
            )
            if resp.status_code == 401:
                raise ProviderError("OpenAI: API-Schlüssel ungültig (401)")
            if resp.status_code == 429:
                raise ProviderError("OpenAI: Limit erreicht oder Guthaben aufgebraucht (429)")
            resp.raise_for_status()
            data = resp.json()
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"OpenAI-Anfrage fehlgeschlagen: {e}") from e

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {}) or {}
        calls = [
            ToolCall(id=c.get("id", ""), name=c.get("function", {}).get("name", ""),
                     arguments=parse_arguments(c.get("function", {}).get("arguments")))
            for c in message.get("tool_calls") or []
        ]
        usage = data.get("usage") or {}
        return ModelResponse(
            text=message.get("content") or "",
            tool_calls=calls,
            provider=self.name,
            model=data.get("model", self.model),
            external=True,
            stop_reason=choice.get("finish_reason", ""),
            usage={"input_tokens": usage.get("prompt_tokens", 0),
                   "output_tokens": usage.get("completion_tokens", 0)},
        )
