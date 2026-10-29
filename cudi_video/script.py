"""Sprechertext aus den recherchierten Daten erzeugen – ohne etwas hinzuzuerfinden.

Grundregel: Zahlen kommen ausschließlich aus Wikidata. Wikipedia-Sätze werden nur
wörtlich übernommen und nur, wenn sie keine (möglicherweise widersprüchlichen) Zahlen
enthalten. Ein optionales Sprachmodell darf umformulieren, sein Text wird aber geprüft
und bei Zweifeln durch die Textbausteine ersetzt.
"""

from __future__ import annotations

import json
import logging
import re

from . import llm
from .models import RankItem, Research, Script, Segment
from .spec import VideoSpec
from .units import quantity

log = logging.getLogger(__name__)

WORDS_PER_SECOND = 2.1   # gemessen: edge-tts bei +8 % Tempo inkl. Satzpausen
MAX_SUMMARY_SENTENCES = 2
MAX_SENTENCE_WORDS = 28

PROPERTY_LABELS = {
    "P17": ({"de": "Land", "en": "Country"}, {"de": "Länder", "en": "Countries"}),
    "P36": ({"de": "Hauptstadt", "en": "Capital"}, None),
    "P30": ({"de": "Kontinent", "en": "Continent"}, {"de": "Kontinente", "en": "Continents"}),
    "P1619": ({"de": "Eröffnet", "en": "Opened"}, None),
    "P571": ({"de": "Gegründet", "en": "Founded"}, None),
    "P4552": ({"de": "Gebirge", "en": "Mountain range"}, None),
    "P403": ({"de": "Mündung", "en": "Mouth"}, None),
    "P131": ({"de": "Ort", "en": "Location"}, None),
    "P1101": ({"de": "Stockwerke", "en": "Floors"}, None),
    "P84": ({"de": "Architekt", "en": "Architect"}, {"de": "Architekten", "en": "Architects"}),
    "P1082": ({"de": "Einwohner", "en": "Population"}, None),
    "P2046": ({"de": "Fläche (km²)", "en": "Area (km²)"}, None),
    "P885": ({"de": "Ursprung", "en": "Origin"}, None),
    "P205": ({"de": "Anrainerstaaten", "en": "Basin countries"}, None),
    "P2044": ({"de": "Höhe (m)", "en": "Elevation (m)"}, None),
}

TEXT = {
    "de": {
        "intro": "{title}! Platz eins kommt auf {top} – aber wer ist es? Bleib bis zum Ende!",
        "rank": "Platz {n}: {name}.",
        "value": "{label}: {value}.",
        "as_of": "Stand {year}.",
        "and": "und",
        "outro": (
            "Das war unser Ranking. Alle Zahlen stammen aus Wikidata, abgerufen am {date}. "
            "Welcher Platz hat dich überrascht? Schreib es in die Kommentare und folge für mehr Rankings!"
        ),
    },
    "en": {
        "intro": "{title}! Number one reaches {top} – but which one is it? Stay until the end!",
        "rank": "Number {n}: {name}.",
        "value": "{label}: {value}.",
        "as_of": "As of {year}.",
        "and": "and",
        "outro": (
            "That was our ranking. All figures come from Wikidata, retrieved on {date}. "
            "Which spot surprised you? Tell us in the comments and follow for more rankings!"
        ),
    },
}


# --------------------------------------------------------------------------- Hilfsfunktionen

def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s*\([^()]*\)", "", text)          # Klammern (Aussprache, Lebensdaten …) entfernen
    text = re.sub(r"\s*\([^()]*\)", "", text)          # verschachtelte Klammern
    text = re.sub(r"\s+", " ", text).strip()
    # Nicht trennen nach Ordnungszahlen ("28. August") und Abkürzungen ("z. B.", "St.").
    parts = re.split(r"(?<![0-9]\.)(?<!\b[A-Za-z]\.)(?<!\bSt\.)(?<!\bNr\.)(?<!\bbzw\.)(?<!\bca\.)(?<!\bCo\.)(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"])", text)
    return [p.strip() for p in parts if p.strip()]


# Eigene Rang-/Superlativ-Aussagen oder zeitabhängige Aussagen aus Wikipedia können der
# Rangfolge in unseren Daten widersprechen oder veralten -> solche Sätze nicht verwenden.
RISKY_WORDS = re.compile(
    r"(höchst|größt|grösst|längst|tiefst|schwerst|schnellst|best|zweit|dritt|viert|fünft|sechst|siebt|acht|neunt|zehnt|elft|zwölft"
    r"|tallest|highest|largest|biggest|longest|deepest|heaviest|fastest|second|third|fourth|fifth|sixth|seventh"
    r"|eighth|ninth|tenth|eleventh|twelfth|\d+(st|nd|rd|th)\b"
    r"|derzeit|aktuell|zurzeit|momentan|\bstand\b|bislang|bisher|currently|as of|to date|at present|so far)",
    re.I,
)


def has_risky_claims(sentence: str) -> bool:
    return bool(RISKY_WORDS.search(sentence)) or has_risky_numbers(sentence)


def has_risky_numbers(sentence: str) -> bool:
    """Zahlen außer Jahreszahlen könnten den Wikidata-Werten widersprechen -> Satz nicht verwenden."""
    for num in re.findall(r"\d[\d.,]*", sentence):
        digits = num.rstrip(".,")
        if not re.fullmatch(r"1\d{3}|20\d{2}", digits):
            return True
    return False


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 2}


def _similar(a: str, b: str, threshold: float = 0.6) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / min(len(ta), len(tb)) >= threshold


def usable_description(item: RankItem, lang: str) -> str:
    desc = item.descriptions.get(lang, "")
    return "" if has_risky_numbers(desc) else desc


def usable_summary_sentences(item: RankItem, lang: str) -> list[str]:
    out: list[str] = []
    desc = usable_description(item, lang)
    for s in _sentences(item.summary.get(lang, "")):
        if has_risky_claims(s) or len(s.split()) > MAX_SENTENCE_WORDS or len(s) < 20 or not s[0].isupper():
            continue
        if (desc and _similar(s, desc)) or any(_similar(s, o) for o in out):
            continue   # nichts doppelt sagen
        out.append(s)
    return out


def _join(values: str, lang: str) -> str:
    parts = [p for p in values.split(" / ") if p != "…"]
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return ", ".join(parts[:-1]) + f" {TEXT[lang]['and']} " + parts[-1]


def extras_lines(spec: VideoSpec, item: RankItem, lang: str) -> list[tuple[str, str]]:
    """(Label, Wert)-Paare, z. B. ("Land", "China / Nepal")."""
    lines = []
    desc = item.descriptions.get(lang, "")
    for key, pid in spec.source.extras.items():
        value = item.extras.get(key, {}).get(lang)
        if not value or (" / " not in value and value in desc):
            continue   # fehlt oder steht schon in der Beschreibung
        singular, plural = PROPERTY_LABELS.get(pid, ({"de": key.title(), "en": key.title()}, None))
        label = (plural or singular)[lang] if " / " in value else singular[lang]
        lines.append((label, value))
    return lines


def _capitalize(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def item_facts(spec: VideoSpec, item: RankItem, lang: str) -> dict:
    q = quantity(item.value, item.unit, spec.unit)
    return {
        "rank": item.rank,
        "name": item.labels[lang],
        "description": usable_description(item, lang),
        "value_label": spec.value_label.get(lang, ""),
        "value_spoken": q.spoken(lang),
        "value_display": q.display(lang),
        "as_of": item.value_date[:4] if item.value_date else None,
        "extras": extras_lines(spec, item, lang),
        "summary_sentences": usable_summary_sentences(item, lang),
    }


MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]


def format_date(iso: str, lang: str) -> str:
    y, m, d = iso.split("-")
    if lang == "de":
        return f"{d}.{m}.{y}"
    return f"{MONTHS_EN[int(m) - 1]} {int(d)}, {y}"


# --------------------------------------------------------------------------- Textbausteine

def template_item_text(facts: dict, lang: str, word_budget: int) -> str:
    t = TEXT[lang]
    parts = [t["rank"].format(n=facts["rank"], name=facts["name"])]
    if facts["description"]:
        parts.append(_capitalize(facts["description"]).rstrip(".") + ".")
    if facts["value_label"]:
        parts.append(t["value"].format(label=facts["value_label"], value=facts["value_spoken"]))
    else:
        parts.append(_capitalize(facts["value_spoken"]) + ".")
    if facts["as_of"]:
        parts.append(t["as_of"].format(year=facts["as_of"]))
    for label, value in facts["extras"]:
        parts.append(f"{label}: {_join(value, lang)}.")
    used = 0
    for sentence in facts["summary_sentences"]:
        if used >= MAX_SUMMARY_SENTENCES:
            break
        if len(" ".join(parts).split()) + len(sentence.split()) > word_budget:
            continue   # passt nicht ins Zeitbudget – evtl. passt ein kürzerer Satz
        parts.append(sentence)
        used += 1
    return " ".join(parts)


# --------------------------------------------------------------------------- Sprachmodell + Prüfung

def _digits(text: str) -> set[str]:
    return {re.sub(r"[.,]", "", n).lstrip("0") or "0" for n in re.findall(r"\d[\d.,]*\d|\d", text)}


def numbers_supported(text: str, facts: dict) -> bool:
    allowed = _digits(json.dumps(facts, ensure_ascii=False))
    return _digits(text) <= allowed


LLM_SYSTEM = {
    "de": (
        "Du schreibst Sprechertexte für kurze Ranking-Faktenvideos (TikTok/YouTube Shorts). "
        "Nutze AUSSCHLIESSLICH die gelieferten Fakten. Erfinde nichts, ergänze kein Wissen, "
        "nenne keine Zahlen, die nicht in den Fakten stehen. Lockerer, spannender Ton, kurze Sätze."
    ),
    "en": (
        "You write voice-over scripts for short ranking fact videos (TikTok/YouTube Shorts). "
        "Use ONLY the provided facts. Do not invent anything, add no outside knowledge, "
        "mention no numbers that are not in the facts. Casual, exciting tone, short sentences."
    ),
}


def llm_item_text(facts: dict, lang: str, word_budget: int) -> tuple[str | None, str]:
    """Gibt (Text, Prüfvermerk) zurück. Text ist None, wenn die Prüfung fehlschlägt."""
    first = TEXT[lang]["rank"].format(n=facts["rank"], name=facts["name"])
    user = (
        f"Fakten (JSON):\n{json.dumps(facts, ensure_ascii=False, indent=1)}\n\n"
        f"Schreibe {word_budget - 10} bis {word_budget} Wörter in der Sprache '{lang}'. "
        f"Beginne exakt mit: \"{first}\" Gib nur den Sprechertext aus."
    )
    try:
        text = llm.chat(LLM_SYSTEM[lang], user)
    except Exception as exc:  # Netz, Limit, Format …
        return None, f"Platz {facts['rank']}: Sprachmodell nicht erreichbar ({exc}), Textbausteine verwendet."
    text = text.strip().strip('"')
    if not text.startswith(first):
        return None, f"Platz {facts['rank']}: Sprachmodell-Text verworfen (falscher Anfang)."
    if not numbers_supported(text, facts):
        return None, f"Platz {facts['rank']}: Sprachmodell-Text verworfen (Zahl ohne Beleg)."
    try:
        verdict = llm.chat_json(
            "You are a strict fact checker. Answer only with JSON.",
            "Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False)
            + "\n\nText:\n" + text
            + '\n\nIs EVERY claim in the text directly supported by the facts? '
              'Answer {"supported": true|false, "unsupported": ["..."]}',
            temperature=0.0,
        )
    except Exception as exc:
        return None, f"Platz {facts['rank']}: Faktencheck nicht möglich ({exc}), Textbausteine verwendet."
    if not verdict.get("supported"):
        return None, f"Platz {facts['rank']}: Sprachmodell-Text verworfen (nicht belegt: {verdict.get('unsupported')})."
    return text, f"Platz {facts['rank']}: Sprachmodell-Text geprüft und übernommen."


# --------------------------------------------------------------------------- Gesamtskript

def build_script(spec: VideoSpec, research: Research, lang: str, use_llm: bool | None = None,
                 budget_scale: float = 1.0) -> Script:
    if use_llm is None:
        use_llm = llm.available()
    items = research.items
    n_items = max(1, len(items))
    total_words = int(spec.target_seconds * WORDS_PER_SECOND)
    word_budget = max(12, int((total_words - 70) / n_items * budget_scale))
    title = spec.title[lang]
    retrieved = format_date(research.fetched_at[:10], lang)

    top = items[0] if items else None
    top_spoken = quantity(top.value, top.unit, spec.unit).spoken(lang) if top else ""
    segments = [Segment(kind="intro", text=TEXT[lang]["intro"].format(title=title, top=top_spoken),
                        sources=[top.wikidata_url] if top else [])]
    checks: list[str] = []
    mode = "llm" if use_llm else "template"

    for item in sorted(items, key=lambda it: it.rank, reverse=True):   # Countdown: letzter Platz zuerst
        facts = item_facts(spec, item, lang)
        text = None
        if use_llm:
            text, note = llm_item_text(facts, lang, word_budget)
            checks.append(note)
        if text is None:
            text = template_item_text(facts, lang, word_budget)
        sources = [item.wikidata_url]
        if facts["summary_sentences"] and item.wiki_url(lang):
            sources.append(item.wiki_url(lang))
        segments.append(Segment(kind="item", text=text, rank=item.rank, sources=sources))

    segments.append(Segment(kind="outro", text=TEXT[lang]["outro"].format(date=retrieved)))
    return Script(lang=lang, title=title, segments=segments, mode=mode, checks=checks)
