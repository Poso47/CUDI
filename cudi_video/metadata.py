"""Titel, Beschreibung (mit Bildnachweisen), Hashtags und Prüfbericht (mit allen Quellen)."""

from __future__ import annotations

from .models import Research, Script
from .script import as_of_year, format_date
from .spec import VideoSpec
from .units import quantity
from .verify import all_sources, compact_sources, confirmed_sources, source_label

DISCLOSURE = {
    "de": "ℹ️ Die Stimme ist KI-generiert. Alle Zahlen sind mit mehreren unabhängigen Quellen abgeglichen.",
    "en": "ℹ️ The voice is AI-generated. Every figure was cross-checked with several independent sources.",
}
SOURCE_LINKS = {
    "Weltbank": "https://data.worldbank.org",
    "CIA World Factbook": "https://www.cia.gov/the-world-factbook/",
    "OpenStreetMap": "https://www.openstreetmap.org (ODbL)",
}
BASE_TAGS = {"de": ["shorts", "fakten", "top10", "wusstestdu"], "en": ["shorts", "facts", "top10", "didyouknow"]}
# Kurztext für TikTok: Zeichenlimit, Links sind dort nicht klickbar – Quellen nur als Namen.
CAPTION = {
    "de": {"hook": "Welcher Platz hat dich überrascht? 👇", "checked": "✓ Geprüft mit", "and": "und",
           "langs": "Sprachen", "as_of": "Stand", "note": "ℹ️ KI-Stimme · Bildnachweise im Video"},
    "en": {"hook": "Which spot surprised you? 👇", "checked": "✓ Checked against", "and": "and",
           "langs": "languages", "as_of": "as of", "note": "ℹ️ AI voice · image credits in the video"},
}


def build_metadata(spec: VideoSpec, research: Research, script: Script) -> dict:
    lang = script.lang
    de = lang == "de"
    items = sorted(research.items, key=lambda i: i.rank)
    retrieved = format_date(research.fetched_at[:10], lang)

    tags = list(dict.fromkeys(BASE_TAGS[lang] + spec.tags_for(lang)))
    title = f"{spec.title[lang]} 🏆"
    if len(title) > 90:
        title = spec.title[lang][:88]

    lines = [spec.title[lang] + (" – von Platz 10 bis Platz 1!" if de else " – from 10 to 1!").replace("10", str(len(items))), ""]
    for it in items:
        value = quantity(it.value, it.unit, spec.unit).display(lang)
        year = as_of_year(spec, it)
        as_of = f" ({'Stand' if de else 'as of'} {year})" if year else ""
        lines.append(f"{it.rank}. {it.labels[lang]} – {value}{as_of}")
    lines += ["", DISCLOSURE[lang]]
    wiki_used = [it.wiki_url(lang) for it in items if it.summary.get(lang) and it.wiki_url(lang)]
    if wiki_used:      # übernommene Wikipedia-Inhalte: Lizenz verlangt die Nennung
        lines.append(("📖 Infos: Wikipedia (CC BY-SA 4.0), Wikidata (CC0)" if de
                      else "📖 Info: Wikipedia (CC BY-SA 4.0), Wikidata (CC0)"))
    credits = [(it.labels[lang], it.image_credit) for it in items if it.image_credit]
    credits += [(it.labels[lang], c["credit"]) for it in items for c in it.clips if c.get("credit")]
    if credits:
        lines += ["", "📷 Bild- und Videonachweise:" if de else "📷 Image and video credits:"]
        lines += [f"• {name}: {credit}" for name, credit in credits]
    lines += ["", " ".join(f"#{t}" for t in tags)]
    return {"title": title, "description": "\n".join(lines), "tags": tags,
            "caption": short_caption(spec, research, lang, tags)}


def short_caption(spec: VideoSpec, research: Research, lang: str, tags: list[str]) -> str:
    """TikTok-Text: Titel, KI-Hinweis, Hashtags (ohne #shorts). Quellen stehen nur im Prüfbericht."""
    c = CAPTION[lang]
    return "\n".join([
        f"{spec.title[lang]} 🏆 {c['hook']}", "",
        c["note"], "",
        " ".join(f"#{t}" for t in tags if t != "shorts"),
    ])


def build_review(spec: VideoSpec, research: Research, scripts: list[Script]) -> str:
    """Markdown-Bericht für die Freigabe vor dem Hochladen."""
    out = [f"# Prüfbericht: {spec.title.get('de') or next(iter(spec.title.values()))}", "",
           f"Daten abgerufen: {research.fetched_at}", ""]
    counts: dict[str, int] = {}
    for it in research.items:
        status = (it.verification or {}).get("status", "nicht geprüft")
        counts[status] = counts.get(status, 0) + 1
    order = ["bestätigt", "korrigiert", "nur eine Quelle", "widersprüchlich", "nicht geprüft"]
    summary = ", ".join(f"{counts[k]} {k}" for k in order if k in counts)
    out += [f"**Quellen-Abgleich:** {summary}", ""]
    if research.warnings:
        out += ["## ⚠️ Bitte prüfen", ""] + [f"- {w}" for w in research.warnings] + [""]
    else:
        out += ["## ✅ Keine Auffälligkeiten in den Daten", ""]
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
