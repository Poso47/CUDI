"""Titel, Beschreibung (mit Bildnachweisen), Hashtags und Prüfbericht (mit allen Quellen)."""

from __future__ import annotations

import re

from . import handoff, textcheck
from .models import Research, Script
from .script import as_of_year, format_date
from .spec import VideoSpec
from .units import quantity
from .verify import all_sources, compact_sources, confirmed_sources, source_label

DISCLOSURE = {
    "de": "ℹ️ Die Stimme ist KI-generiert. Alle Zahlen sind mit mehreren unabhängigen Quellen abgeglichen.",
    "en": "ℹ️ The voice is AI-generated. Every figure was cross-checked with several independent sources.",
}
FACT_DISCLOSURE = {
    "de": "ℹ️ Die Stimme ist KI-generiert. Jeder Fakt ist wörtlich in Fachquellen belegt, Zahlen sind mit einer zweiten Quelle abgeglichen.",
    "en": "ℹ️ The voice is AI-generated. Every fact is backed word for word by reference sources; figures are cross-checked with a second source.",
}
SOURCE_LINKS = {
    "Weltbank": "https://data.worldbank.org",
    "CIA World Factbook": "https://www.cia.gov/the-world-factbook/",
    "OpenStreetMap": "https://www.openstreetmap.org (ODbL)",
}
BASE_TAGS = {"de": ["shorts", "fakten", "top10", "wusstestdu"], "en": ["shorts", "facts", "top10", "didyouknow"]}
# Hashtags (3–5, keine Spam-Liste): erst Themen-Tags der Vorlage, dann ein bis zwei allgemeine, zuletzt der
# Plattform-Tag (YouTube: #shorts, TikTok: #fyp – dort ist #shorts wirkungslos).
KIND_TAGS = {"numbers": {"de": ["top{n}", "ranking"], "en": ["top{n}", "ranking"]},
             "facts": {"de": ["fakten", "wusstestdu"], "en": ["facts", "didyouknow"]}}
PLATFORM_TAG = {"youtube": "shorts", "tiktok": "fyp"}
MAX_TAGS = 5
TITLE_MAX = 60
CLICKBAIT = re.compile(r"glaub|schock|krass|unfassbar|unglaublich|nicht zu fassen|wirst du nie|passiert dann|"
                       r"believe|shock|insane|mind.?blow|gone wrong|you.?ll never|jaw.?drop|will blow", re.I)
TITLE_TEASER = {"numbers": {"de": "kennst du Platz 1?", "en": "can you guess #1?"},
                "facts": {"de": "wusstest du das?", "en": "did you know?"}}
# Längenziel je Videoart in Sekunden (Hinweis im Prüfbericht, nie ein harter Schnitt)
LENGTH_GOALS = {"facts": (35, 60), "numbers": (45, 90), "erklaer": (60, 180)}
# Kurztext für TikTok: Zeichenlimit, Links sind dort nicht klickbar – Quellen nur als Namen.
CAPTION = {
    "de": {"hook": "Welcher Platz hat dich überrascht? 👇", "checked": "✓ Geprüft mit", "and": "und",
           "langs": "Sprachen", "as_of": "Stand", "note": "ℹ️ KI-Stimme · Bildnachweise im Video"},
    "en": {"hook": "Which spot surprised you? 👇", "checked": "✓ Checked against", "and": "and",
           "langs": "languages", "as_of": "as of", "note": "ℹ️ AI voice · image credits in the video"},
}


# --------------------------------------------------------------------------- Titel, Hashtags, Längenziel

def _kind(spec: VideoSpec) -> str:
    return "facts" if spec.kind == "facts" else "numbers"


def fit_title(text: str, limit: int = TITLE_MAX) -> str:
    """Auf höchstens `limit` Zeichen kürzen, an einer Wortgrenze."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit]
    return cut.rstrip(" ,;:–-")


def _peak(spec: VideoSpec, items, lang: str) -> str:
    if _kind(spec) != "numbers" or not items:
        return ""
    try:
        return quantity(items[0].value, items[0].unit, spec.unit).display(lang)
    except Exception:
        return ""


def title_score(title: str, base: str) -> float:
    """Regel für die beste Variante: Länge im Sweet Spot (30–55), Zahl, Frage/Neugier-Lücke; Original gewinnt Gleichstand."""
    n = len(title)
    score = 2.0 if 30 <= n <= 55 else 1.0 if n <= TITLE_MAX else -9.0
    score += 1.0 if re.search(r"\d", title) else 0.0
    score += 1.0 if title.endswith("?") else 0.0
    score += 0.1 if title == base else 0.0
    return score


def rule_titles(spec: VideoSpec, research: Research, lang: str) -> list[str]:
    """Drei Titelvarianten aus Titel und geprüften Werten (ohne Sprachmodell), je ≤ 60 Zeichen."""
    from .render.cover import clean_title

    items = sorted(research.items, key=lambda i: i.rank)
    kind = _kind(spec)
    base = clean_title(spec.title[lang])
    n = len(items) or spec.count
    peak = _peak(spec, items, lang)
    teaser = TITLE_TEASER[kind][lang]
    if kind == "facts":
        second = f"{n} {'Fakten' if lang == 'de' else 'facts'}: {base}"
    elif peak:
        second = f"{'Platz 1' if lang == 'de' else 'No. 1'}: {peak} – {base}"
    else:
        second = f"Top {n}: {base}"
    cands = [fit_title(base), fit_title(f"{base} – {teaser}"), fit_title(second), fit_title(f"{base}: {teaser}"),
             fit_title(f"Top {n}: {base}")]
    out: list[str] = []
    for c in cands:
        if c and c.lower() not in {o.lower() for o in out} and not CLICKBAIT.search(c):
            out.append(c)
    return out[:3] if len(out) >= 3 else out + [fit_title(base)[:TITLE_MAX]] * (3 - len(out))


def allowed_title_numbers(spec: VideoSpec, research: Research, lang: str) -> set[str]:
    """Zahlen, die in einem Titel stehen dürfen: aus dem Titel, der Anzahl und den geprüften Werten."""
    items = sorted(research.items, key=lambda i: i.rank)
    text = " ".join([*spec.title.values(), str(len(items) or spec.count)])
    for it in items:
        try:
            text += " " + quantity(it.value, it.unit, spec.unit).display(lang)
        except Exception:
            continue
    return textcheck.numbers(text, lang) | textcheck.numbers(text, "de" if lang == "en" else "en")


def check_title(title: object, allowed: set[str], lang: str) -> str | None:
    """None = in Ordnung, sonst der Grund für die Ablehnung (Länge, Clickbait, Zahl ohne Beleg)."""
    if not isinstance(title, str) or not title.strip():
        return "leer"
    if len(title) > TITLE_MAX:
        return "länger als 60 Zeichen"
    if CLICKBAIT.search(title):
        return "Clickbait"
    if "#" in title:
        return "Hashtag im Titel"
    if not textcheck.numbers(title, lang) <= allowed:
        return "Zahl ohne Beleg"
    return None


TITLE_INSTRUCTIONS = (
    "Schreibe je Sprache in „daten“ genau 3 Titelvarianten für das Kurzvideo (TikTok/YouTube Shorts), jede höchstens "
    "60 Zeichen. Weck Neugier, ohne zu lügen: keine Clickbait-Floskeln („du wirst nicht glauben“, „schockierend“, "
    "„krass“), kein Spoiler von Platz 1, keine Hashtags, keine Emojis. Nenne nur Zahlen aus „erlaubte_zahlen“ und "
    "Wörter, die zum „titel“ und den „plaetze“ passen – nichts dazuerfinden. Die drei Varianten sollen sich im "
    "Aufbau unterscheiden (z. B. Frage, Zahl vorn, Versprechen). Antwort: JSON {\"de\": [\"…\", \"…\", \"…\"], "
    "\"en\": [...]}."
)


def title_task(spec: VideoSpec, research: Research, langs: list[str]) -> tuple[str, str, dict] | None:
    """Die Schreibaufgabe „titel“ (Name, Anleitung, Daten) – für `handoff.request_many` (eine Runde mit dem Erzählen)."""
    if not handoff.active() or not research.items:
        return None
    data = {lang: {"titel": spec.title[lang], "erlaubte_zahlen": sorted(allowed_title_numbers(spec, research, lang)),
                   "plaetze": [{"platz": it.rank, "name": it.labels.get(lang) or it.labels.get("en", "")}
                               for it in sorted(research.items, key=lambda i: i.rank)[:5]]}
            for lang in langs}
    return "titel", TITLE_INSTRUCTIONS, data


def request_titles(spec: VideoSpec, research: Research, langs: list[str]) -> dict:
    """Titelvarianten von Claude bzw. dem Notbetrieb-LLM {Sprache: [Titel]} oder {} (nicht aktiv / keine Antwort).
    Geprüft wird erst in `choose_titles`; was nicht besteht, ersetzen die Regel-Varianten."""
    asked = title_task(spec, research, langs)
    if asked is None:
        return {}
    answer = handoff.request(*asked)
    return answer if isinstance(answer, dict) else {}


def choose_titles(spec: VideoSpec, research: Research, lang: str, llm: dict | None = None) -> dict:
    """3 Varianten (geprüfte Claude-Titel zuerst, mit Regel-Varianten aufgefüllt) und die per Regel beste."""
    allowed = allowed_title_numbers(spec, research, lang)
    titles: list[str] = []
    rejected: list[str] = []
    for t in (llm or {}).get(lang) or []:
        reason = check_title(t, allowed, lang)
        if reason:
            rejected.append(f"{t!r}: {reason}")
        elif t.strip().lower() not in {x.lower() for x in titles}:
            titles.append(t.strip())
    for t in rule_titles(spec, research, lang):
        if len(titles) < 3 and t.lower() not in {x.lower() for x in titles}:
            titles.append(t)
    titles = (titles + [fit_title(spec.title[lang])] * 3)[:3]
    base = fit_title(spec.title[lang])
    best = max(titles, key=lambda t: title_score(t, base))
    return {"titles": titles, "best": best, "rejected": rejected}


def hashtags(spec: VideoSpec, lang: str, platform: str = "youtube", n: int | None = None) -> list[str]:
    """3–5 Hashtags: Themen-Tags der Vorlage, allgemeine Tags der Videoart, zuletzt der Plattform-Tag."""
    generic = [t.format(n=n or spec.count) for t in KIND_TAGS[_kind(spec)][lang]]
    raw = [*spec.tags_for(lang)[:3], *generic]
    tags: list[str] = []
    for t in raw:
        t = re.sub(r"[^\w]", "", str(t).lower())
        if t and t not in tags and t != PLATFORM_TAG[platform] and len(t) <= 30:
            tags.append(t)
    return [*tags[:MAX_TAGS - 1], PLATFORM_TAG[platform]]


def length_hint(kind: str, seconds: float, lang: str = "de") -> str | None:
    """Hinweis für den Prüfbericht, wenn die Länge das Ziel der Videoart verfehlt (nie ein harter Schnitt)."""
    lo, hi = LENGTH_GOALS.get("numbers" if kind == "ranking" else kind, (0, 0))
    if not hi or lo <= seconds <= hi:
        return None
    label = {"facts": "Fakten-Video", "numbers": "Ranking", "erklaer": "Erklärvideo"}.get(kind, kind)
    if seconds > hi:
        return (f"Länge {seconds:.0f} s liegt über dem Ziel für {label} ({lo}–{hi} s): "
                "Kürzer hält mehr Zuschauer bis zum Ende.")
    return f"Länge {seconds:.0f} s liegt unter dem Ziel für {label} ({lo}–{hi} s): Mehr Inhalt oder Tiefe wäre möglich."


def build_metadata(spec: VideoSpec, research: Research, script: Script, titles_llm: dict | None = None,
                   seconds: float | None = None) -> dict:
    lang = script.lang
    de = lang == "de"
    items = sorted(research.items, key=lambda i: i.rank)
    retrieved = format_date(research.fetched_at[:10], lang)

    choice = choose_titles(spec, research, lang, titles_llm)
    best = choice["best"]
    tags = hashtags(spec, lang, "youtube", len(items))
    tags_tiktok = hashtags(spec, lang, "tiktok", len(items))
    title = f"{best} 🏆" if len(best) + 3 <= TITLE_MAX + 3 else best

    lines = [spec.title[lang] + (" – von Platz 10 bis Platz 1!" if de else " – from 10 to 1!").replace("10", str(len(items))), ""]
    for it in items:
        if spec.kind == "facts":
            lines.append(f"{it.rank}. {it.labels[lang]}")
            continue
        value = quantity(it.value, it.unit, spec.unit).display(lang)
        year = as_of_year(spec, it)
        as_of = f" ({'Stand' if de else 'as of'} {year})" if year else ""
        lines.append(f"{it.rank}. {it.labels[lang]} – {value}{as_of}")
    lines += ["", FACT_DISCLOSURE[lang] if spec.kind == "facts" else DISCLOSURE[lang]]
    wiki_used = [it.wiki_url(lang) for it in items if it.summary.get(lang) and it.wiki_url(lang)]
    if wiki_used:      # übernommene Wikipedia-Inhalte: Lizenz verlangt die Nennung
        lines.append(("📖 Infos: Wikipedia (CC BY-SA 4.0), Wikidata (CC0)" if de
                      else "📖 Info: Wikipedia (CC BY-SA 4.0), Wikidata (CC0)"))
    credits = [(it.labels[lang], it.image_credit) for it in items if it.image_credit]
    credits += [(it.labels[lang], c["credit"]) for it in items for c in it.clips if c.get("credit")]
    credits = list(dict.fromkeys(credits))                 # zwei Ausschnitte aus demselben Clip nur einmal nennen
    if credits:
        lines += ["", "📷 Bild- und Videonachweise:" if de else "📷 Image and video credits:"]
        lines += [f"• {name}: {credit}" for name, credit in credits]
    lines += ["", " ".join(f"#{t}" for t in tags)]
    meta = {"title": title, "titles": choice["titles"], "title_chosen": best, "description": "\n".join(lines),
            "tags": tags, "tags_tiktok": tags_tiktok,
            "caption": short_caption(spec, research, lang, tags_tiktok, best)}
    hint = length_hint(spec.kind if spec.kind == "facts" else "ranking", seconds, lang) if seconds else None
    if hint:
        meta["length_hint"] = hint
    return meta


def short_caption(spec: VideoSpec, research: Research, lang: str, tags: list[str], title: str | None = None) -> str:
    """TikTok-Text: Titel, KI-Hinweis, Hashtags (mit #fyp, ohne #shorts). Quellen stehen nur im Prüfbericht."""
    c = CAPTION[lang]
    return "\n".join([
        f"{title or spec.title[lang]} 🏆 {c['hook']}", "",
        c["note"], "",
        " ".join(f"#{t}" for t in tags if t != "shorts"),
    ])


def bild_zeile(item) -> list[str]:
    """Prüfbericht je Fakt: Motiv und ob das Bild den Fakt wirklich zeigt (Bildpassung)."""
    bild = item.fact.get("bild") or {}
    motif = bild.get("motiv") or item.fact.get("motiv")
    if not bild and not motif:
        return []
    if bild.get("passt") is True:
        seen = f", Bildprüfung {bild['wert']:.2f}" if bild.get("wert") is not None else ""
        verdict = f"Bild passt ({bild.get('quelle')}{seen})"
    elif bild.get("quelle") == "kein Bild":
        verdict = "kein Bild gefunden – Infografik"
    elif bild.get("passt") is False:
        verdict = "Stimmungsbild – Bild zeigt nicht genau den Fakt"
    else:
        verdict = "Bildpassung nicht geprüft"
    aha = (item.fact.get("aha") or {}).get("de")
    return [f"Motiv: {motif or '–'} · {verdict}" + (f" · Aha: {aha}" if aha else "")]


def build_review(spec: VideoSpec, research: Research, scripts: list[Script]) -> str:
    """Markdown-Bericht für die Freigabe vor dem Hochladen."""
    out = [f"# Prüfbericht: {spec.title.get('de') or next(iter(spec.title.values()))}", "",
           f"Daten abgerufen: {research.fetched_at}", ""]
    if spec.angle:
        out += [f"**Deutung des Themas:** {spec.angle}", ""]
    question = (spec.focus.get("frage") or {}).get("de")
    if question:
        out += [f"**Themenkern:** {question}"
                + (f" – Aspekte: {', '.join(spec.focus.get('aspekte') or [])}" if spec.focus.get("aspekte") else "")
                + (f" – nicht gemeint: {', '.join(spec.focus.get('nicht') or [])}" if spec.focus.get("nicht") else ""), ""]
    counts: dict[str, int] = {}
    for it in research.items:
        status = (it.verification or {}).get("status", "nicht geprüft")
        counts[status] = counts.get(status, 0) + 1
    order = ["bestätigt", "korrigiert", "nur eine Quelle", "widersprüchlich", "nicht geprüft"]
    summary = ", ".join(f"{counts[k]} {k}" for k in order + sorted(set(counts) - set(order)) if k in counts)
    out += [f"**Quellen-Abgleich:** {summary}", ""]
    if research.warnings:
        out += ["## ⚠️ Bitte prüfen", ""] + [f"- {w}" for w in research.warnings] + [""]
    else:
        out += ["## ✅ Keine Auffälligkeiten in den Daten", ""]
    if spec.kind == "facts":
        out += ["## Fakten-Ranking (Belege)", ""]
        for it in sorted(research.items, key=lambda i: i.rank):
            aspect = f" ({it.fact['aspekt']})" if it.fact.get("aspekt") else ""
            out += [f"**{it.rank}. {it.labels.get('de') or it.labels.get('en')}**{aspect} – {it.verification.get('status')}",
                    *bild_zeile(it),
                    f"> {it.fact.get('beleg')}", *[f"> {b}" for b in it.fact.get("belege") or []],
                    f"Quelle: [{it.fact.get('quelle')}]({it.fact.get('url')})"
                    + (f" · Zahlen bestätigt durch: {it.fact['zweitquelle']}" if it.fact.get("zweitquelle") else ""), ""]
        for s in scripts:
            out += ["", f"## Sprechertext ({s.lang})", ""]
            for seg in s.segments:
                label = {"intro": "Intro", "outro": "Outro"}.get(seg.kind, f"Platz {seg.rank}")
                out += [f"**{label}:** {seg.text}", ""]
        return "\n".join(out)
    out += ["## Ranking", "", "| Platz | Name | Wert | Stand | Abgleich | Bild | Quelle |", "|---|---|---|---|---|---|---|"]
    for it in sorted(research.items, key=lambda i: i.rank):
        q = quantity(it.value, it.unit, spec.unit)
        status = (it.verification or {}).get("status", "–")
        out.append(f"| {it.rank} | {it.labels.get('de') or it.labels.get('en')} | {q.display('de')} | "
                   f"{it.value_date or '–'} | {status} | {'ja' if it.image_path else 'Grafik'} | "
                   f"[{it.qid}]({it.wikidata_url}) |")
    out += ["", "## Quellen-Abgleich je Platz", "",
            "✓ = stimmt überein · ✗ = weicht ab · ? = Wert dort nicht genannt", ""]
    for it in sorted(research.items, key=lambda i: i.rank):
        evidence = (it.verification or {}).get("evidence", [])
        if not evidence:
            continue
        out.append(f"**{it.rank}. {it.labels.get('de') or it.labels.get('en')}**")
        for e in evidence:
            mark = {True: "✓", False: "✗"}.get(e["agrees"], "?")
            value = f" – {quantity(e['value'], it.unit, spec.unit).display('de')}" if e["value"] is not None else ""
            date = f" ({e['date'][:4]})" if e.get("date") else ""
            out.append(f"- {mark} [{e['source']}]({e['url']}) · {e['origin']}{value}{date}")
        out.append("")
    for s in scripts:
        out += ["", f"## Sprechertext ({s.lang}, Modus: {s.mode})", ""]
        if s.checks:
            out += [f"- {c}" for c in s.checks] + [""]
        for seg in s.segments:
            label = {"intro": "Intro", "outro": "Outro"}.get(seg.kind, f"Platz {seg.rank}")
            out.append(f"**{label}:** {seg.text}")
            out.append("")
    return "\n".join(out)
