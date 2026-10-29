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


def _close(a: Evidence, b_value: float, b_precision: float, tolerance: float) -> bool:
    """Gleich im Rahmen der Toleranz – oder der Rundungsgenauigkeit ("2 km²" passt zu 2,08 km²)."""
    allowed = max(tolerance * max(abs(a.value), abs(b_value)), max(a.precision, b_precision) / 2 * 1.001)
    return abs(a.value - b_value) <= allowed


def _clusters(values: list[Evidence], tolerance: float) -> list[list[Evidence]]:
    """Werte zu Gruppen zusammenfassen, die untereinander übereinstimmen."""
    groups: list[list[Evidence]] = []
    for e in sorted(values, key=lambda x: x.value):
        for group in groups:
            center = statistics.median(g.value for g in group)
            precision = max(g.precision for g in group)
            if _close(e, center, precision, tolerance):
                group.append(e)
                break
        else:
            groups.append([e])
    return groups


def evaluate(item: RankItem, evidence: list[Evidence], tolerance: float) -> dict:
    """Wertet die gesammelten Belege für einen Platz aus (ohne Netzwerk, gut testbar).

    Alle Werte werden zu übereinstimmenden Gruppen zusammengefasst; die größte Gruppe gewinnt.
    Enthält sie den Wikidata-Wert, ist er bestätigt (Abweichler gelten als Ausreißer). Gewinnt eine
    andere Gruppe mit mindestens zwei Quellen klar, wird ihr Wert übernommen (korrigiert)."""
    base = item.value
    wikidata = next((e for e in evidence if e.source == "Wikidata"), None)
    values = [e for e in evidence if e.value is not None]
    mentions = [e for e in evidence if e.value is None and e.agrees]      # Bestätigung ohne eigenen Wert

    status, new_value, new_date = "nur eine Quelle", None, None
    winner: list[Evidence] = []
    base_date = wikidata.date if wikidata and wikidata.date else item.value_date
    current = _newer_sources(evidence, base_date)
    if len(current) >= 2 and _spread(current) <= tolerance:
        # Wikidata-Wert ist veraltet und neuere Quellen stimmen überein -> aktuellste Daten verwenden
        status, winner = "korrigiert", current
        new_value = statistics.median(e.value for e in current)
        new_date = max(e.date for e in current)
    else:
        groups = _clusters(values, tolerance)
        base_group = next((g for g in groups if wikidata in g), [wikidata] if wikidata else [])

        def support(group):
            return len({e.source for e in group}) + (len(mentions) if group is base_group else 0)

        best = max(groups, key=support) if groups else []
        others = [g for g in groups if g is not best]
        clear = not others or support(best) > max(support(g) for g in others)
        if best is base_group or not groups:
            independent = [e for e in base_group if e.source != "Wikidata"] + mentions
            winner = base_group
            if independent and clear:
                status = "bestätigt"
            elif others:
                status = "widersprüchlich"
        elif clear and len({e.source for e in best}) >= 2:
            status, winner = "korrigiert", best
            new_value = statistics.median(e.value for e in best)
            dates = [e.date for e in best if e.date]
            new_date = max(dates) if dates else None
        else:
            status = "widersprüchlich"

    for e in values:                                  # für den Prüfbericht: passt zum verwendeten Wert?
        e.agrees = e in winner
    if status == "korrigiert":
        sources = sorted({e.source for e in winner if e.source != "Wikidata"})
    elif status == "widersprüchlich":
        sources = ["Wikidata"]
    else:
        sources = sorted({e.source for e in winner} | {e.source for e in mentions} | {"Wikidata"})
    outliers = [e for e in values if e not in winner and e.source != "Wikidata"] if status in STATUS_OK else []
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


def _collect(spec: VideoSpec, item: RankItem, checkers) -> list[Evidence]:
    evidence: list[Evidence] = []
    for checker in checkers:
        if not checker.applies(spec, item):
            continue
        try:
            evidence.extend(checker.check(spec, item))
        except (net.FetchError, KeyError, ValueError, TypeError) as exc:
            log.warning("%s für %s nicht verfügbar: %s", checker.name, item.qid, exc)
    return evidence


def _support(result: dict) -> tuple[int, int]:
    """Wie gut ist ein Wert belegt? (Status-Güte, Anzahl unabhängiger Bestätigungen)"""
    quality = {"bestätigt": 3, "korrigiert": 2, "nur eine Quelle": 1, "widersprüchlich": 0}[result["status"]]
    return quality, len([s for s in result["sources"] if s != "Wikidata"])


def verify_item(spec: VideoSpec, item: RankItem, checkers) -> dict:
    """Belege sammeln, auswerten und bei Bedarf den Wert korrigieren.

    Hat Wikidata mehrere gleichrangige Werte (z. B. zwei Höhen ohne Kennzeichnung), gewinnt
    der Wert, den die unabhängigen Quellen am besten bestätigen."""
    tolerance = TOLERANCE.get(spec.source.property, DEFAULT_TOLERANCE)
    candidates = [item.value, *item.alternatives]
    best = None
    for value in candidates:
        item.value = value
        evidence = _collect(spec, item, checkers)
        result = evaluate(item, evidence, tolerance)
        if best is None or _support(result) > _support(best[1]):
            best = (value, result)
    item.value, result = best
    if len(candidates) > 1:
        result["alternatives"] = [v for v in candidates if v != item.value]
    item.verification = result
    if result["status"] == "korrigiert":
        item.value = result["value"]
        item.value_date = result["date"] or item.value_date
    return result


def _warnings_for(spec: VideoSpec, item: RankItem, result: dict) -> list[str]:
    """Hinweise für den Prüfbericht zu einem Platz."""
    name = item.labels.get("de") or item.labels.get("en") or item.qid

    def show(value: float) -> str:
        return quantity(value, item.unit, spec.unit).display("de")

    def listing(evidence_filter) -> str:
        return "; ".join(f"{e['source']}: {show(e['value'])}" for e in result["evidence"] if evidence_filter(e))

    out = []
    if result.get("alternatives"):
        others = ", ".join(show(v) for v in result["alternatives"])
        out.append(f"{name}: Wikidata hat mehrere gleichrangige Werte ({others}) – gewählt wurde der am besten belegte.")
    status = result["status"]
    if status == "korrigiert":
        out.append(f"{name}: Wikidata-Wert {show(result['original_value'])} ist veraltet oder weicht ab – "
                   f"verwendet: {show(result['value'])} ({', '.join(result['sources'])})")
    elif status == "widersprüchlich":
        out.append(f"{name}: Quellen widersprechen sich ({listing(lambda e: e['value'] is not None)}) – bitte prüfen.")
    elif status == "nur eine Quelle":
        out.append(f"{name}: keine unabhängige Bestätigung gefunden (nur Wikidata).")
    elif result["outliers"]:
        out.append(f"{name}: Ausreißer ignoriert ({listing(lambda e: e['source'] in result['outliers'])}) – "
                   f"{result['n_sources']} andere Quellen stimmen überein.")
    return out


def verify(spec: VideoSpec, research: Research, strict: bool = False) -> Research:
    checkers = checkers_for(spec)
    notes: dict[str, list[str]] = {}
    for item in research.items:
        result = verify_item(spec, item, checkers)
        notes[item.qid] = _warnings_for(spec, item, result)

    # Korrigierte Werte können die Reihenfolge ändern – erst jetzt auf die gewünschte Anzahl kürzen.
    research.items.sort(key=lambda it: it.value, reverse=spec.source.order == "desc")
    dropped = research.items[spec.count:]
    research.items = research.items[:spec.count]
    for pos, it in enumerate(research.items, start=1):
        it.rank = pos
        research.warnings.extend(notes.get(it.qid, []))
    for it in dropped:
        if it.verification.get("status") == "korrigiert" or it.verification.get("alternatives"):
            research.warnings.append(f"{it.labels.get('de') or it.qid}: nach dem Abgleich nicht mehr in den Top "
                                     f"{spec.count} ({quantity(it.value, it.unit, spec.unit).display('de')}).")

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
