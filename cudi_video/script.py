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
from .compare import comparison
from .verify import all_sources, source_label

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
        # Nur Varianten, in denen der Name allein steht (kein Artikel-/Kasusproblem).
        "rank": ["Platz {n}: {name}.", "Auf Platz {n}: {name}.", "Weiter mit Platz {n}: {name}."],
        "rank_first": "Wir starten mit Platz {n}: {name}.",
        "rank_one": "Und auf Platz 1: {name}!",
        "top3": "Jetzt wird es spannend – die Top 3!",
        "value": ["{label}: {value}.", "Das sind {value}."],
        "as_of": "Stand {year}.",
        "corrected": "Aktuelle Zahl laut {sources}.",
        "and": "und",
        "outro": (
            "Das war unser Ranking. Geprüft mit {sources}, abgerufen am {date}. "
            "Welcher Platz hat dich überrascht? Schreib es in die Kommentare und folge für mehr Rankings!"
        ),
        "wiki_langs": "Wikipedia in {n} Sprachen",
    },
    "en": {
        "intro": "{title}! Number one reaches {top} – but which one is it? Stay until the end!",
        "rank": ["Number {n}: {name}.", "At number {n}: {name}.", "Next up, number {n}: {name}."],
        "rank_first": "We start at number {n}: {name}.",
        "rank_one": "And number one: {name}!",
        "top3": "Now it gets exciting – the top 3!",
        "value": ["{label}: {value}.", "That's {value}."],
        "as_of": "As of {year}.",
        "corrected": "Latest figure according to {sources}.",
        "and": "and",
        "outro": (
            "That was our ranking. Checked against {sources}, retrieved on {date}. "
            "Which spot surprised you? Tell us in the comments and follow for more rankings!"
        ),
        "wiki_langs": "Wikipedia in {n} languages",
    },
}

# Nur bei Werten, die sich mit der Zeit ändern, wird der Stichtag genannt ("Stand 2025").
TIME_VARYING = {"P1082", "P1083", "P2131", "P2139"}

# Zählwörter für Werte ohne Einheit ("1,4 Milliarden Einwohner")
COUNT_NOUNS = {
    "P1082": {"de": "Einwohner", "en": "people"},
    "P1083": {"de": "Plätze", "en": "seats"},
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


# Neutralität: wertende, politische oder konfliktbezogene Aussagen gehören nicht in ein
# Fakten-Ranking (sie wären einseitig, weil der Kontext fehlt).
NOT_NEUTRAL = re.compile(
    r"(vorgeworfen|vorwürf|menschenrecht|diktat|regime|umstritten|kritik|kritisiert|krieg|konflikt|terror|anschlag"
    r"|annekt|besatz|besetz|propaganda|skandal|korrupt|völkermord|genozid|unterdrück|autoritär|zensur|sanktion"
    r"|accus|allegation|human rights|dictat|controvers|disputed|criticis|criticiz|\bwars?\b|conflict|annex"
    r"|occupation|occupied|scandal|corrupt|genocide|oppress|authoritarian|censorship|sanction)",
    re.I,
)


def has_risky_claims(sentence: str) -> bool:
    return bool(RISKY_WORDS.search(sentence) or NOT_NEUTRAL.search(sentence)) or has_risky_numbers(sentence)


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
    """Wikidata-Kurzbeschreibung ohne Zahlen, Rang-/Superlativ-Aussagen und Wertungen."""
    desc = item.descriptions.get(lang, "").strip()
    if has_risky_claims(desc):
        desc = re.split(r"[,;(]", desc)[0].strip()      # "Country in …, the largest in the world" -> vorderer Teil
        if has_risky_claims(desc):
            return ""
    return desc if len(desc.split()) >= 2 else ""      # "Country" allein sagt nichts


DEFINITION = re.compile(r"\b(ist|sind|war|waren|is|are|was|were)\b", re.I)


def usable_summary_sentences(item: RankItem, lang: str) -> list[str]:
    out: list[str] = []
    desc = usable_description(item, lang)
    has_desc = bool(item.descriptions.get(lang))
    for i, s in enumerate(_sentences(item.summary.get(lang, ""))):
        if has_risky_claims(s) or len(s.split()) > MAX_SENTENCE_WORDS or len(s) < 20 or not s[0].isupper():
            continue
        if i == 0 and has_desc and DEFINITION.search(" ".join(s.split()[:10])):
            continue   # Einleitungssatz definiert nur, was die Beschreibung schon sagt
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
    desc = item.descriptions.get(lang, "").lower()
    name = item.labels.get(lang, "").lower()
    for key, pid in spec.source.extras.items():
        value = item.extras.get(key, {}).get(lang)
        if not value or (" / " not in value and (value.lower() in desc or value.lower() == name)):
            continue   # fehlt, steht schon in der Beschreibung oder wiederholt nur den Namen (Monaco: Monaco)
        singular, plural = PROPERTY_LABELS.get(pid, ({"de": key.title(), "en": key.title()}, None))
        label = (plural or singular)[lang] if " / " in value else singular[lang]
        lines.append((label, value))
    return lines


def _capitalize(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def spoken_sources(sources: list[str], lang: str, limit: int = 3) -> list[str]:
    """Zum Vorlesen: Wikipedia-Sprachversionen zu "Wikipedia" zusammenfassen, höchstens 3 Namen."""
    names: list[str] = []
    for src in sources:
        name = "Wikipedia" if src.startswith("Wikipedia (") else source_label(src, lang)
        if name not in names:
            names.append(name)
    names.sort(key=lambda n: n == "Wikipedia")        # Institutionen zuerst, Wikipedia zuletzt
    return names[:limit]


def as_of_year(spec: VideoSpec, item: RankItem) -> str | None:
    """Stichtag nur für Werte, die sich mit der Zeit ändern (Einwohner ja, Fläche nein)."""
    return item.value_date[:4] if item.value_date and spec.source.property in TIME_VARYING else None


def spoken_with_noun(spec: VideoSpec, value: float, unit: str, lang: str, extra_decimals: int = 0) -> str:
    """'1,4 Milliarden Einwohner' statt '1,4 Milliarden' bei Werten ohne Einheit."""
    q = quantity(value, unit, spec.unit)
    noun = COUNT_NOUNS.get(spec.source.property, {}).get(lang)
    text = q.spoken(lang, extra_decimals)
    return f"{text} {noun}" if noun and not (q.unit and q.unit.symbol) else text


def distinct_precision(spec: VideoSpec, items: list[RankItem], lang: str) -> dict[str, int]:
    """Zusätzliche Nachkommastellen je Platz, damit unterschiedliche Werte nicht gleich klingen."""
    extra = {it.qid: 0 for it in items}
    for _ in range(3):
        spoken: dict[str, list[RankItem]] = {}
        for it in items:
            if it.value:
                spoken.setdefault(spoken_with_noun(spec, it.value, it.unit, lang, extra[it.qid]), []).append(it)
        clashes = [group for group in spoken.values() if len({g.value for g in group}) > 1]
        if not clashes:
            break
        for group in clashes:
            for it in group:
                extra[it.qid] += 1
    return extra


def item_facts(spec: VideoSpec, item: RankItem, lang: str, reference: dict | None = None,
               extra_decimals: int = 0) -> dict:
    q = quantity(item.value, item.unit, spec.unit)
    bare = q.spoken(lang, extra_decimals)
    spoken = spoken_with_noun(spec, item.value, item.unit, lang, extra_decimals)
    corrected_by = []
    if (item.verification or {}).get("status") == "korrigiert":
        corrected_by = spoken_sources(item.verification.get("sources", []), lang)
    return {
        "rank": item.rank,
        "name": item.labels[lang],
        "description": usable_description(item, lang),
        "value_label": spec.value_label.get(lang, ""),
        "value_spoken": spoken,
        "value_spoken_bare": bare,
        "value_display": q.display(lang),
        "has_unit": spoken != bare or bool(q.unit and q.unit.symbol),
        "as_of": as_of_year(spec, item),
        "comparison": comparison(item, reference, spec.source.property, lang),
        "corrected_by": corrected_by,
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

def rank_sentence(n: int, name: str, lang: str, first: bool) -> str:
    t = TEXT[lang]
    if n == 1:
        return t["rank_one"].format(name=name)
    if first:
        return t["rank_first"].format(n=n, name=name)
    text = t["rank"][n % len(t["rank"])].format(n=n, name=name)
    return f"{t['top3']} {text}" if n == 3 else text


def template_item_text(facts: dict, lang: str, word_budget: int, first: bool = False, detail: int = 2) -> str:
    """detail 2 = alles, 1 = ohne Wikipedia-Sätze und mit höchstens einer Zusatzinfo,
    0 = nur Rang, Wert, Vergleich und Stichtag (für die Längengrenze von Shorts)."""
    t = TEXT[lang]
    parts = [rank_sentence(facts["rank"], facts["name"], lang, first)]
    if facts["description"] and detail >= 1:
        parts.append(_capitalize(facts["description"]).rstrip(".") + ".")
    variant = t["value"][facts["rank"] % 2] if facts["has_unit"] else t["value"][0]
    if variant == t["value"][0] and facts["value_label"]:
        value_sentence = variant.format(label=facts["value_label"], value=facts["value_spoken_bare"])
    elif variant != t["value"][0]:
        value_sentence = variant.format(value=facts["value_spoken"])
    else:
        value_sentence = _capitalize(facts["value_spoken"]) + "."
    comp = facts["comparison"] or {}
    kind, text = comp.get("kind"), comp.get("text")
    if kind == "fragment":
        value_sentence = f"{value_sentence[:-1]} – {text}."     # Wert und Vergleich in einem Satz
    parts.append(value_sentence)
    if kind == "sentence":
        parts.append(text)
    if facts["as_of"]:
        parts.append(t["as_of"].format(year=facts["as_of"]))
    if facts["corrected_by"]:
        parts.append(t["corrected"].format(sources=_join(" / ".join(facts["corrected_by"]), lang)))
    extras = facts["extras"] if detail >= 2 else facts["extras"][:1] if detail == 1 else []
    for label, value in extras:
        parts.append(f"{label}: {_join(value, lang).rstrip('.')}.")
    used = 0
    for sentence in facts["summary_sentences"] if detail >= 2 else []:
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
        "nenne keine Zahlen, die nicht in den Fakten stehen. Bleib neutral: keine Wertungen, "
        "keine politischen Aussagen. Lockerer, spannender Ton, kurze Sätze."
    ),
    "en": (
        "You write voice-over scripts for short ranking fact videos (TikTok/YouTube Shorts). "
        "Use ONLY the provided facts. Do not invent anything, add no outside knowledge, "
        "mention no numbers that are not in the facts. Stay neutral: no judgments, "
        "no political statements. Casual, exciting tone, short sentences."
    ),
}


def llm_item_text(facts: dict, lang: str, word_budget: int, first_item: bool = False) -> tuple[str | None, str]:
    """Gibt (Text, Prüfvermerk) zurück. Text ist None, wenn die Prüfung fehlschlägt."""
    first = rank_sentence(facts["rank"], facts["name"], lang, first_item)
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
                 budget_scale: float = 1.0, detail: int = 2) -> Script:
    if use_llm is None:
        use_llm = llm.available()
    items = research.items
    n_items = max(1, len(items))
    total_words = int(spec.target_seconds * WORDS_PER_SECOND)
    word_budget = max(12, int((total_words - 70) / n_items * budget_scale))
    title = spec.title[lang]
    retrieved = format_date(research.fetched_at[:10], lang)

    top = items[0] if items else None
    top_spoken = spoken_with_noun(spec, top.value, top.unit, lang) if top else ""   # bewusst gerundet (Hook)
    segments = [Segment(kind="intro", text=TEXT[lang]["intro"].format(title=title, top=top_spoken),
                        sources=[top.wikidata_url] if top else [])]
    checks: list[str] = []
    mode = "llm" if use_llm else "template"

    reference = research.references.get(lang)
    precision = distinct_precision(spec, items, lang)
    countdown = sorted(items, key=lambda it: it.rank, reverse=True)   # Countdown: letzter Platz zuerst
    for i, item in enumerate(countdown):
        facts = item_facts(spec, item, lang, reference, precision.get(item.qid, 0))
        text = None
        if use_llm:
            text, note = llm_item_text(facts, lang, word_budget, first_item=i == 0)
            checks.append(note)
        if text is None:
            text = template_item_text(facts, lang, word_budget, first=i == 0, detail=detail)
        sources = [item.wikidata_url]
        if facts["comparison"] and reference:
            sources.append(reference["url"])
        if facts["summary_sentences"] and item.wiki_url(lang):
            sources.append(item.wiki_url(lang))
        segments.append(Segment(kind="item", text=text, rank=item.rank, sources=sources))

    names, n_langs = all_sources(research, lang)
    if n_langs:
        names.append(TEXT[lang]["wiki_langs"].format(n=n_langs))
    source_text = _join(" / ".join(names), lang)
    segments.append(Segment(kind="outro", text=TEXT[lang]["outro"].format(sources=source_text, date=retrieved)))
    return Script(lang=lang, title=title, segments=segments, mode=mode, checks=checks)
