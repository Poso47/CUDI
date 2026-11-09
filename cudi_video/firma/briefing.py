"""Morgen-Briefing: was in der Firma lief + was in der Welt los ist -> firma_daten/briefing.json und briefing.md.

Grundsatz (nie lügen, auch nicht durch Formulierung): Alle Punkte stammen wörtlich aus den Daten der anderen Mitarbeiter
(status/trends/news/welt/ideen/lernen/wissen) und tragen ihre Quellenlinks. Zusammenhänge nur, wenn belegt (Wikidata-Link in
welt.json). Alles Unbelegte steht ausschließlich als ausdrücklich markierte „offene Frage“. Ein Sprachmodell (CUDI_LLM_*) darf
nur eine kurze Übersicht aus diesen Punkten formulieren; neue Zahlen, Vornamen oder Links -> Regel-Fassung ohne Modell.
Archiv: briefing_archiv.json (30 Tage) – ähnliche frühere bestätigte Meldungen erscheinen nur als Hinweis, ohne Wertung."""

from __future__ import annotations

import re
import time
from datetime import timedelta

from . import common
from . import news as newsmod
from .common import iso, now

NAMES = {"trends": "Trend-Scout", "news": "News-Reporter", "welt": "Welt-Blick", "ideen": "Ideen-Entwickler",
         "putzen": "Putzmann", "clipscout": "Clip-Scout", "messung": "Messung", "lernen": "Lern-Analyst", "wissen": "Wissens-Sammler", "briefing": "Morgen-Briefing"}
FRESH_H = 24
MAX_MD = 60_000
ARCHIV, ARCHIV_DAYS = "briefing_archiv.json", 30


def _cut(text, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def point(text: str, links: list[tuple[str, str]] | None = None) -> dict:
    return {"text": text, "links": [{"titel": _cut(t, 40), "url": u} for t, u in (links or []) if u][:5]}


# --------------------------------------------------------------------------- Wichtigste Meldungen + Archiv

def _unabh(m: dict, qs: list[dict]) -> int:
    """Anzahl unabhängiger Gruppen unter den passenden Quellen (ältere Daten ohne Gruppenangabe: je Quelle eine)."""
    if any("gruppe" in q for q in qs):
        return len({q.get("gruppe") for q in qs if "gruppe" in q} | {f"x{i}" for i, q in enumerate(qs) if "gruppe" not in q})
    return len(qs)


def agreeing(m: dict) -> list[dict]:
    """Nur Quellen, deren Titel zur Hauptmeldung passt (Schutz vor fehlerhaft zusammengefassten Gruppen)."""
    tok = newsmod.tokens(m["titel"])
    return [q for i, q in enumerate(m.get("quellen", []))
            if q.get("titel") == m["titel"] or i == 0 or newsmod.similar(tok, newsmod.tokens(q.get("titel", "")))]


def _wer(q: dict) -> str:
    """„Welt – gehört Axel Springer SE“ bzw. „… – Eigentümer unbekannt“; abhängige Quellen mit Grund."""
    text = q.get("quelle", "")
    if q.get("eigentuemer"):
        text += f" – {q['eigentuemer']}"
    if q.get("zaehlt_nicht"):
        text += f" [zählt nicht: {q['zaehlt_nicht']}]"
    return text


def top_items(news: dict, welt: dict, limit: int = 5) -> list[dict]:
    """Zuerst von >= 3 nicht beteiligten Ländern übereinstimmend berichtet, dann von >= 2 unabhängigen Betreibern bestätigt."""
    out = []
    for g in welt.get("themen", []):
        if g.get("bestaetigt_laender"):
            skipped = sorted({q["land"] for q in g.get("quellen", []) if q.get("beteiligt")})
            head = f"übereinstimmend berichtet in {len(g['laender_einig'])} Ländern ({', '.join(g['laender_einig'])})"
            if skipped:
                head += f"; beteiligte Länder nicht mitgezählt: {', '.join(skipped)}"
            zeilen = [_wer(q) for q in g.get("quellen", []) if q.get("zaehlt_nicht")]
            out.append({"titel": _cut(g["titel"], 150), "kopf": head,
                        "zeilen": g.get("zusammenfassung", [])[:5] + [f"Eigentümer: {_wer(q)}" for q in g.get("quellen", [])[:5] if q.get("eigentuemer")] + zeilen,
                        "links": [(f"{q['quelle']} ({q['land']})", q["link"]) for q in g.get("quellen", [])]})
    for m in news.get("meldungen", []):
        qs = agreeing(m) if m.get("status") == "bestätigt" else []
        if len(qs) >= 2 and _unabh(m, qs) >= 2:
            out.append({"titel": _cut(m["titel"], 150), "kopf": f"bestätigt von {_unabh(m, qs)} unabhängigen Quellgruppen",
                        "zeilen": [f"{_wer(q)}: {_cut(q.get('titel'), 140)}" for q in qs][:5],
                        "links": [(q.get("quelle", ""), q.get("link", "")) for q in qs]})
    return out[:limit]


def archive_hints(items: list[dict], today: str) -> list[dict]:
    """Ähnliche frühere bestätigte Meldungen als Hinweis (ohne Wertung); Archiv 30 Tage, danach ausgedünnt."""
    old = (common.read_json(ARCHIV, {}) or {}).get("eintraege", [])
    hints = []
    for it in items:
        tok = newsmod.tokens(it["titel"])
        for e in old:
            if e["datum"] != today and newsmod.similar(tok, set(e.get("tokens", []))):
                hints.append(point(f"Frühere Meldung vom {e['datum']}: „{_cut(e['titel'], 130)}“ – zu „{_cut(it['titel'], 100)}“ gehört "
                                   "möglicherweise eine Fortsetzung oder Korrektur; nicht bewertet.", [("frühere Meldung", e.get("link", ""))]))
                break
    limit = (now() - timedelta(days=ARCHIV_DAYS)).strftime("%Y-%m-%d")
    keep = [e for e in old if e["datum"] >= limit]
    have = {(e["datum"], e["titel"]) for e in keep}
    for it in items:
        if (today, it["titel"]) not in have:
            keep.append({"datum": today, "titel": it["titel"], "link": it["links"][0][1] if it["links"] else "",
                         "tokens": sorted(newsmod.tokens(it["titel"]))})
    common.write_json(ARCHIV, {"erzeugt": iso(), "eintraege": keep[-300:]})
    return hints[:5]


# --------------------------------------------------------------------------- Abschnitte

def section_top(top: list[dict], hints: list[dict]) -> list[dict]:
    pts = [point(f"{t['titel']} – {t['kopf']}.\n" + "\n".join("  · " + z for z in t["zeilen"]), t["links"]) for t in top]
    return pts + hints


def section_firma(status: dict, ideen: dict, lernen: dict, wissen: dict) -> list[dict]:
    pts = []
    t0 = now() - timedelta(hours=FRESH_H)
    for key, s in sorted(status.items()):
        if key == "briefing":
            continue
        when = common.parse_time(s.get("letzter_lauf", ""))
        name = NAMES.get(key, key)
        if not when:
            pts.append(point(f"{name}: noch kein Lauf eingetragen."))
        elif s.get("ergebnis") == "fehler":
            pts.append(point(f"{name}: letzter Lauf ({s['letzter_lauf']}) FEHLGESCHLAGEN – {_cut(s.get('zusammenfassung'), 160)}"))
        elif when < t0 and (now() - when) > timedelta(hours=common.WORKERS.get(key, 24) * 2 + FRESH_H):
            pts.append(point(f"{name}: kein Lauf in den letzten {FRESH_H} Stunden (zuletzt {s['letzter_lauf']}) – ist der Zeitplan aktiv?"))
        else:
            pts.append(point(f"{name}: {_cut(s.get('zusammenfassung'), 160)} (Lauf {s['letzter_lauf']})."))
        for h in (s.get("hinweise") or [])[:2]:
            pts.append(point(f"Hinweis von {name}: {_cut(h, 170)}"))
    new = [i for i in (ideen.get("ideen") or []) if (common.parse_time(i.get("erstellt", "")) or t0) >= t0]
    if new:
        pts.append(point(f"{len(new)} neue Video-Ideen in den letzten {FRESH_H} Stunden, z. B. „{_cut(new[0].get('titel'), 80)}“"
                         + (f" und „{_cut(new[1].get('titel'), 80)}“." if len(new) > 1 else ".")))
    if lernen.get("zusammenfassung"):
        pts.append(point(f"Lern-Analyst: {_cut(lernen['zusammenfassung'], 200)}"))
    if wissen.get("neue_regeln"):
        pts.append(point(f"Wissens-Sammler: {wissen['neue_regeln']} neue Regeln gelernt."))
    return pts


STUFE = {"erlaubt": "erlaubt (Beleg)", "geduldet": "geduldet, nicht ausdrücklich erlaubt", "unklar": "Erlaubnis offen",
         "gesperrt": "gesperrt"}


def section_entdeckt(ent: dict) -> list[dict]:
    """Entdeckte Creator im Hype: Top 10 mit ehrlicher Stufe, offene Fälle mit Link (ohne Wertung), neu erlaubte Zugänge."""
    rows = [e for e in ent.get("creators", []) if isinstance(e, dict) and e.get("erlaubnis") != "gesperrt"]
    pts = []
    if rows:
        def wer(e):
            extra = f", {e['aufrufe_je_stunde']:.0f} Aufrufe/Stunde" if e.get("aufrufe_je_stunde") else ""
            sig = f" (Signale: {'; '.join(e['signale'][:3])})" if e.get("erlaubnis") == "geduldet" and e.get("signale") else ""
            return f"{_cut(e.get('name'), 30)} ({e.get('plattform', '?')}{extra}, {STUFE.get(e.get('erlaubnis', 'unklar'), 'Erlaubnis offen')}{sig})"
        top = rows[:10]
        pts.append(point("Im Hype (Top 10 von " + str(len(rows)) + " entdeckten Creatorn): " + " · ".join(f"{i}. {wer(e)}" for i, e in enumerate(top, 1)),
                         [(e.get("name", ""), e.get("link", "")) for e in top]))
    for e in [e for e in rows if e.get("erlaubnis") == "unklar" and e.get("link")][:3]:
        pts.append(point(f"Im Hype, Erlaubnis offen: {_cut(e.get('name'), 40)} – {_cut(e.get('grund'), 120)}.", [("Quelle", e["link"])]))
    t0 = now() - timedelta(hours=48)
    for e in rows:
        seen = common.parse_time(e.get("erste_sichtung", ""))
        if e.get("erlaubnis") == "erlaubt" and seen and seen >= t0:
            pts.append(point(f"Neu entdeckt mit belegter Erlaubnis: {_cut(e.get('name'), 40)} – {_cut(e.get('grund'), 120)}.", [("Quelle", e.get("link", ""))]))
            if len(pts) >= 8:
                break
    return pts


def section_clipteam(radar: dict, erl: dict, mess: dict, ent: dict | None = None) -> list[dict]:
    """Clip-Team: nur Belegtes – virale Videos mit belegter Erlaubnis, Creator mit Erlaubnis (Zitat+Link), Messwerte eigener Posts."""
    pts = section_entdeckt(ent or {})
    t0 = now() - timedelta(hours=FRESH_H)
    for v in [v for v in radar.get("videos", []) if v.get("erlaubt") and v.get("faktor", 0) >= 1.5][:3]:
        pts.append(point(f"Virales erlaubtes Material: {_cut(v.get('creator'), 40)} – „{_cut(v.get('titel'), 90)}“, "
                         f"{v.get('aufrufe_je_stunde', 0):.0f} Aufrufe/Stunde ({v.get('faktor')}× Kanal-Median).", [("Video", v.get("url", ""))]))
    for c in erl.get("creators", []):
        if c.get("status") != "erlaubt":
            continue
        b = next((b for b in c.get("belege", []) if b.get("url") and b.get("zitat")), None)
        when = common.parse_time(c.get("geprueft", ""))
        if b and when and when >= t0:
            pts.append(point(f"Erlaubnis belegt: {_cut(c.get('name'), 40)} – „{_cut(b['zitat'], 120)}“ ({b.get('datum', '')}).", [("Beleg", b["url"])]))
    for url, e in sorted((mess.get("posts") or {}).items(), key=lambda kv: -(kv[1].get("verlauf") or [{"aufrufe": 0}])[-1]["aufrufe"])[:3]:
        if e.get("verlauf"):
            last = e["verlauf"][-1]
            pts.append(point(f"Eigener Post: {last['aufrufe']} Aufrufe, {last.get('likes') or 0} Likes (Stand {last['zeit'][:10]}).", [("Post", url)]))
    return pts


def section_confirmed(news: dict) -> list[dict]:
    pts = []
    for m in news.get("meldungen", []):
        qs = agreeing(m) if m.get("status") == "bestätigt" else []
        if len(qs) < 2 or _unabh(m, qs) < 2:
            continue
        links = [(q.get("quelle", ""), q.get("link", "")) for q in qs]
        wer = "; ".join(_wer(q) for q in qs[:5])
        pts.append(point(f"{_cut(m['titel'], 150)} – bestätigt von {_unabh(m, qs)} unabhängigen Quellgruppen ({wer}).", links))
        if len(pts) >= 6:
            break
    return pts


def section_abroad(welt: dict) -> list[dict]:
    pts = []
    for g in welt.get("themen", [])[:8]:
        links = [(f"{q['quelle']} ({q['land']})", q["link"]) for q in g.get("quellen", [])]
        lands = ", ".join(g.get("laender", []))
        if g.get("bestaetigt_laender"):
            pts.append(point(f"Übereinstimmend in {len(g['laender_einig'])} Ländern ({', '.join(g['laender_einig'])}): {_cut(g['titel'], 150)}", links))
        elif g.get("nur_ausland"):
            pts.append(point(f"Nur im Ausland gefunden ({g['ausland_quellen']} Betreiber: {lands}): {_cut(g['titel'], 150)} "
                             "– in den ausgewerteten deutschen Medien keine passende Meldung.", links))
        elif g.get("deutsch_quellen"):
            de = g["deutsch_quellen"][0]
            pts.append(point(f"Ausland ({lands}): „{_cut(g['titel'], 120)}“ – Deutschland ({de['quelle']}): „{_cut(de['titel'], 120)}“. "
                             "Beides ist nur nebeneinandergestellt, nicht bewertet.", links + [(de["quelle"], de["link"])]))
        else:
            pts.append(point(f"Ausland ({lands}): {_cut(g['titel'], 150)}", links))
        beteiligt = sorted({q["land"] for q in g.get("quellen", []) if q.get("beteiligt")})
        if beteiligt:
            pts[-1]["text"] += f" Beteiligte Länder (für die Übereinstimmung nicht gezählt): {', '.join(beteiligt)}."
        if g.get("staatsnah"):
            pts[-1]["text"] += f" Hinweis: {', '.join(g['staatsnah'])} ist staatsnah getragen."
        wer = "; ".join(_wer(q) for q in g.get("quellen", [])[:5] if q.get("eigentuemer"))
        if wer:
            pts[-1]["text"] += f" Quellen: {wer}."
    return pts


def section_links(welt: dict) -> list[dict]:
    pts = []
    for v in welt.get("verbindungen", []):
        rows = [r for r in v.get("verbindungen", []) if not r.get("beendet")][:4] or v.get("verbindungen", [])[:3]
        text = "; ".join(f"{r['eigenschaft']}: {r['wert']}" + (f" (bis {r['beendet']})" if r.get("beendet")
                                                               else " (kein Enddatum eingetragen – ob noch aktuell, ist offen)")
                         for r in rows)
        links = [(v["name"] + " (Wikidata)", v["wikidata"])] + [(r["wert"], r["link"]) for r in rows]
        pts.append(point(f"{v['name']} – laut Wikidata {text}. Genannt in: „{_cut(v['themen'][0], 110)}“.", links))
    return pts


def section_questions(welt: dict, news: dict) -> list[dict]:
    pts = []
    for g in welt.get("themen", []):
        if g.get("nur_ausland") and not g.get("bestaetigt_laender") and len(pts) < 3:
            pts.append(point(f"OFFENE FRAGE (unbelegt): Warum berichten {g['ausland_quellen']} ausländische Betreiber über „{_cut(g['titel'], 110)}“, "
                             "während in den ausgewerteten deutschen Medien keine passende Meldung auftaucht? Eine Erklärung ist nicht belegt.",
                             [(q["quelle"], q["link"]) for q in g.get("quellen", [])]))
    for m in [m for m in news.get("meldungen", []) if m.get("status") != "bestätigt"][:2]:
        pts.append(point(f"OFFENE FRAGE (unbelegt): Wird „{_cut(m['titel'], 120)}“ (bisher nur {m.get('quelle', 'eine Quelle')}) "
                         "von einer zweiten unabhängigen Quelle bestätigt?", [(m.get("quelle", ""), m.get("link", ""))]))
    return pts


def build_sections(top: list[dict] | None = None, hints: list[dict] | None = None) -> list[dict]:
    r = common.read_json
    status = (r("status.json", {}) or {}).get("mitarbeiter", {})
    ideen, lernen, wissen = r("ideen.json", {}) or {}, r("lernen.json", {}) or {}, r("wissen.json", {}) or {}
    news, welt = r("news.json", {}) or {}, r("welt.json", {}) or {}
    secs = [("0. Die wichtigsten Meldungen (je höchstens 5 Zeilen)", section_top(top or [], hints or [])),
            ("1. Firma – was lief", section_firma(status, ideen, lernen, wissen)),
            ("2. Bestätigte Meldungen (≥ 2 unabhängige Betreiber)", section_confirmed(news)),
            ("3. Deutschland von außen", section_abroad(welt)),
            ("4. Belegte Verbindungen (Wikidata)", section_links(welt)),
            ("5. Offene Fragen (nicht belegt, nur Fragen)", section_questions(welt, news)),
            ("6. Clip-Team (nur Belegtes)", section_clipteam(r("clip_radar.json", {}) or {}, r("clip_erlaubnis.json", {}) or {},
                                                            r("messung.json", {}) or {}, r("clip_entdeckt.json", {}) or {}))]
    empty = {"0": "Heute keine Meldung, die mehrere Länder bzw. Betreiber bestätigen.", "1": "Keine Mitarbeiter-Daten vorhanden.",
             "2": "Heute keine Meldung mit zwei unabhängigen Betreibern.", "3": "Keine Auslandsberichte mit Deutschland-Bezug erhalten.",
             "4": "Keine belegte Verbindung gefunden.", "5": "Keine offenen Fragen.", "6": "Kein belegtes Clip-Material und keine Messwerte heute."}
    return [{"titel": t, "punkte": p or [point(empty[t[0]])]} for t, p in secs]


# --------------------------------------------------------------------------- Übersicht (Regeln oder Sprachmodell)

LLM_SYSTEM = (
    "Du fasst ein Morgen-Briefing zusammen. STRENGE REGELN: Nutze ausschließlich die gelieferten Punkte. Keine neuen Zahlen, "
    "Namen, Orte, Links oder Ursachen. Keine Vermutungen, keine Andeutungen, keine Verschwörungen, keine Wertung über Personen; "
    "Unbelegtes nur als Frage mit „offene Frage“ kennzeichnen. Zusammenhänge nur, wenn ein Punkt sie ausdrücklich nennt. "
    'Höchstens 90 Wörter, Deutsch, sachlich. Antworte als JSON: {"ueberblick": "..."}')


def rule_overview(sections: list[dict]) -> str:
    n = [len(s["punkte"]) for s in sections]
    return (f"Wichtigste Meldungen: {n[0]}. Firma: {n[1]} Punkte. Bestätigte Meldungen: {n[2]}. Deutschland von außen: {n[3]} Themen. "
            f"Belegte Verbindungen: {n[4]}. Offene Fragen: {n[5]}. Clip-Team: {n[6]}. Alles mit Quellenlinks; Unbelegtes steht nur als Frage.")


INTERNA = re.compile(r"Sprachmodell|GDELT|Workflow|\bAPI\b|nicht erreichbar|Mitarbeiter|Hinweis|Secret|Zugangsdaten", re.I)


def check_overview(text: str, source: str) -> list[str]:
    from .. import textcheck
    problems = []
    new_nums = textcheck.numbers(text, "de") - textcheck.numbers(source, "de")
    if new_nums:
        problems.append(f"neue Zahlen {sorted(new_nums)}")
    if textcheck.invented_people(text, source):
        problems.append("neue Vornamen")
    if re.search(r"https?://|www\.", text):
        problems.append("Link im Text")
    if INTERNA.search(text):
        problems.append("Interna im Text")
    return problems


def overview(sections: list[dict], notes: list[str]) -> tuple[str, str]:
    from .. import llm
    plain = rule_overview(sections)
    if not llm.available():
        return plain, "regeln"
    # nur die Nachrichten-Abschnitte – Firma-Interna (Ausfälle, Hinweise) gehören nicht in den Welt-Überblick
    source = "\n".join(f"[{s['titel']}] " + " | ".join(p["text"] for p in s["punkte"])
                       for s in sections if not s["titel"].startswith(("1.", "6.")))
    try:
        text = " ".join(str(llm.chat_json(LLM_SYSTEM, source, temperature=0.2, timeout=90).get("ueberblick", "")).split())
        problems = check_overview(text, source) if text else ["leer"]
        if len(text) > 900:
            problems.append("zu lang")
        if problems:
            notes.append("Sprachmodell-Übersicht verworfen: " + ", ".join(problems))
            return plain, "regeln"
        return text, "llm"
    except Exception as exc:                          # noqa: BLE001 – Ausfall = Regel-Fassung
        notes.append(f"Sprachmodell nicht erreichbar ({common.short_error(exc)})")
        return plain, "regeln"


def markdown(date: str, over: str, sections: list[dict], notes: list[str]) -> str:
    out = [f"# CUDI-Briefing {date}", "", over, ""]
    for s in sections:
        out += [f"## {s['titel']}", ""]
        for p in s["punkte"]:
            links = " ".join(f"[{l['titel']}]({l['url']})" for l in p["links"])
            first, *rest = p["text"].split("\n")
            out.append(f"- {first}")
            out += [f"  {r}" for r in rest]
            if links:
                out.append(f"  Quellen: {links}")
        out.append("")
    if notes:
        out += ["_Hinweise: " + "; ".join(notes) + "_", ""]
    out.append("_Nur aus den gesammelten Daten; Quellen in Klammern. Unbelegtes steht nur als „offene Frage“._")
    return "\n".join(out)[:MAX_MD] + "\n"


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    from zoneinfo import ZoneInfo
    date = now().astimezone(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")
    news, welt = common.read_json("news.json", {}) or {}, common.read_json("welt.json", {}) or {}
    hints = archive_hints(top_items(news, welt, 30), date)
    sections = build_sections(top_items(news, welt), hints)
    over, mode = overview(sections, notes)
    data = {"erzeugt": iso(), "datum": date, "modus": mode, "ueberblick": over, "abschnitte": sections, "hinweise": notes}
    common.write_json("briefing.json", data)
    md = markdown(date, over, sections, notes)
    path = common.DATA_DIR / "briefing.md"
    common.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text("utf-8") != md:
        path.write_text(md, "utf-8")
    common.record_status("briefing", started, True, f"Briefing {date} ({mode}), {sum(len(s['punkte']) for s in sections)} Punkte", notes)
    return data
