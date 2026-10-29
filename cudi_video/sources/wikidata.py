"""Rankings aus Wikidata (SPARQL). Pro Objekt wird der aktuellste gültige Wert verwendet."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote

from .. import net
from ..models import RankItem, Research
from ..spec import VideoSpec, WikidataSource
from ..units import fmt_number, quantity

log = logging.getLogger(__name__)

ENDPOINT = "https://query.wikidata.org/sparql"
CANDIDATE_LIMIT = 500

# Qualifikator "verwendetes Kriterium" (P1013) bei Höhen: architektonische Höhe ist der
# internationale Standard für Gebäude-Rankings, Antennen-/Spitzen-Höhen werden gemieden.
CRITERION_SCORE = {
    "Q24192182": 1,    # architektonische Höhe
    "Q26970842": -1,   # Höhe bis zur Spitze (inkl. Antenne)
    "Q31271474": -1,   # Höhe des obersten Geschosses
}

# Immer ausschließen: Objekte, die es (so) nicht gibt oder nicht mehr gibt.
DEFAULT_EXCLUDE = [
    "Q105821051",  # nie gebautes Bauwerk
    "Q1570262",    # unvollendetes Gebäude
    "Q12377751",   # im Bau
    "Q811683",     # geplantes Bauwerk
    "Q15720793",   # fiktives Gebäude
    "Q3895768",    # fiktiver Ort
    "Q19860854",   # zerstörtes Bauwerk
    "Q96084375",   # ehemaliges Bauwerk
    "Q55965244",   # Urzeitsee
    "Q47486890",   # ehemaliger See
    "Q1140477",    # subglazialer See (Werte stark unsicher)
]
MAX_EXTRA_VALUES = 3


def _sparql(query: str, cache_hours: float = 6.0, retry_on=net.RETRY_STATUSES) -> list[dict]:
    data = net.get_json(
        ENDPOINT,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        cache_hours=cache_hours,
        timeout=90,
        retries=5,
        max_wait=90,   # Wikidata begrenzt Rechenzeit pro Minute -> bei 429 geduldig warten
        retry_on=retry_on,
    )
    return data["results"]["bindings"]


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


# Eigenschaften mit Einheit: der normalisierte Wert (psn:, SI-Einheit) reicht und ist schneller.
UNIT_PROPERTIES = {"P2044", "P2048", "P2046", "P4511", "P2043", "P2049", "P2386", "P2120", "P2067", "P2052"}


def _value_pattern(p: str) -> list[str]:
    if p in UNIT_PROPERTIES:
        return [f"  ?st psn:{p} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ] ."]
    return [  # z. B. Einwohner: ohne Einheit gibt es oft keinen normalisierten Wert
        f"  {{ ?st psn:{p} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ] }}",
        f"  UNION {{ FILTER NOT EXISTS {{ ?st psn:{p} [] }}",
        f"          ?st psv:{p} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ] }}",
    ]


def build_ranking_query(src: WikidataSource, limit: int = CANDIDATE_LIMIT) -> str:
    """Alle (nicht veralteten) Aussagen zur Eigenschaft, sortiert nach Wert.

    Es werden Aussagen statt Objekte geholt, damit pro Objekt später die neueste bzw. passendste
    ausgewählt werden kann. Mengen werden, wo möglich, in SI-Einheiten normalisiert (psn:).
    Die Reihenfolge der Bedingungen überlässt Wikidata dem eigenen Optimierer (gemessen: schneller
    als jede erzwungene Reihenfolge).
    """
    p = src.property
    instance = "wdt:P31/wdt:P279*" if src.subclasses else "wdt:P31"
    classes = " ".join(f"wd:{c}" for c in dict.fromkeys([src.cls, *src.extra_classes]))
    region: list[str] = []
    if src.country:
        region.append(f"  ?item wdt:P17 wd:{src.country} .")
    for i, (path, qids) in enumerate(src.where.items()):
        sparql_path = "/".join("wdt:" + part for part in path.split("/"))
        if isinstance(qids, str):
            region.append(f"  ?item {sparql_path} wd:{qids} .")
        else:
            values = " ".join(f"wd:{q}" for q in qids)
            region.append(f"  VALUES ?where{i} {{ {values} }} ?item {sparql_path} ?where{i} .")
    lines = [
        "SELECT ?item ?value ?unit ?rank ?date ?criterion WHERE {",
        f"  VALUES ?cls {{ {classes} }}",
        f"  ?item {instance} ?cls .",
        *region,
        f"  ?item p:{p} ?st .",
        "  ?st wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)",
        *_value_pattern(p),
        "  OPTIONAL { ?st pq:P585 ?date }",
        "  OPTIONAL { ?st pq:P1013 ?criterion }",
    ]
    lines += _filter_lines(src)
    direction = "DESC" if src.order == "desc" else "ASC"
    lines.append(f"}} ORDER BY {direction}(?value) LIMIT {int(limit)}")
    return "\n".join(lines)


def _filter_lines(src: WikidataSource) -> list[str]:
    lines = []
    for prop in src.require_props:
        lines.append(f"  FILTER EXISTS {{ ?item wdt:{prop} [] }}")
    if src.require_any:
        alternatives = " UNION ".join(f"{{ ?item wdt:{prop} [] }}" for prop in src.require_any)
        lines.append(f"  FILTER EXISTS {{ {alternatives} }}")
    excluded = " ".join(f"wd:{c}" for c in dict.fromkeys([*DEFAULT_EXCLUDE, *src.exclude_classes]))
    lines.append(f"  FILTER NOT EXISTS {{ ?item wdt:P31 ?excluded . VALUES ?excluded {{ {excluded} }} }}")
    # auch über den Nutzungszustand (P5817): im Bau, geplant, zerstört …
    lines.append(f"  FILTER NOT EXISTS {{ ?item wdt:P5817 ?state . VALUES ?state {{ {excluded} }} }}")
    # nur Objekte auf der Erde (kein Olympus Mons & Co.)
    lines.append("  FILTER NOT EXISTS { ?item wdt:P376 ?body . FILTER(?body != wd:Q2) }")
    for prop in src.exclude_props:
        lines.append(f"  FILTER NOT EXISTS {{ ?item wdt:{prop} [] }}")
    if src.min_sitelinks:
        lines.append(f"  ?item wikibase:sitelinks ?sitelinks . FILTER(?sitelinks >= {int(src.min_sitelinks)})")
    if src.exclude_ended:
        lines.append("  FILTER NOT EXISTS { ?item wdt:P576 [] }")
    if src.min_value is not None:
        lines.append(f"  FILTER(?value >= {float(src.min_value)})")
    if src.max_value is not None:
        lines.append(f"  FILTER(?value <= {float(src.max_value)})")
    return lines


# --------------------------------------------------------------------------- Ausweichroute

SEARCH_API = "https://www.wikidata.org/w/api.php"
SEARCH_MAX_OFFSET = 2_000   # die 2.000 meistverlinkten Kandidaten genügen (Top-Objekte sind gut verlinkt)
BATCH = 300


class QueryTooHeavy(net.FetchError):
    pass


def _countries_in(continents: list[str]) -> list[str]:
    values = " ".join(f"wd:{q}" for q in continents)
    rows = _sparql(f"SELECT DISTINCT ?c WHERE {{ VALUES ?cont {{ {values} }} ?c wdt:P30 ?cont ; wdt:P31 wd:Q3624078 . }}",
                   cache_hours=24 * 7)
    return [_qid(r["c"]["value"]) for r in rows]


def _search_candidates(src: WikidataSource) -> list[str]:
    """Kandidaten über den Suchindex (haswbstatement) – schnell auch bei riesigen Klassen.

    Sortiert nach eingehenden Verweisen und begrenzt auf die meistverlinkten Treffer: bei sehr
    vielen Objekten (z. B. Seen in Schweden) bleiben die bekanntesten – und damit sicher die
    größten – dabei, und es sind nur wenige Anfragen nötig."""
    filters: list[str] = []
    if src.country:
        filters.append(f"haswbstatement:P17={src.country}")
    for path, qids in src.where.items():
        qid_list = [qids] if isinstance(qids, str) else list(qids)
        if path == "P17/P30":                      # Land liegt auf Kontinent -> Länder auflösen
            countries = _countries_in(qid_list)
            filters.append("haswbstatement:" + "|".join(f"P17={c}" for c in countries))
        elif "/" in path or "*" in path:
            raise QueryTooHeavy(
                "Wikidata ist für diese Abfrage gerade zu langsam. Bitte später erneut versuchen "
                "oder ein einzelnes Land wählen.")
        else:
            filters.append("haswbstatement:" + "|".join(f"{path}={q}" for q in qid_list))
    found: list[str] = []
    for cls in dict.fromkeys([src.cls, *src.extra_classes]):
        terms = [f"haswbstatement:P31={cls}", f"haswbstatement:{src.property}", *filters]
        offset = 0
        while offset < SEARCH_MAX_OFFSET:
            data = net.get_json(SEARCH_API, params={
                "action": "query", "list": "search", "srsearch": " ".join(terms), "srlimit": "500",
                "srnamespace": "0", "srprop": "", "sroffset": offset, "srsort": "incoming_links_desc",
                "format": "json",
            }, cache_hours=6, retries=4, max_wait=30)
            found += [hit["title"] for hit in data.get("query", {}).get("search", [])]
            if "continue" not in data:
                break
            offset = data["continue"]["sroffset"]
    return list(dict.fromkeys(q for q in found if re.fullmatch(r"Q\d+", q)))


def _statements_for(src: WikidataSource, qids: list[str]) -> list[dict]:
    """Aussagen zur Eigenschaft für eine feste Liste von Objekten (in kleinen Paketen)."""
    rows: list[dict] = []
    for i in range(0, len(qids), BATCH):
        values = " ".join(f"wd:{q}" for q in qids[i:i + BATCH])
        query = "\n".join([
            "SELECT ?item ?value ?unit ?rank ?date ?criterion WHERE {",
            f"  VALUES ?item {{ {values} }}",
            f"  ?item p:{src.property} ?st .",
            "  ?st wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)",
            *_value_pattern(src.property),
            "  OPTIONAL { ?st pq:P585 ?date }",
            "  OPTIONAL { ?st pq:P1013 ?criterion }",
            *_filter_lines(src),
            "}",
        ])
        rows += _sparql(query)
    return rows


def _ranking_bindings(src: WikidataSource, fresh: bool) -> list[dict]:
    """Hauptabfrage; bei Zeitüberschreitung Ausweichroute über den Suchindex."""
    try:
        # Bei Zeitüberschreitung (5xx) nicht dieselbe schwere Abfrage wiederholen, nur bei Drosselung (429)
        return _sparql(build_ranking_query(src), cache_hours=0 if fresh else 6.0, retry_on=(429,))
    except net.FetchError as exc:
        if not re.search(r"HTTP 5\d\d|timed out|Read timed out", str(exc)):
            raise
        log.warning("Wikidata-Abfrage zu langsam (%s) – nutze den Suchindex als Ausweichroute", exc)
    qids = _search_candidates(src)
    log.info("Suchindex: %d Kandidaten", len(qids))
    return _statements_for(src, qids)


def pick_latest(bindings: list[dict]) -> dict[str, RankItem]:
    """Pro Objekt eine Aussage wählen: neuester Stichtag, dann bevorzugter Rang, dann Kriterium
    (architektonische Höhe vor Antennenhöhe). Gleichwertige andere Werte landen in `alternatives`."""
    best: dict[str, tuple[tuple, RankItem]] = {}
    ties: dict[str, set[float]] = {}
    for b in bindings:
        qid = _qid(b["item"]["value"])
        date = b.get("date", {}).get("value", "")[:10] or None
        preferred = b["rank"]["value"].endswith("PreferredRank")
        criterion = CRITERION_SCORE.get(_qid(b["criterion"]["value"]), 0) if "criterion" in b else 0
        key = (date or "", preferred, criterion)
        value = float(b["value"]["value"])
        item = RankItem(qid=qid, value=value, unit=_qid(b["unit"]["value"]), value_date=date)
        if qid not in best or key > best[qid][0]:
            best[qid] = (key, item)
            ties[qid] = {value}
        elif key == best[qid][0]:
            ties[qid].add(value)
    out = {}
    for qid, (_, item) in best.items():
        item.alternatives = sorted(v for v in ties[qid] if v != item.value)
        out[qid] = item
    return out


def _details(qids: list[str], langs: list[str], image_prop: str = "P18") -> dict[str, dict]:
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
        f"SELECT ?item ?img ?photo ?built {' '.join(selects)} WHERE {{",
        f"  VALUES ?item {{ {values} }}",
        "  OPTIONAL { ?item wdt:P1619|wdt:P571 ?built }",
        f"  OPTIONAL {{ ?item wdt:{image_prop} ?img }}",
        "  OPTIONAL { ?item wdt:P18 ?photo }",
        *opts,
        "}",
    ])
    out: dict[str, dict] = {}
    for b in _sparql(query):
        qid = _qid(b["item"]["value"])
        if qid in out:
            continue
        row = {"labels": {}, "descriptions": {}, "wiki_titles": {}, "image_file": None, "image_kind": "photo",
               "built": "built" in b}
        if "img" in b:
            row["image_file"] = unquote(b["img"]["value"].rsplit("/", 1)[-1])
            row["image_kind"] = "flag" if image_prop == "P41" else "photo"
        elif "photo" in b:                                # Rückfall: normales Foto
            row["image_file"] = unquote(b["photo"]["value"].rsplit("/", 1)[-1])
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
    # Wikipedia-Titel sind die gebräuchlichen Namen ("China" statt "Volksrepublik China").
    title_opts = [
        f"  OPTIONAL {{ ?vw_{lang} schema:about ?v ; schema:isPartOf <https://{lang}.wikipedia.org/> ; "
        f"schema:name ?vt_{lang} }}" for lang in langs
    ]
    names = " ".join(f"?vl_{l} ?vt_{l}" for l in langs)
    query = "\n".join([
        f"SELECT ?item ?key ?v {names} WHERE {{",
        f"  VALUES ?item {{ {values} }}",
        "\n  UNION\n".join(unions),
        *label_opts,
        *title_opts,
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
            else:
                text = display_name(b.get(f"vt_{lang}", {}).get("value"), lang) or b.get(f"vl_{lang}", {}).get("value")
                if not text:
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
    union_sites = (f"  UNION {{ ?article schema:about ?item ; schema:isPartOf ?site ; schema:name ?title . "
                   f"FILTER(?site IN ({sites})) }}") if check_langs else ""
    query = "\n".join([
        "SELECT ?item ?iso3 ?fips ?site ?title WHERE {",
        f"  VALUES ?item {{ {values} }}",
        "  { ?item wdt:P298 ?iso3 } UNION { ?item wdt:P901 ?fips }",
        union_sites,
        "}",
    ])
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


def candidate_buffer(count: int) -> int:
    """Wie viele Kandidaten zusätzlich geprüft werden (z. B. 5 bei einer Top 10)."""
    return max(3, count // 2)


# Gebräuchliche Kurzformen, wie sie auch Nachrichtensendungen verwenden.
COMMON_NAMES = {"de": {"Volksrepublik China": "China", "Vereinigte Staaten": "USA"}}


def display_name(title: str | None, lang: str | None = None) -> str | None:
    """'Victoria Island (Canada)' -> 'Victoria Island', 'Volksrepublik China' -> 'China'."""
    if not title:
        return None
    name = re.sub(r"\s*\([^)]*\)$", "", title).strip()
    return COMMON_NAMES.get(lang, {}).get(name, name) or None


def fetch_item_value(qid: str, prop: str) -> RankItem | None:
    """Aktuellsten Wert einer Eigenschaft für ein einzelnes Objekt (z. B. Vergleichsobjekt)."""
    query = "\n".join([
        "SELECT ?item ?value ?unit ?rank ?date WHERE {",
        f"  VALUES ?item {{ wd:{qid} }}",
        f"  ?item p:{prop} ?st .",
        "  ?st wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)",
        f"  {{ ?st psn:{prop} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ] }}",
        f"  UNION {{ FILTER NOT EXISTS {{ ?st psn:{prop} [] }}",
        f"          ?st psv:{prop} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ] }}",
        "  OPTIONAL { ?st pq:P585 ?date }",
        "}",
    ])
    return pick_latest(_sparql(query, cache_hours=24)).get(qid)


def fetch_ranking(spec: VideoSpec, fresh: bool = False) -> Research:
    src = spec.source
    langs = list(dict.fromkeys([*spec.langs, "en"]))
    query = build_ranking_query(src)
    log.info("Wikidata-Abfrage: Klasse %s, Eigenschaft %s", src.cls, src.property)
    bindings = _ranking_bindings(src, fresh)
    candidates = pick_latest(bindings)
    ordered = sorted(candidates.values(), key=lambda it: it.value, reverse=src.order == "desc")

    # Mehr Kandidaten als nötig holen: Objekte ohne Namen in allen Sprachen fallen weg.
    # Puffer: einige Kandidaten mehr holen – der Quellen-Abgleich kann Werte korrigieren und damit
    # die Reihenfolge ändern; gekürzt wird erst danach (siehe verify()).
    wanted = spec.count + candidate_buffer(spec.count)
    pool = ordered[: wanted * 2]
    details = _details([it.qid for it in pool], langs, spec.image_prop)
    items: list[RankItem] = []
    for it in pool:
        d = details.get(it.qid)
        names = {lang: display_name(d["wiki_titles"].get(lang), lang) or d["labels"].get(lang) for lang in langs} if d else {}
        if not d or not all(names.get(lang) for lang in spec.langs):
            log.info("Überspringe %s (kein Name in allen Sprachen)", it.qid)
            continue
        # Anzeigename: Titel des Wikipedia-Artikels (gepflegter als Wikidata-Bezeichnungen), sonst Bezeichnung
        it.labels = {lang: name for lang, name in names.items() if name}
        it.descriptions = d["descriptions"]
        it.wiki_titles, it.image_file, it.image_kind = d["wiki_titles"], d["image_file"], d["image_kind"]
        it.has_build_date = d["built"]
        items.append(it)
        if len(items) == wanted:
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
    if spec.source.property == "P2048" and spec.source.cls in ("Q11303", "Q18142", "Q41176"):
        for it in items:
            if it.has_build_date is False:
                warnings.append(f"{it.labels.get('de') or it.labels.get('en')}: kein Eröffnungs-/Baudatum in Wikidata – "
                                "bitte prüfen, ob das Gebäude fertiggestellt ist.")
    for a, b in zip(items, items[1:]):
        if a.value == b.value:
            shown = quantity(a.value, a.unit, spec.unit).display("de")
            warnings.append(f"Gleichstand: {a.labels.get('de') or a.labels.get('en')} und "
                            f"{b.labels.get('de') or b.labels.get('en')} ({shown}).")
    return warnings
