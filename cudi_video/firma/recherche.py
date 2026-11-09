"""Firma-Mitarbeiter „Rechercheur“: recherchiert täglich die wichtigsten bestätigten Meldungen/Trends nach (suchen, Seiten lesen, Datum
und Eigentümer prüfen, abgleichen) -> firma_daten/recherche.json. Kein Claude-Verbrauch; Brave-Schlüssel optional (CUDI_BRAVE_API_KEY)."""

from __future__ import annotations

import time

from . import common

MAX_THEMEN = 3


def themen() -> list[str]:
    news = common.read_json("news.json", {}) or {}
    out = [m.get("titel", "") for m in news.get("meldungen", []) if m.get("status") == "bestätigt" and m.get("titel")]
    trends = (common.read_json("trends.json", {}) or {}).get("themen", [])
    out += [t.get("thema", "") for t in trends[:2] if t.get("thema")]
    seen, res = set(), []
    for t in out:
        if t.casefold() not in seen:
            seen.add(t.casefold())
            res.append(t)
    return res[:MAX_THEMEN]


def kompakt(e: dict) -> dict:
    return {"thema": e["frage"], "stand": e["stand"], "seiten_gelesen": e["seiten_gelesen"], "hinweise": e["hinweise"][:3],
            "aussagen": [{"text": a["text"][:240], "status": a["status"], "n_gruppen": a["n_gruppen"], "datum": a["neuestes_datum"],
                          "belege": [{"url": b["url"], "quelle": b["quelle"], "datum": b["datum"], "eigentuemer": b["eigentuemer"]}
                                     for b in a["belege"][:4]]} for a in e["aussagen"][:4]],
            "widersprueche": len([w for w in e["widersprueche"] if w["art"] == "widerspruch"]), "schritte": e["schritte"][:12]}


def run() -> dict:
    from .. import recherche

    started = time.monotonic()
    notes: list[str] = []
    ergebnisse = []
    for thema in themen():
        recherche.neuer_lauf()
        try:
            ergebnisse.append(kompakt(recherche.recherchiere(thema, "news", "de", max_seiten=4, llm=False)))
        except Exception as exc:                          # noqa: BLE001 – ein Thema darf ausfallen
            notes.append(f"{thema[:50]}: {common.short_error(exc)}")
    if not ergebnisse and not notes:
        notes.append("keine bestätigten Meldungen/Trends vorhanden – erst News-Reporter/Trend-Scout laufen lassen")
    best = sum(a["status"] == "bestaetigt" for r in ergebnisse for a in r["aussagen"])
    data = {"erzeugt": common.iso(), "hinweise": notes, "anzahl": len(ergebnisse), "bestaetigte_aussagen": best,
            "seiten_gelesen": sum(r["seiten_gelesen"] for r in ergebnisse), "ergebnisse": ergebnisse}
    changed = common.write_json("recherche.json", data)
    common.record_status("recherche", started, bool(ergebnisse),
                         f"{len(ergebnisse)} Themen, {data['seiten_gelesen']} Seiten gelesen, {best} bestätigte Aussagen"
                         + ("" if changed else " (unverändert)"), notes)
    return data
