"""Absichtserkennung (Deutsch/Englisch).

Regeln erkennen nur eindeutige Anliegen zuverlässig (Befehle, „merke dir“, Feedback, Ja/Nein …).
Alles andere geht an das Sprachmodell, das mit Werkzeugen selbst entscheidet. Ohne Sprachmodell
liefern die Regeln einen ehrlichen, eingeschränkten Ersatz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict

from ..brain.memory import subject_from_question


@dataclass
class Intent:
    kind: str
    data: Dict[str, Any] = field(default_factory=dict)


_I = re.I | re.S


def _m(pattern: str, text: str):
    return re.match(pattern, text, _I)


YES = r"^(ja|jo|jep|jup|yes|yep|ok|okay|klar|gern|gerne|mach( das| es)?|bestätigt|einverstanden|passt|sure)\b[\s.!]*$"
NO = r"^(nein|nö|ne|no|nope|abbrechen|stopp|stop|lieber nicht|auf keinen fall|cancel)\b[\s.!]*$"


def is_yes(text: str) -> bool:
    return bool(_m(YES, text.strip()))


def is_no(text: str) -> bool:
    return bool(_m(NO, text.strip()))


def looks_english(text: str) -> bool:
    words = set(re.findall(r"[a-z']+", text.lower()))
    en = {"the", "you", "can", "what", "is", "my", "hello", "please", "remember", "how", "do", "are", "i"}
    de = {"der", "die", "das", "du", "kannst", "was", "ist", "mein", "hallo", "bitte", "wie", "ich", "und"}
    return len(words & en) > len(words & de)


def route(text: str) -> Intent:
    t = text.strip()

    if t.startswith("/"):
        name, _, arg = t[1:].partition(" ")
        return Intent("command", {"name": name.lower(), "arg": arg.strip()})

    if _m(r"^(?:bitte\s+)?speicher\w*\s+(?:diese|die|das)\s+(erkenntnis|lösung|loesung|entscheidung)", t):
        kind = _m(r"^(?:bitte\s+)?speicher\w*\s+(?:diese|die|das)\s+(\w+)", t).group(1).lower()
        return Intent("save_insight", {"kind": {"lösung": "solution", "loesung": "solution",
                                                "entscheidung": "decision"}.get(kind, "insight")})

    # Nur eindeutige Merk-Aufträge. "Speichere den Code als main.py" ist KEIN Gedächtnis-Auftrag.
    m = _m(r"^(?:bitte\s+)?(?:merke?\s+dir|merk\s+dir|speichere\s+dir|notiere\s+dir|behalte|"
           r"speichere\s+(?:im|in\s+deinem)\s+gedächtnis|speichere(?=\s*,?\s*dass\b)|"
           r"remember(?:\s+that)?|note\s+that)\s*[:,]?\s*(?:bitte\s*)?(?:,\s*)?(?:dass\s+|that\s+)?(.+)$", t)
    if m and len(m.group(1).strip()) > 2:
        return Intent("remember", {"content": m.group(1).strip()})

    m = _m(r"^(?:bitte\s+)?(?:vergiss|lösche\s+(?:die\s+)?erinnerung|forget)\s+(.+)$", t)
    if m:
        return Intent("forget", {"query": m.group(1).strip().rstrip(".!")})

    m = _m(r"^(?:so\s+möchte\s+ich\s+(?:das|es)\s+künftig(?:\s+haben)?|so\s+will\s+ich\s+(?:das|es)\s+künftig(?:\s+haben)?|"
           r"künftig|zukünftig|in\s+zukunft|ab\s+jetzt|ab\s+sofort|von\s+nun\s+an|from\s+now\s+on|in\s+future)"
           r"\s*[:,.!]?\s*(.*)$", t)
    if m:
        return Intent("preference", {"content": m.group(1).strip()})

    m = _m(r"^(?:diese\s+|die\s+|das\s+)?(?:lösung|loesung|ansatz|fix)?\s*hat\s+(nicht\s+)?funktioniert", t)
    if m:
        return Intent("solution_feedback", {"worked": not m.group(1)})

    if len(t.split()) <= 8:
        if _m(r"^(?:nein,?\s+)?(?:das\s+(?:war|ist)\s+(?:falsch|nicht\s+richtig|nicht\s+korrekt|quatsch)|falsch\b|"
              r"stimmt\s+nicht|that'?s\s+wrong|wrong\b)(.*)$", t):
            return Intent("feedback", {"rating": -1, "comment": t})
        if _m(r"^(?:das\s+(?:war|ist)\s+)?(?:richtig|korrekt|genau\s+richtig|perfekt|super|top|gut\s+so|sehr\s+gut|"
              r"that'?s\s+(?:right|correct|perfect)|correct|perfect)\b[\s.!]*$", t):
            return Intent("feedback", {"rating": 1, "comment": t})

    if _m(r"^(?:hilfe|help|was\s+kannst\s+du|what\s+can\s+you\s+do)\b", t):
        return Intent("help")

    subject = subject_from_question(t)
    if subject:
        return Intent("recall", {"subject": subject, "query": t})
    m = _m(r"^(?:was\s+weißt\s+du\s+über|was\s+weisst\s+du\s+über|woran\s+erinnerst\s+du\s+dich\s+zu|"
           r"erinnerst\s+du\s+dich\s+an|what\s+do\s+you\s+know\s+about|do\s+you\s+remember)\s+(.+?)\??$", t)
    if m:
        return Intent("recall", {"subject": None, "query": m.group(1)})

    if len(t.split()) <= 6 and _m(r"^(?:hallo|hi|hey|servus|moin|grüß\s+dich|guten\s+(?:morgen|tag|abend)|"
                                  r"hello|good\s+(?:morning|evening|afternoon))\b", t):
        return Intent("greeting")
    if _m(r"^(?:danke|vielen\s+dank|thx|thanks|thank\s+you)\b", t) and len(t.split()) <= 6:
        return Intent("thanks")
    m = _m(r"^(?:kannst\s+du|könntest\s+du|bist\s+du\s+in\s+der\s+lage(?:\s+zu)?|can\s+you|are\s+you\s+able\s+to)\s+(.+?)\??$", t)
    if m and len(t.split()) <= 6:
        return Intent("capability", {"topic": m.group(1)})
    return Intent("chat")
