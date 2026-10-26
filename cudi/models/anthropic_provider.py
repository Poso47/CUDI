"""Claude über die offizielle Anthropic-SDK (extern). Schlüssel nur über ANTHROPIC_API_KEY.

Standardmodell: claude-opus-5-5 (Aufwand/effort konfigurierbar, Standard 'medium').
Bei einer Ablehnung durch Sicherheitsfilter springt die API über
``fallbacks="default"`` serverseitig auf ein passendes Ersatzmodell.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Tuple

from .base import ModelProvider, ModelResponse, ProviderError, ToolCall, parse_arguments

log = logging.getLogger("cudi.models.anthropic")

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _block_to_dict(block: Any) -> Dict[str, Any]:
    if isinstance(block, dict):
        return block
    for attr in ("to_dict", "model_dump"):
        fn = getattr(block, attr, None)
        if callable(fn):
            return fn()
    return dict(vars(block))


def _get(block: Any, key: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


class AnthropicProvider(ModelProvider):
    name = "anthropic"
    external = True

    def __init__(self, api_key: str, model: str, effort: str = "medium", timeout: int = 120, client=None):
        self.api_key = api_key
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self._client = client
        self._use_fallbacks = True

    @property
    def model_name(self) -> str:
        return self.model

    def _sdk(self):
        try:
            import anthropic
            return anthropic
        except ImportError:
            return None

    def status(self) -> Tuple[bool, str]:
        if self._client is not None:
            return True, f"konfiguriert mit Modell {self.model} (externer Dienst)"
        if self._sdk() is None:
            return False, "Paket 'anthropic' fehlt (pip install anthropic)"
        if not (self.api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            return False, "kein ANTHROPIC_API_KEY gesetzt"
        return True, f"konfiguriert mit Modell {self.model} (externer Dienst)"

    def client(self):
        if self._client is None:
            sdk = self._sdk()
            if sdk is None:
                raise ProviderError("Paket 'anthropic' fehlt (pip install anthropic)")
            kwargs = {"timeout": float(self.timeout)}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = sdk.Anthropic(**kwargs)
        return self._client

    # ---------------------------------------------------------- Umwandlung
    @staticmethod
    def convert(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for m in messages:
            role = m["role"]
            if role == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if m.get("is_error"):
                    block["is_error"] = True
                # Alle Ergebnisse einer Runde gehören in EINE Nutzer-Nachricht
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) \
                        and all(b.get("type") == "tool_result" for b in out[-1]["content"]):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            elif role == "assistant":
                raw = m.get("raw") or {}
                if raw.get("provider") == "anthropic" and raw.get("data"):
                    # Antwortblöcke (inkl. thinking/fallback) unverändert zurückgeben
                    out.append({"role": "assistant", "content": raw["data"]})
                    continue
                blocks: List[Dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for c in m.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]})
                if blocks:
                    out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    # --------------------------------------------------------------- Anfrage
    def chat(self, system, messages, tools=None) -> ModelResponse:
        ok, info = self.status()
        if not ok:
            raise ProviderError(info)
        params: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 16000,
            "system": system,
            "messages": self.convert(messages),
            "output_config": {"effort": self.effort},
        }
        if tools:
            params["tools"] = [
                {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                for t in tools
            ]
        response = self._request(params)

        if _get(response, "stop_reason") == "refusal":
            return ModelResponse(
                text="Diese Anfrage wurde vom Modell aus Sicherheitsgründen abgelehnt.",
                provider=self.name, model=self.model, external=True, stop_reason="refusal",
            )

        content = list(_get(response, "content", []) or [])
        texts, calls = [], []
        for block in content:
            kind = _get(block, "type")
            if kind == "text":
                texts.append(_get(block, "text", ""))
            elif kind == "tool_use":
                calls.append(ToolCall(id=_get(block, "id"), name=_get(block, "name"),
                                      arguments=parse_arguments(_get(block, "input"))))
        usage = _get(response, "usage")
        text = "\n".join(t for t in texts if t)
        if _get(response, "stop_reason") == "max_tokens":
            text += "\n\n(Hinweis: Die Antwort wurde wegen der Längenbegrenzung abgeschnitten.)"
        return ModelResponse(
            text=text,
            tool_calls=calls,
            provider=self.name,
            model=_get(response, "model", self.model) or self.model,
            external=True,
            stop_reason=_get(response, "stop_reason", "") or "",
            usage={"input_tokens": _get(usage, "input_tokens", 0) or 0,
                   "output_tokens": _get(usage, "output_tokens", 0) or 0},
            raw=[_block_to_dict(b) for b in content],
        )

    def _request(self, params: Dict[str, Any]):
        client = self.client()
        sdk = self._sdk()
        try:
            if self._use_fallbacks:
                try:
                    return client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
                except TypeError:
                    # Ältere SDK-Version ohne 'fallbacks' – ohne Ersatzmodell weiter
                    log.warning("Installierte anthropic-SDK kennt 'fallbacks' nicht – bitte aktualisieren")
                    self._use_fallbacks = False
            return client.messages.create(**params)
        except Exception as e:
            raise ProviderError(self._explain(e, sdk)) from e

    @staticmethod
    def _explain(error: Exception, sdk) -> str:
        if sdk is not None:
            if isinstance(error, getattr(sdk, "AuthenticationError", ())):
                return "Anthropic: API-Schlüssel ungültig"
            if isinstance(error, getattr(sdk, "PermissionDeniedError", ())):
                return "Anthropic: Schlüssel hat keine Berechtigung für dieses Modell"
            if isinstance(error, getattr(sdk, "NotFoundError", ())):
                return "Anthropic: Modell nicht gefunden – Modellnamen in den Einstellungen prüfen"
            if isinstance(error, getattr(sdk, "RateLimitError", ())):
                return "Anthropic: Anfragelimit erreicht – bitte später erneut versuchen"
            if isinstance(error, getattr(sdk, "APIStatusError", ())):
                return f"Anthropic: Fehler {getattr(error, 'status_code', '?')}: {getattr(error, 'message', error)}"
            if isinstance(error, getattr(sdk, "APIConnectionError", ())):
                return "Anthropic: keine Verbindung (Internet prüfen)"
        return f"Anthropic-Anfrage fehlgeschlagen: {type(error).__name__}: {error}"
