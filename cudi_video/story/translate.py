"""Übersetzung englischer Storys für deutsche Videos (und umgekehrt).

Reihenfolge: Sprachmodell (falls eingerichtet) -> DeepL API Free (kostenloser Schlüssel) ->
MyMemory (ohne Schlüssel, ca. 5.000 Zeichen pro Tag). Ohne Übersetzung bleibt die Originalsprache.
"""

from __future__ import annotations

import json
import os
import re

from .. import config, llm, net

NAMES = {"de": "Deutsch", "en": "Englisch"}


class TranslationUnavailable(RuntimeError):
    pass


class TranslationNeeded(TranslationUnavailable):
    """Auftrag aus der CUDI-App: Claude übersetzt selbst (besser als der Gratis-Dienst, ohne Schlüssel)."""

    def __init__(self, texts: list[str], target: str, source: str):
        super().__init__(f"{len(texts)} Texte für Claude zum Übersetzen nach {NAMES[target]}")
        self.texts, self.target, self.source = texts, target, source


# Im Auftragsmodus (CUDI-App) zeigt diese Variable auf die Übersetzungsdatei der Auftrags-Sitzung:
# {"texte": [...], "uebersetzt": [...]} – fehlt sie oder ein Text, wird TranslationNeeded geworfen.
CLAUDE_FILE_ENV = "CUDI_CLAUDE_UEBERSETZUNG"


def _from_claude(texts: list[str]) -> list[str] | None:
    path = os.environ.get(CLAUDE_FILE_ENV)
    if not path or not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path, encoding="utf-8").read())
        pairs = dict(zip(data.get("texte", []), data.get("uebersetzt", [])))
    except (OSError, ValueError, AttributeError):
        return None
    if len(data.get("uebersetzt", [])) != len(data.get("texte", [])):
        return None
    out = [pairs.get(t) for t in texts]
    return [str(t) for t in out] if all(isinstance(t, str) and t.strip() for t in out) else None


def _llm(texts: list[str], target: str) -> list[str]:
    system = (f"Übersetze jeden Text der JSON-Liste ins {NAMES[target]}e – natürlich und gut vorlesbar, "
              "ohne etwas hinzuzufügen oder wegzulassen. Antworte NUR mit einer JSON-Liste gleicher Länge.")
    answer = llm.chat(system, json.dumps(texts, ensure_ascii=False), temperature=0.2)
    match = re.search(r"\[.*\]", answer, re.S)
    out = json.loads(match.group(0)) if match else []
    if len(out) != len(texts):
        raise ValueError("Übersetzung unvollständig")
    return [str(t) for t in out]


def _deepl(texts: list[str], target: str, source: str) -> list[str]:
    host = "api-free.deepl.com" if config.DEEPL_API_KEY.endswith(":fx") else "api.deepl.com"
    resp = net._session.post(f"https://{host}/v2/translate", timeout=60,
                             headers={"Authorization": f"DeepL-Auth-Key {config.DEEPL_API_KEY}"},
                             data=[("text", t) for t in texts] + [("target_lang", target.upper()),
                                                                  ("source_lang", source.upper())])
    if not resp.ok:
        raise net.FetchError(f"DeepL: HTTP {resp.status_code}")
    return [t["text"] for t in resp.json()["translations"]]


def _chunks(text: str, size: int = 450) -> list[str]:
    """MyMemory nimmt höchstens ~500 Zeichen pro Anfrage – an Satzgrenzen teilen."""
    parts, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if current and len(current) + len(sentence) + 1 > size:
            parts.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    return [*parts, current] if current else parts


def _mymemory(texts: list[str], target: str, source: str) -> list[str]:
    out = []
    for text in texts:
        pieces = []
        for chunk in _chunks(text):
            data = net.get_json("https://api.mymemory.translated.net/get", params={"q": chunk, "langpair": f"{source}|{target}"},
                                cache_hours=24 * 30, retries=1, max_wait=10)
            translated = data.get("responseData", {}).get("translatedText", "")
            if data.get("responseStatus") != 200 or translated.startswith("MYMEMORY WARNING"):
                raise net.FetchError("MyMemory: Tageskontingent aufgebraucht")
            pieces.append(translated)
        out.append(" ".join(pieces))
    return out


def translate(texts: list[str], target: str, source: str = "en") -> tuple[list[str], str]:
    """Gibt (Übersetzungen, Dienst) zurück oder wirft TranslationUnavailable."""
    if target == source:
        return list(texts), "keine Übersetzung nötig"
    claude_mode = bool(os.environ.get(CLAUDE_FILE_ENV))
    if claude_mode:
        done = _from_claude(texts)
        if done is not None:
            return done, "Claude"
    attempts = []
    if llm.available():
        attempts.append(("Sprachmodell", lambda: _llm(texts, target)))
    if config.DEEPL_API_KEY:
        attempts.append(("DeepL", lambda: _deepl(texts, target, source)))
    if not claude_mode:                        # im Auftragsmodus übersetzt Claude statt des Gratis-Dienstes
        attempts.append(("MyMemory", lambda: _mymemory(texts, target, source)))
    errors = []
    for name, run in attempts:
        try:
            return run(), name
        except Exception as exc:               # nächster Dienst
            errors.append(f"{name}: {exc}")
    if claude_mode:
        raise TranslationNeeded(list(texts), target, source)
    raise TranslationUnavailable(
        f"Übersetzung nach {NAMES[target]} nicht möglich ({'; '.join(errors)}). Lösung: kostenlosen "
        "Gemini-Schlüssel (CUDI_LLM_*) oder DeepL-Free-Schlüssel (CUDI_DEEPL_API_KEY) eintragen – oder eine "
        "Story in Videosprache wählen.")
