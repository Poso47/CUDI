"""Studio-Lehrer (Bildlehrer): lernt aus den Lücken früherer Videos -> firma_daten/bildregeln.json.

Rohstoff ist `firma_daten/abgleich.json`: je Video-Abschnitt, was gesagt, aber nicht gezeigt wurde (gesammelt aus den
Läufen, `cudi_video.firma abgleich <datei>`). Der Lehrer zählt, was immer wieder fehlt, und macht daraus kurze Regeln.
Mit freiem Sprachmodell (Gemini über `CUDI_LLM_*`) wird für häufige Lücken ein konkreter Zeichen-Tipp mit den Bausteinen
formuliert; ohne Modell bleibt es bei der Regel aus der Zählung. Jede Regel trägt die Anzahl der Fälle als Beleg.
Die Szenen-Abteilung (`animation.anleitung`) hängt die wichtigsten Regeln an jede Aufgabe.
"""

from __future__ import annotations

import re
from collections import Counter

from . import common

MAX_ABSCHNITTE = 400
MAX_REGELN = 12
MIN_FAELLE = 2
_GRUND = {"satz": "Satz ohne eigenen Schritt", "wort": "gesagt, aber nicht gezeigt", "drehbuch": "Drehbuch-Wort fehlt in der Szene"}


def zusammenfuehren(neu: dict) -> int:
    """Lücken eines Laufs an firma_daten/abgleich.json anhängen (älteste fallen weg). Rückgabe: Anzahl neuer Abschnitte."""
    alt = common.read_json("abgleich.json", {"abschnitte": []}) or {"abschnitte": []}
    abschnitte = [dict(a, art=neu.get("art", "")) for a in (neu.get("abschnitte") or []) if isinstance(a, dict)]
    alt["abschnitte"] = (alt.get("abschnitte") or []) + abschnitte
    alt["abschnitte"] = alt["abschnitte"][-MAX_ABSCHNITTE:]
    common.write_json("abgleich.json", alt)
    return len(abschnitte)


def auswerten(abschnitte: list[dict]) -> tuple[Counter, Counter, int]:
    woerter, arten = Counter(), Counter()
    for a in abschnitte:
        for m in a.get("maengel") or []:
            w = re.search(r"„([^“]+)“ wird gesagt", m)
            if w:
                woerter[w.group(1).lower()] += 1
                arten["wort"] += 1
            elif m.startswith("Satz"):
                arten["satz"] += 1
            elif m.startswith("Drehbuch"):
                arten["drehbuch"] += 1
    return woerter, arten, len(abschnitte)


def regeln_aus(woerter: Counter, arten: Counter, gesamt: int, notes: list[str]) -> list[dict]:
    regeln = []
    if arten["satz"] >= MIN_FAELLE:
        regeln.append({"regel": f"In {arten['satz']} Abschnitten hatte ein Satz keinen eigenen Schritt: Gib JEDEM Satz mindestens einen "
                                "Schritt mit \"bei\" auf ein Wort genau dieses Satzes.", "faelle": arten["satz"]})
    if arten["drehbuch"] >= MIN_FAELLE:
        regeln.append({"regel": f"In {arten['drehbuch']} Fällen stand ein Wort im Drehbuch, aber nicht in der Szene: Lege für jeden "
                                "Drehbuch-Eintrag einen Schritt oder eine Beschriftung mit genau diesem \"bei\"-Wort an.",
                       "faelle": arten["drehbuch"]})
    haeufig = [(w, n) for w, n in woerter.most_common(20) if n >= MIN_FAELLE]
    tipps = _zeichen_tipps([w for w, _ in haeufig[:8]], notes)
    for w, n in haeufig:
        tipp = tipps.get(w)
        regeln.append({"regel": f"„{w}“ wurde {n}× gesagt, aber nicht gezeigt – " + (tipp or "immer als eigenes Element mit "
                       f"Beschriftung „{w}“ zeigen, beim Wort einblenden."), "faelle": n, "wort": w})
    regeln.sort(key=lambda r: -r["faelle"])
    return regeln[:MAX_REGELN]


def _zeichen_tipps(woerter: list[str], notes: list[str]) -> dict[str, str]:
    """Konkreter Zeichen-Tipp je Wort vom freien Sprachmodell (nur Bausteine, keine Fakten). Ausfall -> {}."""
    if not woerter:
        return {}
    try:
        from .. import llm

        if not llm.available():
            return {}
        antwort = llm.chat_json(
            "Du hilfst einem Erklärvideo-Studio. Die Animation kennt nur diese Bausteine: form (kreis, ei, tropfen, herz, quadrat, "
            "sechseck oder SVG-Pfad), schlauch, huelle, schale, kristalle, partikel, traube, pfeil, uhr, beschriftung, figur. "
            "Aktionen: erscheine, verschwinde, bewege, wachse, faerbe, fuelle, drehe, pulsiere, zoom. Antworte nur mit JSON.",
            "Für jedes Wort: ein Satz (höchstens 25 Wörter), wie man es mit den Bausteinen zeigt. "
            '{"tipps": {"wort": "Tipp"}}. Wörter: ' + ", ".join(woerter))
        tipps = antwort.get("tipps") if isinstance(antwort, dict) else None
        return {str(k).lower(): re.sub(r"\s+", " ", str(v))[:200] for k, v in (tipps or {}).items() if str(k).lower() in woerter}
    except Exception as exc:                                  # Tipp ist optional
        notes.append(f"Zeichen-Tipps nicht verfügbar: {common.short_error(exc)}")
        return {}


def figur_wuensche(abschnitte: list[dict]) -> list[dict]:
    """Welche Figuren das Storyboard am häufigsten vermisst hat -> Arbeitsliste der Figuren-Abteilung."""
    zaehler = Counter(str(w).strip().lower() for a in abschnitte for w in (a.get("figur_wuensche") or []) if str(w).strip())
    return [{"figur": w, "faelle": n} for w, n in zaehler.most_common(10)]


def run() -> dict:
    import time
    started = time.monotonic()
    notes: list[str] = []
    abschnitte = (common.read_json("abgleich.json", {"abschnitte": []}) or {}).get("abschnitte") or []
    woerter, arten, gesamt = auswerten(abschnitte)
    regeln = regeln_aus(woerter, arten, gesamt, notes)
    ohne = sum(1 for a in abschnitte if not a.get("maengel"))
    daten = {"stand": common.iso(), "abschnitte": gesamt, "ohne_luecke": ohne,
             "quote": round(ohne / gesamt, 3) if gesamt else None, "regeln": regeln,
             "figur_wuensche": figur_wuensche(abschnitte), "hinweise": notes}
    common.write_json("bildregeln.json", daten)
    common.record_status("bildlehrer", started, True, f"{len(regeln)} Regeln aus {gesamt} Abschnitten", notes)
    return {"summary": f"{len(regeln)} Regeln aus {gesamt} Abschnitten ({ohne} ohne Lücke)", "hinweise": notes}
