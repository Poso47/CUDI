"""Model Manager: kennt alle Anbieter, wählt einen verfügbaren aus, weicht bei Fehlern aus."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .base import ModelProvider, ModelResponse, ProviderError

log = logging.getLogger("cudi.models")


class NoModelAvailable(Exception):
    def __init__(self, reasons: List[Tuple[str, str]]):
        self.reasons = reasons
        super().__init__("; ".join(f"{n}: {r}" for n, r in reasons) or "kein Anbieter konfiguriert")

    def explain(self) -> str:
        lines = ["Ich konnte kein Sprachmodell erreichen:"]
        lines += [f"• {name}: {reason}" for name, reason in self.reasons]
        lines.append(SETUP_HINT)
        return "\n".join(lines)


SETUP_HINT = (
    "So richtest du ein Modell ein (eine Möglichkeit genügt):\n"
    "  1. Lokal & kostenlos: Ollama installieren (https://ollama.com), dann im Terminal `ollama pull llama3.1`.\n"
    "  2. Claude: in der Datei .env die Zeile `ANTHROPIC_API_KEY=...` eintragen und `pip install anthropic`.\n"
    "  3. OpenAI: in der Datei .env die Zeile `OPENAI_API_KEY=...` eintragen.\n"
    "Danach CUDI neu starten oder /modelle eingeben."
)


class ModelManager:
    def __init__(self, providers: Dict[str, ModelProvider], order: List[str],
                 on_call: Optional[Callable[..., None]] = None):
        self.providers = providers
        self.order = [n for n in order if n in providers]
        self.on_call = on_call

    def status(self) -> List[Tuple[str, bool, str]]:
        result = []
        for name in self.order:
            try:
                ok, info = self.providers[name].status()
            except Exception as e:  # pragma: no cover - defensiv
                ok, info = False, f"Statusprüfung fehlgeschlagen: {e}"
            result.append((name, ok, info))
        return result

    def available(self) -> List[ModelProvider]:
        return [self.providers[n] for n, ok, _ in self.status() if ok]

    def has_model(self) -> bool:
        return bool(self.available())

    def chat(self, system: str, messages: List[Dict[str, Any]], tools=None,
             preferred: Optional[str] = None) -> ModelResponse:
        names = self.order[:]
        if preferred in names:
            names.remove(preferred)
            names.insert(0, preferred)
        reasons: List[Tuple[str, str]] = []
        for name in names:
            provider = self.providers[name]
            ok, info = provider.status()
            if not ok:
                reasons.append((name, info))
                continue
            start = time.perf_counter()
            try:
                response = provider.chat(system, messages, tools)
            except ProviderError as e:
                latency = int((time.perf_counter() - start) * 1000)
                log.warning("Anbieter %s fehlgeschlagen: %s", name, e)
                self._record(name, provider.model_name, False, latency, error=str(e))
                reasons.append((name, str(e)))
                continue
            latency = int((time.perf_counter() - start) * 1000)
            self._record(name, response.model, True, latency,
                         response.usage.get("input_tokens"), response.usage.get("output_tokens"))
            return response
        raise NoModelAvailable(reasons)

    def _record(self, *args, **kwargs) -> None:
        if self.on_call:
            try:
                self.on_call(*args, **kwargs)
            except Exception:  # pragma: no cover
                log.exception("Protokollierung des Modellaufrufs fehlgeschlagen")
