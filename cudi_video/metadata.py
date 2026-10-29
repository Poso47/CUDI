"""Titel, Beschreibung (mit Quellen + Bildnachweisen), Hashtags und Prüfbericht."""

from __future__ import annotations

from .models import Research, Script
from .script import format_date
from .spec import VideoSpec
from .units import quantity

DISCLOSURE = {
    "de": "ℹ️ Automatisch erstellt. Die Stimme ist KI-generiert. Alle Fakten stammen aus den unten genannten Quellen.",
    "en": "ℹ️ Created automatically. The voice is AI-generated. All facts come from the sources listed below.",
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
        as_of = f" ({'Stand' if de else 'as of'} {it.value_date[:4]})" if it.value_date else ""
        lines.append(f"{it.rank}. {it.labels[lang]} – {value}{as_of}")
    lines += ["", DISCLOSURE[lang], "",
              ("📚 Quellen (abgerufen am " if de else "📚 Sources (retrieved ") + retrieved + "):"]
    lines.append("• Wikidata (CC0): " + ", ".join(it.qid for it in items))
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
    out += ["## Ranking", "", "| Platz | Name | Wert | Stand | Bild | Quelle |", "|---|---|---|---|---|---|"]
    for it in sorted(research.items, key=lambda i: i.rank):
        q = quantity(it.value, it.unit, spec.unit)
        out.append(f"| {it.rank} | {it.labels.get('de') or it.labels.get('en')} | {q.display('de')} | "
                   f"{it.value_date or '–'} | {'ja' if it.image_path else 'Grafik'} | [{it.qid}]({it.wikidata_url}) |")
    for s in scripts:
        out += ["", f"## Sprechertext ({s.lang}, Modus: {s.mode})", ""]
        if s.checks:
            out += [f"- {c}" for c in s.checks] + [""]
        for seg in s.segments:
            label = {"intro": "Intro", "outro": "Outro"}.get(seg.kind, f"Platz {seg.rank}")
            out.append(f"**{label}:** {seg.text}")
            out.append("")
    return "\n".join(out)
