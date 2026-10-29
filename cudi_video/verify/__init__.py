"""Quellen-Abgleich: jeder Wert wird mit unabhängigen Quellen aus verschiedenen Ländern
und Gemeinschaften verglichen, bevor er ins Video kommt.

Status je Platz:
  bestätigt        – mindestens eine unabhängige Quelle stimmt mit dem Wert überein
  korrigiert       – mehrere unabhängige Quellen stimmen untereinander, aber nicht mit
                     Wikidata überein -> deren (neuerer) Wert wird verwendet
  widersprüchlich  – Quellen widersprechen sich ohne klare Mehrheit -> Mensch muss prüfen
  nur eine Quelle  – keine unabhängige Quelle verfügbar
"""

from __future__ import annotations

import logging
import statistics

from .. import net
from ..models import RankItem, Research
from ..spec import VideoSpec
from ..units import quantity
from .checkers import Evidence, FactCheckSearch, checkers_for

log = logging.getLogger(__name__)

# Erlaubte Abweichung zwischen Quellen. Bevölkerungszahlen sind Schätzungen mit
# unterschiedlichem Stichtag, Flächen werden je nach Gewässern leicht anders gezählt.
TOLERANCE = {"P1082": 0.05, "P2046": 0.01}
OUTDATED_YEARS = 1.5   # so viel älter als die neueste Quelle -> Wikidata-Wert gilt als veraltet
DEFAULT_TOLERANCE = 0.01

STATUS_OK = ("bestätigt", "korrigiert")

# Quellennamen je Sprache (intern werden die deutschen Namen als Schlüssel verwendet)
SOURCE_NAMES = {
    "Weltbank": {"de": "Weltbank", "en": "World Bank"},
    "CIA World Factbook": {"de": "CIA World Factbook", "en": "CIA World Factbook"},
    "OpenStreetMap": {"de": "OpenStreetMap", "en": "OpenStreetMap"},
    "Wikidata": {"de": "Wikidata", "en": "Wikidata"},
}


def source_label(name: str, lang: str) -> str:
    return SOURCE_NAMES.get(name, {}).get(lang, name)


def confirmed_sources(item: RankItem) -> list[str]:
    """Quellen, die den verwendeten Wert stützen – nur wenn der Abgleich erfolgreich war."""
    v = item.verification or {}
    return list(v.get("sources", [])) if v.get("status") in STATUS_OK else []


def compact_sources(sources: list[str], lang: str = "de") -> str:
    """['Weltbank', 'Wikipedia (ru)', 'Wikipedia (zh)'] -> 'Weltbank, Wikipedia (ru, zh)'"""
    plain = [source_label(s, lang) for s in sources if not s.startswith("Wikipedia (")]
    langs = [s[len("Wikipedia ("):-1] for s in sources if s.startswith("Wikipedia (")]
    if langs:
        plain.append(f"Wikipedia ({', '.join(langs)})")
    return ", ".join(plain)


def all_sources(research: Research, lang: str = "de") -> tuple[list[str], int]:
    """Alle Datenquellen mit Bestätigungen (ohne Wikipedia-Sprachen) + Anzahl Wikipedia-Sprachen."""
    names, langs = [], set()
    for item in research.items:
        for src in confirmed_sources(item) or ["Wikidata"]:
            if src.startswith("Wikipedia ("):
                langs.add(src)
            elif source_label(src, lang) not in names:
                names.append(source_label(src, lang))
    return names, len(langs)


def _rel_diff(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


def _years(date: str) -> float:
    y, m, *_ = (date + "-01").split("-")
    return int(y) + (int(m) - 1) / 12


def _spread(evidence: list[Evidence]) -> float:
    values = [e.value for e in evidence]
    return max(_rel_diff(a, b) for a in values for b in values)


def _newer_sources(evidence: list[Evidence], base_date: str | None) -> list[Evidence]:
    """Unabhängige Quellen mit deutlich neuerem Stichtag als der Wikidata-Wert."""
    if not base_date:
        return []
    return [e for e in evidence
            if e.source != "Wikidata" and e.value is not None and e.date
            and _years(e.date) - _years(base_date) >= OUTDATED_YEARS]


def evaluate(item: RankItem, evidence: list[Evidence], tolerance: float) -> dict:
    """Wertet die gesammelten Belege für einen Platz aus (ohne Netzwerk, gut testbar)."""
    base = item.value
    values = [e for e in evidence if e.value is not None]
    for e in values:
        e.agrees = _rel_diff(e.value, base) <= tolerance
    independent = [e for e in evidence if e.source != "Wikidata"]
    confirming = [e for e in independent if e.agrees]
    disagreeing = [e for e in independent if e.value is not None and e.agrees is False]

    status, new_value, new_date = "nur eine Quelle", None, None
    outliers: list[Evidence] = []
    base_date = next((e.date for e in evidence if e.source == "Wikidata" and e.date), item.value_date)
    current = _newer_sources(evidence, base_date)
    if len(current) >= 2 and _spread(current) <= tolerance:
        # Wikidata-Wert ist veraltet und neuere Quellen stimmen überein -> aktuellste Daten verwenden
        status = "korrigiert"
        disagreeing = current
        new_value = statistics.median(e.value for e in current)
        new_date = max(e.date for e in current)
        for e in current:
            e.agrees = True
    elif disagreeing and len(confirming) >= 2 * len(disagreeing):
        # klare Mehrheit: einzelne Ausreißer (z. B. Datenfehler einer Quelle) werden benannt, nicht übernommen
        status, outliers = "bestätigt", disagreeing
    elif disagreeing:
        dis_values = [e.value for e in disagreeing]
        spread_ok = _spread(disagreeing) <= tolerance
        confirming_values = [e for e in confirming if e.value is not None]
        if len(disagreeing) >= 2 and spread_ok and len(disagreeing) > len(confirming_values):
            status = "korrigiert"
            new_value = statistics.median(dis_values)
            dates = [e.date for e in disagreeing if e.date]
            new_date = max(dates) if dates else None
        else:
            status = "widersprüchlich"
    elif confirming:
        status = "bestätigt"

    sources = sorted({e.source for e in evidence if e.source == "Wikidata" or e.agrees}
                     if status != "korrigiert" else {e.source for e in disagreeing})
    return {
        "status": status,
        "original_value": base,
        "value": new_value if new_value is not None else base,
        "date": new_date,
        "sources": sources,                         # Quellen, die den verwendeten Wert stützen
        "n_sources": len(sources),
        "outliers": [e.source for e in outliers],
        "evidence": [e.to_dict() for e in evidence],
    }


def verify_item(spec: VideoSpec, item: RankItem, checkers) -> dict:
    """Belege sammeln, auswerten und bei Bedarf den Wert korrigieren."""
    evidence: list[Evidence] = []
    for checker in checkers:
        if not checker.applies(spec, item):
            continue
        try:
            evidence.extend(checker.check(spec, item))
        except (net.FetchError, KeyError, ValueError, TypeError) as exc:
            log.warning("%s für %s nicht verfügbar: %s", checker.name, item.qid, exc)
    result = evaluate(item, evidence, TOLERANCE.get(spec.source.property, DEFAULT_TOLERANCE))
    item.verification = result
    if result["status"] == "korrigiert":
        item.value = result["value"]
        item.value_date = result["date"] or item.value_date
    return result


def verify(spec: VideoSpec, research: Research, strict: bool = False) -> Research:
    checkers = checkers_for(spec)
    for item in research.items:
        result = verify_item(spec, item, checkers)
        name = item.labels.get("de") or item.labels.get("en") or item.qid
        if result["status"] == "korrigiert":
            old = quantity(result["original_value"], item.unit, spec.unit).display("de")
            new = quantity(result["value"], item.unit, spec.unit).display("de")
            research.warnings.append(
                f"{name}: Wikidata-Wert {old} ist veraltet oder weicht ab – verwendet: {new} ({', '.join(result['sources'])})")
        elif result["outliers"]:
            details = "; ".join(
                f"{e['source']}: {quantity(e['value'], item.unit, spec.unit).display('de')}"
                for e in result["evidence"] if e["source"] in result["outliers"])
            research.warnings.append(
                f"{name}: Ausreißer ignoriert ({details}) – {result['n_sources']} andere Quellen stimmen überein.")
        if result["status"] == "widersprüchlich":
            details = "; ".join(
                f"{e['source']}: {quantity(e['value'], item.unit, spec.unit).display('de')}"
                for e in result["evidence"] if e["value"] is not None)
            research.warnings.append(f"{name}: Quellen widersprechen sich ({details}) – bitte prüfen.")
        elif result["status"] == "nur eine Quelle":
            research.warnings.append(f"{name}: keine unabhängige Bestätigung gefunden (nur Wikidata).")

    # Korrigierte Werte können die Reihenfolge ändern.
    research.items.sort(key=lambda it: it.value, reverse=spec.source.order == "desc")
    for pos, it in enumerate(research.items, start=1):
        it.rank = pos

    search = FactCheckSearch()
    if search.available():
        for item in research.items:
            for hit in search.search(item.labels.get("de") or item.labels.get("en", ""), "de"):
                research.warnings.append(
                    f"Faktencheck-Treffer zu {item.labels.get('de')}: „{hit['claim']}“ – "
                    f"{hit['publisher']}: {hit['rating']} ({hit['url']})")

    if strict:
        bad = [it.labels.get("de", it.qid) for it in research.items
               if it.verification.get("status") not in STATUS_OK]
        if bad:
            raise RuntimeError("Strenger Modus: nicht ausreichend bestätigt: " + ", ".join(bad))
    return research
