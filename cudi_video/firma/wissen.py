"""Wissens-Sammler: aktuelle, öffentlich zugängliche Erkenntnisse zu Short-Form-Retention -> firma_daten/wissen.json.

Zwei Teile, klar getrennt:
* **Basis** (`BASIS`): feste, im Code gepflegte Checkliste mit gut belegten Grundlagen. Sie steht immer drin, ist als
  „Basis“ gekennzeichnet und braucht keine Quelle im Lauf.
* **Regeln** (`regeln`): wöchentlich gesammelt aus offiziellen Blogs/Newsrooms (YouTube, TikTok) und frei zugänglichen
  Studien-Abstracts (Europe PMC, Open Access). Ein freies Sprachmodell (Gemini über `CUDI_LLM_*`, kein Claude) fasst sie zu
  kurzen, prüfbaren Regeln zusammen. Übernommen wird nur, was auf eine tatsächlich gelesene Quelle zeigt und dort
  Stichwörter wiederfindet; Quelle, Link und Datum setzt der Code aus der Quelle, nie das Modell. Ohne Modell/Ausfall bleiben
  die bisherigen Regeln stehen (nichts wird erfunden)."""

from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import timedelta

from . import common
from .common import fetch, iso, now, run_source
from .news import clean, _when

MAX_REGELN = 30
MAX_AGE_DAYS = 400
TEXT_CHARS = 700

# Fest gepflegte, gut belegte Grundlagen (Basis). id -> (Kurzname, Regel, Begründung/Stand der Forschung)
BASIS: dict[str, tuple[str, str, str]] = {
    "hook": ("Hook in den ersten 1–2 Sekunden",
             "Der erste Satz ist kurz (höchstens ~12 Wörter) und weckt sofort Neugier – Frage, überraschende Zahl oder Bild im Kopf.",
             "Kurzvideo-Plattformen entscheiden in Sekunden über Weiterwischen; offizielle Creator-Hinweise nennen den Einstieg als "
             "wichtigsten Moment."),
    "neugier": ("Neugierlücke",
                "Eine Frage oder Lücke öffnen, die erst später im Video geschlossen wird – ohne die Antwort vorwegzunehmen.",
                "Loewenstein 1994 (Information-Gap-Theorie der Neugier)."),
    "musterbruch": ("Musterunterbrechung alle paar Sekunden",
                    "Regelmäßig etwas Neues: Frage, direkte Ansprache, Zwischen-Aufhänger, Tempo- oder Themenwechsel.",
                    "Aufmerksamkeit fällt bei Gleichförmigkeit ab; Orientierungsreaktion auf Neues (Praxis-Standard im Schnitt)."),
    "fortschritt": ("Sichtbarer Fortschritt",
                    "Countdown, Platznummern oder „gleich kommt“ zeigen, wie weit das Video ist und was noch kommt.",
                    "Zielgradient-Effekt: Motivation wächst, je näher das Ziel rückt."),
    "payoff": ("Payoff am Ende",
               "Das Versprochene wird am Schluss eingelöst (Auflösung, „Heute gelernt“) – das Ende bleibt im Gedächtnis.",
               "Peak-End-Regel (Kahneman): Rückblick wird von Höhepunkt und Ende geprägt."),
    "ansprache": ("Natürliche Ansprache „du“",
                  "Zuschauer direkt ansprechen, wie im Gespräch mit einem Freund – nicht wie ein Vortrag.",
                  "Direkte Ansprache erhöht Beteiligung; gesprochene Sprache wird leichter verarbeitet als Schriftsprache."),
    "rhythmus": ("Kurze Sätze, wechselnder Rhythmus",
                 "Kurze Sätze, dazwischen auch mal ein längerer; keine Schachtelsätze; Satzlängen variieren.",
                 "Gleichförmiger Satzbau klingt vorgelesen; Variation hält das Ohr wach."),
    "verbindung": ("Sätze verbinden",
                   "Sätze mit und/aber/dann/weil verknüpfen statt Fakten aufzuzählen; jeder Satz knüpft an den vorigen an.",
                   "Kohärenz erleichtert das Verstehen beim Hören; Aufzählungen wirken wie vorgelesen."),
    "einordnung": ("Zahlen einordnen",
                   "Jede wichtige Zahl bekommt ein Bild im Kopf oder einen Vergleich („so hoch wie …“, „nur noch X trennen …“).",
                   "Zahlen ohne Bezugsgröße werden schlecht behalten (Zahlenverständnis, Praxis der Wissenschaftskommunikation)."),
    "kernaussage": ("Eine Kernaussage pro Szene",
                    "Jede Szene bringt genau eine Hauptidee (höchstens wenige Zahlen), damit man sie beim Hören behält.",
                    "Begrenzte Arbeitsgedächtnis-Kapazität beim Hören (Cognitive-Load-Forschung)."),
    "loop": ("Loop-Ende",
             "Das Ende greift den Anfang wieder auf oder lädt zum erneuten Ansehen/Kommentieren ein.",
             "Wiedersehen und Kommentare zählen als starke Signale; ein Bogen zurück zum Hook belohnt das Zuhören."),
    "natuerlich": ("Natürliche gesprochene Sprache",
                   "Schreib, wie man spricht: Alltagswörter, Kontraktionen im Englischen, kaum Amtsdeutsch, Füllwörter sparsam.",
                   "Vorgelesener Schrifttext wirkt künstlich und wird eher weggewischt."),
}

# Live geprüft (08.11.2026): blog.youtube/rss/ liefert RSS. Die Creator-/News-Unterfeeds des YouTube-Blogs sind 404, der TikTok-Newsroom
# bietet keinen Feed (alle /rss-Adressen liefern HTML) – darum nur dieser Feed; weitere offizielle Feeds hier eintragen.
FEEDS = [
    ("YouTube Official Blog", "offiziell", "https://blog.youtube/rss/"),
]
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PMC_QUERY = ('(("short-form video" OR "short video" OR TikTok OR "YouTube Shorts") AND (attention OR engagement OR '
             'retention OR "viewer")) AND OPEN_ACCESS:y AND FIRST_PDATE:[{since} TO {until}]')
KEYWORDS = re.compile(r"short|retention|watch ?time|engage|recommend|algorithm|attention|viewer|audience|hook|creator|"
                      r"discover|feed|loop|storytell", re.I)

SYSTEM = ("Du bist Redakteur für Kurzvideo-Dramaturgie. Antworte ausschließlich mit gültigem JSON, ohne Erklärtext.")
INSTRUCTIONS = (
    "Aus „quellen“ (Titel + Auszug offizieller Veröffentlichungen und Studien-Abstracts) sollst du kurze, prüfbare Regeln "
    "für Kurzvideo-Drehbücher (TikTok/YouTube Shorts) ableiten, die das Zuschauer-Halten betreffen. Jede Regel muss sich "
    "direkt auf EINE Quelle stützen (deren „id“ angeben) und darf nichts behaupten, was nicht im Auszug steht. Keine "
    "Zahlen oder Prozentwerte, die nicht im Auszug stehen. Formuliere jede Regel auf Deutsch als Handlungsanweisung "
    "(höchstens 200 Zeichen). Zu jeder Regel gehört „beleg“: ein WÖRTLICH kopierter Satzteil (mindestens 12 Zeichen) aus Titel oder "
    "Auszug der Quelle, der die Regel stützt. Gibt eine Quelle nichts Brauchbares her, lass sie aus. Höchstens 12 Regeln. "
    "Antwort: {\"regeln\": [{\"id\": \"q3\", \"regel\": \"…\", \"beleg\": \"…\"}]}"
)


# --------------------------------------------------------------------------- Quellen

def feed_items(name: str, art: str, url: str) -> list[dict]:
    root = ET.fromstring(fetch(url, timeout=20).content)
    ns = "{http://www.w3.org/2005/Atom}"
    out = []
    for item in list(root.iter("item")) + list(root.iter(f"{ns}entry")):
        title = clean(item.findtext("title") or item.findtext(f"{ns}title") or "", 200)
        text = clean(item.findtext("description") or item.findtext(f"{ns}summary") or item.findtext(f"{ns}content") or "",
                     TEXT_CHARS)
        link = item.findtext("link") or ""
        if not link:
            el = item.find(f"{ns}link")
            link = el.get("href", "") if el is not None else ""
        when = _when(item.findtext("pubDate") or item.findtext(f"{ns}updated") or item.findtext(f"{ns}published") or "")
        if title and link and KEYWORDS.search(f"{title} {text}"):
            out.append({"quelle": name, "art": art, "titel": title, "text": text, "link": link.strip(),
                        "datum": when.date().isoformat() if when else ""})
    return out[:15]


def europe_pmc() -> list[dict]:
    """Frei zugängliche (Open-Access-)Studien der letzten zwei Jahre; nur Titel, Abstract-Auszug, Link, Datum."""
    since = (now() - timedelta(days=730)).date().isoformat()
    data = fetch(EUROPE_PMC, params={"query": PMC_QUERY.format(since=since, until=now().date().isoformat()),
                                     "format": "json", "resultType": "core", "pageSize": 15, "sort": "P_PDATE_D desc"},
                 timeout=30).json()
    out = []
    for r in (data.get("resultList") or {}).get("result") or []:
        abstract = clean(html.unescape(r.get("abstractText") or ""), TEXT_CHARS)
        title = clean(r.get("title") or "", 200)
        ident = r.get("pmcid") or r.get("id") or ""
        if title and abstract and ident:
            link = f"https://europepmc.org/article/{r.get('source', 'MED')}/{r.get('id', ident)}"
            out.append({"quelle": "Europe PMC" + (f" · {r['journalTitle']}" if r.get("journalTitle") else ""), "art": "studie",
                        "titel": title, "text": abstract, "link": link, "datum": str(r.get("firstPublicationDate") or "")[:10]})
    return out


# --------------------------------------------------------------------------- Regeln ableiten

RECHERCHE_FRAGE = "Kurzvideo Zuschauerbindung Hook Retention Empfehlungsalgorithmus TikTok YouTube Shorts"


def recherche_quellen() -> list[dict]:
    """Aktuelle Webseiten (Behörden/Fachquellen/Plattform-Blogs), vom Recherche-Agent gelesen und datiert; nur mit Datum."""
    from .. import recherche

    if not recherche.aktiv():
        return []
    recherche.neuer_lauf()
    e = recherche.recherchiere(RECHERCHE_FRAGE, "wissen", "de", max_seiten=5, llm=False)
    return [{"quelle": q["name"], "datum": q["datum"], "titel": q["titel"], "text": q["text"][:900], "link": q["link"], "art": "recherche"}
            for q in recherche.seiten_als_quellen(e) if q.get("datum")]


def ableiten(sources: list[dict], answer) -> list[dict]:
    """Regeln des Modells prüfen: Quelle muss existieren, Länge passen, Zahlen im Auszug stehen. Quelle/Datum/Link vom Code."""
    found = answer.get("regeln") if isinstance(answer, dict) else answer
    out, seen = [], set()
    for e in found if isinstance(found, list) else []:
        if not isinstance(e, dict):
            continue
        ident = str(e.get("id", "")).lstrip("q")
        src = sources[int(ident)] if ident.isdigit() and int(ident) < len(sources) else None
        regel = re.sub(r"\s+", " ", str(e.get("regel") or "")).strip()
        if not src or not 25 <= len(regel) <= 220 or regel.lower() in seen:
            continue
        evidence = f"{src['titel']} {src['text']}"
        if not set(re.findall(r"\d+(?:[.,]\d+)?", regel)) <= set(re.findall(r"\d+(?:[.,]\d+)?", evidence)):
            continue                                                  # Zahl ohne Beleg in der Quelle
        beleg = re.sub(r"\s+", " ", str(e.get("beleg") or "")).strip().lower()
        if len(beleg) < 12 or beleg not in re.sub(r"\s+", " ", evidence).lower():
            continue                                                  # kein wörtlicher Beleg aus der Quelle -> nicht übernehmen
        seen.add(regel.lower())
        out.append({"regel": regel, "quelle": src["quelle"], "titel": src["titel"], "link": src["link"],
                    "datum": src["datum"], "art": src["art"]})
    return out


def merge(old: list[dict], new: list[dict]) -> list[dict]:
    keep = [r for r in common.thin_by_age(old, "datum", MAX_AGE_DAYS) if r.get("regel") and r.get("link") and r.get("datum")]
    by_rule = {r["regel"].lower(): r for r in keep}
    for r in new:
        by_rule[r["regel"].lower()] = r
    return sorted(by_rule.values(), key=lambda r: r["datum"], reverse=True)[:MAX_REGELN]


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    items: list[dict] = []
    for name, art, url in FEEDS:
        items += run_source(name, lambda n=name, a=art, u=url: feed_items(n, a, u), notes)
    items += run_source("Europe PMC", europe_pmc, notes)
    items += run_source("Recherche (aktuelle Webquellen)", recherche_quellen, notes)
    previous = common.read_json("wissen.json", {}) or {}
    old_rules = previous.get("regeln") or []
    new_rules: list[dict] = []
    from .. import llm

    if items and llm.available():
        sources = items[:40]
        payload = [{"id": f"q{i}", "quelle": s["quelle"], "datum": s["datum"], "titel": s["titel"], "auszug": s["text"]}
                   for i, s in enumerate(sources)]
        try:
            import json

            answer = llm.chat_json(SYSTEM, INSTRUCTIONS + "\n\nDATEN:\n" + json.dumps({"quellen": payload}, ensure_ascii=False),
                                   temperature=0.2, timeout=120)
            new_rules = ableiten(sources, answer)
        except Exception as exc:                                       # noqa: BLE001 – Modell/Netz: bisherige Regeln bleiben
            notes.append(f"Zusammenfassung nicht möglich ({common.short_error(exc)}) – bisherige Regeln bleiben")
    elif items:
        notes.append("Kein Sprachmodell (CUDI_LLM_*) – bisherige Regeln bleiben, nichts wird ohne Quelle ergänzt")
    rules = merge(old_rules, new_rules)
    data = {"erzeugt": iso(), "hinweis": "Basis = fest gepflegte Grundlagen; Regeln = aus Quellen (mit Link und Datum).",
            "basis": [{"id": k, "name": v[0], "regel": v[1], "begruendung": v[2], "art": "basis"} for k, v in BASIS.items()],
            "quellen_geprueft": len(items), "neue_regeln": len(new_rules), "hinweise": notes, "regeln": rules}
    changed = common.write_json("wissen.json", data)
    common.record_status("wissen", started, bool(items or rules),
                         f"{len(items)} Quellen gelesen, {len(new_rules)} neue Regeln, {len(rules)} gesamt"
                         + ("" if changed else " (unverändert)"), notes)
    return data
