"""Optionaler Zugriff auf ein Sprachmodell über eine OpenAI-kompatible Schnittstelle.

Kostenlose Varianten (Stand 2026, Limits können sich ändern):
  Google Gemini:  CUDI_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
  Groq:           CUDI_LLM_BASE_URL=https://api.groq.com/openai/v1
  Zweiter/dritter Anbieter als Ausweichweg: CUDI_LLM2_* / CUDI_LLM3_* (BASE_URL, API_KEY, MODEL), z. B. Groq oder OpenRouter.
  Ollama (lokal): CUDI_LLM_BASE_URL=http://localhost:11434/v1   (kein Schlüssel nötig)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import requests

from . import config

log = logging.getLogger(__name__)


PAUSE = 8                      # Sekunden Pause vor dem nächsten Versuch nach 429/5xx
RETRIES = 2                    # Versuche je Anbieter (bei Limit/Störung)


def providers() -> list[tuple[str, str, str]]:
    """Ausweichkette freier Sprachmodelle: CUDI_LLM_* zuerst, danach CUDI_LLM2_*, CUDI_LLM3_* (nur gesetzte).
    Rückgabe: [(Basis-URL, Schlüssel, Modell)]. Zwei kostenlose Anbieter siehe docs/notbetrieb-einrichten.md."""
    out = []
    for prefix in ("CUDI_LLM", "CUDI_LLM2", "CUDI_LLM3"):
        if prefix == "CUDI_LLM":
            url, key, model = config.LLM_BASE_URL, config.LLM_API_KEY, config.LLM_MODEL
        else:
            url, key, model = (os.environ.get(f"{prefix}_{n}", "") for n in ("BASE_URL", "API_KEY", "MODEL"))
        if url and model:
            out.append((url, key, model))
    return out


def available() -> bool:
    return bool(providers())


def _post(url: str, key: str, model: str, system: str, user: str, temperature: float, timeout: int) -> str:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    resp = requests.post(
        url.rstrip("/") + "/chat/completions",
        headers=headers,
        json={
            "model": model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def chat(system: str, user: str, temperature: float = 0.4, timeout: int = 120) -> str:
    """Antwort des ersten Anbieters, der antwortet. Bei 429/5xx/Netzfehler kurze Pause und ein zweiter Versuch,
    dann der nächste Anbieter der Kette. Scheitern alle, wird der letzte Fehler geworfen (Aufrufer: Textbausteine)."""
    chain = providers()
    if not chain:
        raise RuntimeError("Kein Sprachmodell konfiguriert.")
    last: Exception | None = None
    for index, (url, key, model) in enumerate(chain):
        for attempt in range(RETRIES):
            try:
                return _post(url, key, model, system, user, temperature, timeout)
            except requests.HTTPError as exc:
                last = exc
                status = exc.response.status_code if exc.response is not None else 0
                if status not in (408, 425, 429, 500, 502, 503, 504):
                    break                                   # z. B. 401/404: Wiederholen hilft nicht, nächster Anbieter
            except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
                last = exc
            if attempt + 1 < RETRIES:
                time.sleep(PAUSE)
        log.warning("Sprachmodell %d/%d (%s) ohne Antwort: %s", index + 1, len(chain), model, str(last)[:160])
    raise last  # type: ignore[misc]


def chat_json(system: str, user: str, **kw) -> dict:
    text = chat(system, user, **kw)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"Keine JSON-Antwort: {text[:200]}")
    return json.loads(match.group(0))
