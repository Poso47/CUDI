"""Optionaler Zugriff auf ein Sprachmodell über eine OpenAI-kompatible Schnittstelle.

Kostenlose Varianten (Stand 2026, Limits können sich ändern):
  Google Gemini:  CUDI_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
  Groq:           CUDI_LLM_BASE_URL=https://api.groq.com/openai/v1
  Ollama (lokal): CUDI_LLM_BASE_URL=http://localhost:11434/v1   (kein Schlüssel nötig)
"""

from __future__ import annotations

import json
import re

import requests

from . import config


def available() -> bool:
    return bool(config.LLM_BASE_URL and config.LLM_MODEL)


def chat(system: str, user: str, temperature: float = 0.4, timeout: int = 120) -> str:
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    resp = requests.post(
        config.LLM_BASE_URL.rstrip("/") + "/chat/completions",
        headers=headers,
        json={
            "model": config.LLM_MODEL,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def chat_json(system: str, user: str, **kw) -> dict:
    text = chat(system, user, **kw)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"Keine JSON-Antwort: {text[:200]}")
    return json.loads(match.group(0))
