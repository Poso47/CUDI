"""Rankings aus Wikidata (SPARQL). Pro Objekt wird der aktuellste gültige Wert verwendet."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import unquote

from .. import net
from ..models import RankItem, Research
from ..spec import VideoSpec, WikidataSource
from ..units import fmt_number

log = logging.getLogger(__name__)

ENDPOINT = "https://query.wikidata.org/sparql"
CANDIDATE_LIMIT = 500
MAX_EXTRA_VALUES = 3


def _sparql(query: str, cache_hours: float = 6.0) -> list[dict]:
    data = net.get_json(
        ENDPOINT,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        cache_hours=cache_hours,
        timeout=90,
    )
    return data["results"]["bindings"]


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def build_ranking_query(src: WikidataSource, limit: int = CANDIDATE_LIMIT) -> str:
    """Alle (nicht veralteten) Aussagen zur Eigenschaft, sortiert nach Wert.

    Es werden Aussagen statt Objekte geholt, damit pro Objekt später die neueste
    ausgewählt werden kann. Mengen werden, wo möglich, in SI-Einheiten normalisiert (psn:).
    """
    p = src.property
    instance = "wdt:P31/wdt:P279*" if src.subclasses else "wdt:P31"
    lines = [
        "SELECT ?item ?value ?unit ?rank ?date WHERE {",
        f"  ?item {instance} wd:{src.cls} .",
        f"  ?item p:{p} ?st .",
        "  ?st wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)",
        f"  {{ ?st psn:{p} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ] }}",
        f"  UNION {{ FILTER NOT EXISTS {{ ?st psn:{p} [] }}",
        f"          ?st psv:{p} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ] }}",
        "  OPTIONAL { ?st pq:P585 ?date }",
    ]
    if src.country:
        lines.append(f"  ?item wdt:P17 wd:{src.country} .")
    for prop in src.require_props:
        lines.append(f"  FILTER EXISTS {{ ?item wdt:{prop} [] }}")
    for cls in src.exclude_classes:
        lines.append(f"  FILTER NOT EXISTS {{ ?item wdt:P31 wd:{cls} }}")
    if src.exclude_ended:
        lines.append("  FILTER NOT EXISTS { ?item wdt:P576 [] }")
    if src.min_value is not None:
        lines.append(f"  FILTER(?value >= {float(src.min_value)})")
    if src.max_value is not None:
        lines.append(f"  FILTER(?value <= {float(src.max_value)})")
    direction = "DESC" if src.order == "desc" else "ASC"
    lines.append(f"}} ORDER BY {direction}(?value) LIMIT {int(limit)}")
    return "\n".join(lines)


def pick_latest(bindings: list[dict]) -> dict[str, RankItem]:
    """Pro Objekt eine Aussage wählen: neuester Stichtag, dann bevorzugter Rang, dann erste."""
    best: dict[str, tuple[tuple, RankItem]] = {}
    for b in bindings:
        qid = _qid(b["item"]["value"])
        date = b.get("date", {}).get("value", "")[:10] or None
        preferred = b["rank"]["value"].endswith("PreferredRank")
        key = (date or "", preferred)
        item = RankItem(qid=qid, value=float(b["value"]["value"]), unit=_qid(b["unit"]["value"]), value_date=date)
        if qid not in best or key > best[qid][0]:
            best[qid] = (key, item)
    return {qid: item for qid, (_, item) in best.items()}


def _details(qids: list[str], langs: list[str]) -> dict[str, dict]:
    values = " ".join(f"wd:{q}" for q in qids)
    selects, opts = [], []
    for lang in langs:
        selects += [f"?l_{lang}", f"?d_{lang}", f"?w_{lang}"]
        opts += [
            f'  OPTIONAL {{ ?item rdfs:label ?l_{lang} FILTER(LANG(?l_{lang}) = "{lang}") }}',
            f'  OPTIONAL {{ ?item schema:description ?d_{lang} FILTER(LANG(?d_{lang}) = "{lang}") }}',
            f"  OPTIONAL {{ ?w_{lang} schema:about ?item ; schema:isPartOf <https://{lang}.wikipedia.org/> }}",
        ]
    query = "\n".join([
        f"SELECT ?item ?img {' '.join(selects)} WHERE {{",
        f"  VALUES ?item {{ {values} }}",
        "  OPTIONAL { ?item wdt:P18 ?img }",
        *opts,
        "}",
    ])
    out: dict[str, dict] = {}
    for b in _sparql(query):
        qid = _qid(b["item"]["value"])
        if qid in out:
            continue
        row = {"labels": {}, "descriptions": {}, "wiki_titles": {}, "image_file": None}
        if "img" in b:
            row["image_file"] = unquote(b["img"]["value"].rsplit("/", 1)[-1])
        for lang in langs:
            if f"l_{lang}" in b:
                row["labels"][lang] = b[f"l_{lang}"]["value"]
            if f"d_{lang}" in b:
                row["descriptions"][lang] = b[f"d_{lang}"]["value"]
            if f"w_{lang}" in b:
                row["wiki_titles"][lang] = unquote(b[f"w_{lang}"]["value"].rsplit("/wiki/", 1)[-1]).replace("_", " ")
        out[qid] = row
    return out


def _extras(qids: list[str], extras: dict[str, str], langs: list[str]) -> dict[str, dict[str, dict[str, str]]]:
    if not extras:
        return {}
    values = " ".join(f"wd:{q}" for q in qids)
    unions = []
    for key, prop in extras.items():
        unions.append(f'  {{ ?item wdt:{prop} ?v . BIND("{key}" AS ?key) }}')
    label_opts = [
        f'  OPTIONAL {{ ?v rdfs:label ?vl_{lang} FILTER(LANG(?vl_{lang}) = "{lang}") }}' for lang in langs
    ]
    query = "\n".join([
        f"SELECT ?item ?key ?v {' '.join(f'?vl_{l}' for l in langs)} WHERE {{",
        f"  VALUES ?item {{ {values} }}",
        "\n  UNION\n".join(unions),
        *label_opts,
        "}",
    ])
    # Mehrere Werte sammeln (z. B. Mount Everest: China und Nepal), Reihenfolge beibehalten.
    collected: dict[str, dict[str, dict[str, list[str]]]] = {}
    for b in _sparql(query):
        qid, key = _qid(b["item"]["value"]), b["key"]["value"]
        per_lang = collected.setdefault(qid, {}).setdefault(key, {})
        raw = b["v"]["value"]
        for lang in langs:
            datatype = b["v"].get("datatype", "")
            if datatype.endswith("dateTime"):
                text = raw.lstrip("+")[:4]
            elif datatype.endswith(("decimal", "integer", "double")):
                num = float(raw)
                text = fmt_number(num, lang, 0 if num.is_integer() else 1)
            elif f"vl_{lang}" in b:
                text = b[f"vl_{lang}"]["value"]
            else:
                continue
            values = per_lang.setdefault(lang, [])
            if text not in values:
                values.append(text)
    out: dict[str, dict[str, dict[str, str]]] = {}
    for qid, keys in collected.items():
        for key, per_lang in keys.items():
            texts = {}
            for lang, values in per_lang.items():
                if len(values) > MAX_EXTRA_VALUES:
                    values = values[:MAX_EXTRA_VALUES] + ["…"]
                texts[lang] = " / ".join(values)
            out.setdefault(qid, {})[key] = texts
    return out


def fetch_identifiers(items: list[RankItem], check_langs: list[str]) -> None:
    """Länder-Codes (für Weltbank/Factbook) und Artikel in weiteren Sprachen nachladen."""
    if not items:
        return
    values = " ".join(f"wd:{it.qid}" for it in items)
    sites = ", ".join(f"<https://{lang}.wikipedia.org/>" for lang in check_langs)
    query = "\n".join([
        "SELECT ?item ?iso3 ?fips ?site ?title WHERE {",
        f"  VALUES ?item {{ {values} }}",
        "  { ?item wdt:P298 ?iso3 } UNION { ?item wdt:P901 ?fips }",
        f"  UNION {{ ?article schema:about ?item ; schema:isPartOf ?site ; schema:name ?title . FILTER(?site IN ({sites})) }}",
        "}",
    ]) if check_langs else ""
    if not query:
        return
    by_qid = {it.qid: it for it in items}
    for b in _sparql(query, cache_hours=24):
        it = by_qid[_qid(b["item"]["value"])]
        if "iso3" in b:
            it.codes.setdefault("iso3", b["iso3"]["value"])
        if "fips" in b:
            it.codes.setdefault("fips", b["fips"]["value"])
        if "site" in b:
            lang = b["site"]["value"].split("//")[1].split(".")[0]
            it.wiki_titles.setdefault(lang, b["title"]["value"])


def fetch_ranking(spec: VideoSpec, fresh: bool = False) -> Research:
    src = spec.source
    langs = list(dict.fromkeys([*spec.langs, "en"]))
    query = build_ranking_query(src)
    log.info("Wikidata-Abfrage: Klasse %s, Eigenschaft %s", src.cls, src.property)
    bindings = _sparql(query, cache_hours=0 if fresh else 6.0)
    candidates = pick_latest(bindings)
    ordered = sorted(candidates.values(), key=lambda it: it.value, reverse=src.order == "desc")

    # Mehr Kandidaten als nötig holen: Objekte ohne Namen in allen Sprachen fallen weg.
    pool = ordered[: spec.count * 3]
    details = _details([it.qid for it in pool], langs)
    items: list[RankItem] = []
    for it in pool:
        d = details.get(it.qid)
        if not d or not all(lang in d["labels"] for lang in spec.langs):
            log.info("Überspringe %s (kein Name in allen Sprachen)", it.qid)
            continue
        it.labels, it.descriptions = d["labels"], d["descriptions"]
        it.wiki_titles, it.image_file = d["wiki_titles"], d["image_file"]
        items.append(it)
        if len(items) == spec.count:
            break

    extras = _extras([it.qid for it in items], src.extras, langs)
    for it in items:
        it.extras = extras.get(it.qid, {})
    # Platz 1 = bester Wert; im Video wird rückwärts gezählt.
    for pos, it in enumerate(items, start=1):
        it.rank = pos

    research = Research(
        spec_id=spec.id,
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        items=items,
        query=query,
    )
    return research


def check_consistency(spec: VideoSpec, research: Research) -> list[str]:
    """Warnungen für Dinge, die ein Mensch vor der Veröffentlichung prüfen sollte."""
    warnings = []
    items = research.items
    if len(items) < spec.count:
        warnings.append(f"Nur {len(items)} von {spec.count} Plätzen gefunden.")
    units = {it.unit for it in items}
    if len(units) > 1:
        warnings.append(f"Uneinheitliche Einheiten {sorted(units)} – Werte sind evtl. nicht vergleichbar.")
    years = sorted({int(it.value_date[:4]) for it in items if it.value_date})
    if years and years[-1] - years[0] >= 3:
        warnings.append(
            f"Werte stammen aus unterschiedlichen Jahren ({years[0]}–{years[-1]}). "
            "Die Reihenfolge kann sich mit neueren Daten ändern."
        )
    if spec.source.max_age_years and years:
        now = datetime.now(timezone.utc).year
        old = [it for it in items if it.value_date and now - int(it.value_date[:4]) > spec.source.max_age_years]
        for it in old:
            warnings.append(f"Wert für {it.labels.get('en', it.qid)} ist von {it.value_date[:4]} (älter als erlaubt).")
    for a, b in zip(items, items[1:]):
        if a.value == b.value:
            warnings.append(f"Gleichstand: {a.labels.get('en')} und {b.labels.get('en')} ({a.value}).")
    return warnings
