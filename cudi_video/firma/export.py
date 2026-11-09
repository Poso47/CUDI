"""Kompakte Sammeldatei für das 3D-Büro der App: firma_daten/* -> docs/firma/firma.json (GitHub Pages, CORS offen).

Nur das, was die Stationskarten zeigen (Top-Trends, bestätigte News, Ideen mit Auftrag, Wissensregeln, Putzbericht, Status).
Wird nur geschrieben, wenn sich außer den flüchtigen Feldern etwas ändert (kein Commit ohne Neuigkeit).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .. import config
from . import common

OUT = Path(os.environ.get("CUDI_FIRMA_EXPORT", config.PROJECT_DIR / "docs" / "firma" / "firma.json"))
MAX_BYTES = 60_000


def _cut(text, n: int) -> str:
    return " ".join(str(text or "").split())[:n]


def _extra(name: str) -> dict | None:
    """Optionale Mitarbeiter (Lern-Analyst, Wahrheits-Prüfer): nur kurze Skalare/Listen, falls ihre Datei existiert."""
    data = common.read_json(name)
    if not isinstance(data, dict):
        return None
    out: dict = {}
    for k, v in data.items():
        if isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) <= 300):
            out[k] = v
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            out[k] = [_cut(x, 160) for x in v[:5]]
    return out or None


def build() -> dict:
    status = (common.read_json("status.json", {}) or {}).get("mitarbeiter", {})
    for s in status.values():
        s["hinweise"] = [_cut(x, 160) for x in (s.get("hinweise") or [])[:3]]
        s["zusammenfassung"] = _cut(s.get("zusammenfassung"), 200)
    trends = (common.read_json("trends.json", {}) or {}).get("themen", [])
    news = common.read_json("news.json", {}) or {}
    meldungen = sorted(news.get("meldungen", []), key=lambda m: m.get("status") == "bestätigt", reverse=True)
    ideen = (common.read_json("ideen.json", {}) or {}).get("ideen", [])
    wissen = common.read_json("wissen.json", {}) or {}
    last = (common.read_json("putzen.json", {}) or {}).get("letzter_lauf") or {}
    data = {
        "version": 1, "erzeugt": common.iso(), "status": status,
        "trends": [{"thema": _cut(t.get("thema"), 80), "kategorie": _cut(t.get("kategorie"), 30), "score": t.get("score")}
                   for t in trends[:5]],
        "news": {"bestaetigt": news.get("bestaetigt", 0), "anzahl": news.get("anzahl", 0),
                 "meldungen": [{"titel": _cut(m.get("titel"), 140), "kurz": _cut(m.get("kurz"), 160), "link": m.get("link", ""),
                                "quelle": _cut(m.get("quelle"), 40), "n_quellen": m.get("n_quellen", 1), "status": m.get("status", "")}
                               for m in meldungen[:5]]},
        "ideen": [{"id": i.get("id"), "bereich": i.get("bereich"), "titel": _cut(i.get("titel"), 80),
                   "begruendung": _cut(i.get("begruendung"), 200), "hinweis": _cut(i.get("hinweis"), 160),
                   "auftrag": i.get("auftrag") if i.get("app_auftrag") else None}
                  for i in ideen[:8]],
        "wissen": {"basis": len(wissen.get("basis", [])), "neu": wissen.get("neue_regeln", 0), "gesamt": len(wissen.get("regeln", [])),
                   "regeln": [{"regel": _cut(r.get("regel"), 220), "quelle": _cut(r.get("quelle"), 60), "link": r.get("link", ""),
                               "datum": r.get("datum", "")} for r in wissen.get("regeln", [])[:5]]},
        "putzen": {"zeit": last.get("zeit", ""), "entfernt": last.get("entfernt", {}),
                   "hinweise": [_cut(x, 160) for x in last.get("hinweise", [])[:3]]},
    }
    welt = common.read_json("welt.json", {}) or {}
    if welt.get("themen"):
        data["welt"] = {"anzahl": welt.get("anzahl", 0), "nur_ausland": welt.get("nur_ausland", 0),
                        "themen": [{"titel": _cut(g.get("titel"), 140), "link": g.get("link", ""), "laender": g.get("laender", [])[:6],
                                    "laender_einig": g.get("laender_einig", [])[:6], "nur_ausland": bool(g.get("nur_ausland"))}
                                   for g in welt["themen"][:5]]}
    brief = common.read_json("briefing.json", {}) or {}
    if brief.get("abschnitte"):
        data["briefing"] = {"datum": brief.get("datum", ""), "ueberblick": _cut(brief.get("ueberblick"), 400),
                            "top": [_cut(p.get("text"), 220) for p in brief["abschnitte"][0]["punkte"][:5]]}
    radar, erl, mess = (common.read_json(n, {}) or {} for n in ("clip_radar.json", "clip_erlaubnis.json", "messung.json"))
    if radar or erl or mess:
        data["clipteam"] = {
            "creators": radar.get("creators", 0),
            "erlaubt": [_cut(c.get("name"), 40) for c in erl.get("creators", []) if c.get("status") == "erlaubt"][:8],
            "viral": [{"creator": _cut(v.get("creator"), 40), "titel": _cut(v.get("titel"), 90), "url": v.get("url", ""),
                       "je_stunde": v.get("aufrufe_je_stunde", 0)} for v in radar.get("videos", []) if v.get("erlaubt")][:3],
            "vorschlaege": len(radar.get("vorschlaege", [])),
            "kampagnen": len(radar.get("kampagnen", [])),
            "messung": {"posts": mess.get("anzahl", 0), "aufrufe": mess.get("gesamt_aufrufe", 0)}}
    for key in ("lernen", "wahrheit"):
        extra = _extra(key + ".json")
        if extra:
            data[key] = extra
    return data


def write() -> bool:
    data = build()
    if not data["status"]:
        return False                                   # noch keine Läufe: nichts veröffentlichen
    old = None
    try:
        old = json.loads(OUT.read_text("utf-8"))
    except (OSError, ValueError):
        pass
    if old is not None and common._strip(old) == common._strip(data):
        return False
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_BYTES:          # Auftragsfelder der Ideen zuerst weglassen
        for i in data["ideen"]:
            i["auftrag"] = None
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n", "utf-8")
    return True
