"""Titel, Beschreibung (mit Quellen + Bildnachweisen), Hashtags und Prüfbericht."""

from __future__ import annotations

from .models import Research, Script
from .script import as_of_year, format_date
from .spec import VideoSpec
from .units import quantity
from .verify import compact_sources, confirmed_sources, source_label

DISCLOSURE = {
    "de": "ℹ️ Automatisch erstellt. Die Stimme ist KI-generiert. Alle Fakten stammen aus den unten genannten Quellen.",
    "en": "ℹ️ Created automatically. The voice is AI-generated. All facts come from the sources listed below.",
}
SOURCE_LINKS = {
    "Weltbank": "https://data.worldbank.org",
    "CIA World Factbook": "https://www.cia.gov/the-world-factbook/",
    "OpenStreetMap": "https://www.openstreetmap.org (ODbL)",
}
BASE_TAGS = {"de": ["shorts", "fakten", "top10", "wusstestdu"], "en": ["shorts", "facts", "top10", "didyouknow"]}


def build_metadata(spec: VideoSpec, research: Research, script: Script) -> dict:
    lang = script.lang
    de = lang == "de"
    items = sorted(research.items, key=lambda i: i.rank)
    retrieved = format_date(research.fetched_at[:10], lang)

    tags = list(dict.fromkeys(BASE_TAGS[lang] + [t.lower().replace(" ", "") for t in spec.hashtags]))
    title = f"{spec.title[lang]} 🏆"
    if len(title) > 90:
        title = spec.title[lang][:88]

    lines = [spec.title[lang] + (" – von Platz 10 bis Platz 1!" if de else " – from 10 to 1!").replace("10", str(len(items))), ""]
    for it in items:
        value = quantity(it.value, it.unit, spec.unit).display(lang)
        year = as_of_year(spec, it)
        as_of = f" ({'Stand' if de else 'as of'} {year})" if year else ""
        lines.append(f"{it.rank}. {it.labels[lang]} – {value}{as_of}")
        confirmed = confirmed_sources(it)
        if len(confirmed) >= 2:
            lines.append(f"   ✓ {compact_sources(confirmed, lang)}")
    lines += ["", DISCLOSURE[lang], "",
              ("📚 Quellen (abgerufen am " if de else "📚 Sources (retrieved ") + retrieved + "):"]
    lines.append("• Wikidata (CC0): " + ", ".join(it.qid for it in items))
    used = {src for it in items for src in confirmed_sources(it)}
    for name, url in SOURCE_LINKS.items():
        if name in used:
            lines.append(f"• {source_label(name, lang)}: {url}")
    ref = research.references.get(lang)
    if ref and any(ref.get("qid") != it.qid for it in items):
        lines.append(("• Vergleichswert: " if de else "• Comparison: ") + f"{ref['name']} ({ref['url']})")
    langs = sorted(src[len("Wikipedia ("):-1] for src in used if src.startswith("Wikipedia ("))
    if langs:
        lines.append(("• Abgleich mit Wikipedia-Sprachversionen: " if de else "• Cross-checked with Wikipedia editions: ")
                     + ", ".join(langs))
    wiki_used = [it.wiki_url(lang) for it in items if it.summary.get(lang) and it.wiki_url(lang)]
    if wiki_used:
        lines.append("• Wikipedia (CC BY-SA 4.0):")
        lines += [f"  {u}" for u in wiki_used]
    credits = [(it.labels[lang], it.image_credit) for it in items if it.image_credit]
    if credits:
        lines += ["", "📷 Bildnachweise:" if de else "📷 Image credits:"]
        lines += [f"• {name}: {credit}" for name, credit in credits]
    lines += ["", " ".join(f"#{t}" for t in tags)]
    return {"title": title, "description": "\n".join(lines), "tags": tags}


def build_review(spec: VideoSpec, research: Research, scripts: list[Script]) -> str:
    """Markdown-Bericht für die Freigabe vor dem Hochladen."""
    out = [f"# Prüfbericht: {spec.title.get('de') or next(iter(spec.title.values()))}", "",
           f"Daten abgerufen: {research.fetched_at}", ""]
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
