"""Unabhängige Quellen, die einen Wert bestätigen oder ihm widersprechen können.

Jeder Prüfer liefert "Evidence": entweder einen eigenen Wert (Weltbank, Factbook,
OpenStreetMap) oder nur die Aussage, ob der Wert dort genannt wird (Wikipedia in
anderen Sprachen). Fällt eine Quelle aus, wird sie übersprungen.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup

from .. import config, net
from ..enrich import fetch_summary
from ..models import RankItem
from ..spec import VideoSpec
from ..units import quantity
from .numbers import UNIT_FACTORS, closest_unit_value, mentions_value

log = logging.getLogger(__name__)


@dataclass
class Evidence:
    source: str                 # z. B. "Weltbank"
    origin: str                 # Herkunft, z. B. "internationale Organisation"
    url: str
    value: float | None = None  # in derselben Einheit wie RankItem.value (SI); None = nur Erwähnung
    date: str | None = None
    agrees: bool | None = None  # None = keine Aussage (z. B. Wert dort nicht erwähnt)
    note: str = ""
    precision: float = 0.0      # Rundungsgenauigkeit der Quelle (SI), z. B. 1e6 bei "2 sq km"

    def to_dict(self) -> dict:
        return asdict(self)


class Checker:
    name = ""
    origin = ""

    def applies(self, spec: VideoSpec, item: RankItem) -> bool:
        return True

    def check(self, spec: VideoSpec, item: RankItem) -> list[Evidence]:
        raise NotImplementedError


# --------------------------------------------------------------------------- Wikidata (Ausgangswert)

class WikidataChecker(Checker):
    name = "Wikidata"
    origin = "Wikimedia, weltweite Community"

    def check(self, spec, item):
        return [Evidence(self.name, self.origin, item.wikidata_url, item.value, item.value_date)]


# --------------------------------------------------------------------------- Weltbank

class WorldBankChecker(Checker):
    """World Bank Open Data – internationale Organisation, Daten der Statistikämter."""

    name = "Weltbank"
    origin = "internationale Organisation"
    INDICATORS = {"P2046": ("AG.SRF.TOTL.K2", 1e6), "P1082": ("SP.POP.TOTL", 1.0)}  # km² -> m²

    def applies(self, spec, item):
        return spec.source.property in self.INDICATORS and "iso3" in item.codes

    def check(self, spec, item):
        indicator, factor = self.INDICATORS[spec.source.property]
        url = f"https://api.worldbank.org/v2/country/{item.codes['iso3']}/indicator/{indicator}"
        data = net.get_json(url, params={"format": "json", "mrnev": 1}, cache_hours=24, retries=2, max_wait=10)
        rows = data[1] if isinstance(data, list) and len(data) > 1 and data[1] else []
        if not rows or rows[0].get("value") is None:
            return []
        row = rows[0]
        page = f"https://data.worldbank.org/indicator/{indicator}?locations={row['country']['id']}"
        value = float(row["value"])
        precision = factor if value.is_integer() else 0.0          # ganze km² -> auf 1 km² gerundet
        return [Evidence(self.name, self.origin, page, value * factor, f"{row['date']}-12-31", precision=precision)]


# --------------------------------------------------------------------------- CIA World Factbook

class FactbookChecker(Checker):
    """CIA World Factbook (US-Regierung, gemeinfrei) über den JSON-Spiegel factbook/factbook.json."""

    name = "CIA World Factbook"
    origin = "US-Regierung"
    BASE = "https://raw.githubusercontent.com/factbook/factbook.json/master"
    REGIONS = ["europe", "central-asia", "east-n-southeast-asia", "south-asia", "middle-east", "africa",
               "north-america", "central-america-n-caribbean", "south-america", "australia-oceania", "antarctica"]
    PROPS = {"P2046", "P1082"}

    def applies(self, spec, item):
        return spec.source.property in self.PROPS and "fips" in item.codes

    def _load(self, fips: str) -> tuple[dict, str] | None:
        code = fips.lower()
        cache = config.CACHE_DIR / "factbook_regions.json"
        regions = json.loads(cache.read_text()) if cache.exists() else {}
        order = ([regions[code]] if code in regions else []) + [r for r in self.REGIONS if r != regions.get(code)]
        for region in order:
            url = f"{self.BASE}/{region}/{code}.json"
            try:
                data = net.get_json(url, cache_hours=24 * 7, retries=0)
            except net.FetchError:
                continue
            regions[code] = region
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(regions))
            return data, url
        return None

    @staticmethod
    def _number(text: str) -> tuple[float, float] | None:
        """'2 sq km' -> (2, 1); '1.4 billion' -> (1.4e9, 1e8) – Wert und Rundungsgenauigkeit."""
        m = re.search(r"([\d,]+(?:\.(\d+))?)\s*(million|billion)?", text)
        if not m:
            return None
        scale = {"million": 1e6, "billion": 1e9}.get(m.group(3) or "", 1.0)
        decimals = len(m.group(2) or "")
        return float(m.group(1).replace(",", "")) * scale, 10 ** -decimals * scale

    def check(self, spec, item):
        loaded = self._load(item.codes["fips"])
        if not loaded:
            return []
        data, _ = loaded
        page = "https://www.cia.gov/the-world-factbook/countries/"
        if spec.source.property == "P2046":
            area = {k.strip(): v for k, v in data.get("Geography", {}).get("Area", {}).items()}
            text = area.get("total", {}).get("text", "")
            parsed = self._number(text)
            if not parsed or not parsed[0]:
                return []
            return [Evidence(self.name, self.origin, page, parsed[0] * 1e6, None, note=text, precision=parsed[1] * 1e6)]
        pop = data.get("People and Society", {}).get("Population", {})
        text = (pop.get("total") or {}).get("text") or pop.get("text", "")
        parsed = self._number(text)
        if not parsed or not parsed[0]:
            return []
        year = re.search(r"\((\d{4})", text)
        date = f"{year.group(1)}-07-01" if year else None
        return [Evidence(self.name, self.origin, page, parsed[0], date, note=text, precision=parsed[1])]


# --------------------------------------------------------------------------- OpenStreetMap

class OSMChecker(Checker):
    """OpenStreetMap – eigenständige, weltweite Kartografie-Community (Gebäude- und Berghöhen)."""

    name = "OpenStreetMap"
    origin = "weltweite Kartografie-Community"
    TAGS = {"P2048": "height", "P2044": "ele"}

    def applies(self, spec, item):
        return spec.source.property in self.TAGS

    def check(self, spec, item):
        tag = self.TAGS[spec.source.property]
        query = f'[out:json][timeout:25];nwr["wikidata"="{item.qid}"];out tags 5;'
        data = net.get_json(config.OVERPASS_URL, params={"data": query}, cache_hours=24 * 7, retries=1, max_wait=10)
        for el in data.get("elements", []):
            raw = el.get("tags", {}).get(tag, "")
            if not raw or re.search(r"ft|'|\"", raw):
                continue   # nur metrische Angaben
            m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(m)?\s*$", raw)
            if m:
                url = f"https://www.openstreetmap.org/{el['type']}/{el['id']}"
                return [Evidence(self.name, self.origin, url, float(m.group(1)), None, note=f"{tag}={raw}")]
        return []


# --------------------------------------------------------------------------- Wikipedia in anderen Sprachen

LANG_ORIGIN = {
    "fr": "französischsprachige Community", "es": "spanischsprachige Community",
    "ru": "russischsprachige Community", "ar": "arabischsprachige Community",
    "zh": "chinesischsprachige Community", "ja": "japanischsprachige Community",
    "pt": "portugiesischsprachige Community", "it": "italienischsprachige Community",
    "tr": "türkischsprachige Community", "hi": "hindisprachige Community", "ko": "koreanischsprachige Community",
}


def fetch_lead_text(lang: str, title: str) -> str:
    """Text des ersten Artikelabschnitts inklusive Infobox (dort stehen Fläche, Höhe, Tiefe …)."""
    data = net.get_json(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={"action": "parse", "page": title, "prop": "text", "section": 0, "redirects": 1,
                "disabletoc": 1, "format": "json", "formatversion": 2},
        cache_hours=24, retries=2, max_wait=15,
    )
    soup = BeautifulSoup(data.get("parse", {}).get("text", ""), "lxml")
    for junk in soup.select("sup.reference, style, script, .mw-editsection, .noprint"):
        junk.decompose()
    return soup.get_text(" ", strip=True)


class WikipediaLangChecker(Checker):
    """Liest den Wert (mit Einheit) aus einer Wikipedia-Sprachversion: zuerst aus der Einleitung,
    sonst aus der Infobox. Gefundene Werte können den Wikidata-Wert bestätigen oder ihm widersprechen."""

    def __init__(self, lang: str):
        self.lang = lang
        self.name = f"Wikipedia ({lang})"
        self.origin = LANG_ORIGIN.get(lang, f"Wikipedia-Community ({lang})")

    def applies(self, spec, item):
        return self.lang in item.wiki_titles

    def check(self, spec, item):
        text = item.summary.get(self.lang)
        if text is None:
            text = fetch_summary(self.lang, item.wiki_titles[self.lang]) or ""
            if text:
                item.summary[self.lang] = text   # nur Erfolge merken, damit später erneut versucht werden kann
        if not text:
            return []
        q = quantity(item.value, item.unit, spec.unit)
        url = item.wiki_url(self.lang) or ""
        symbol = q.unit.symbol if q.unit else ""
        # Erst die Einleitung, dann die Infobox (eine Anfrage mehr, nur wenn nötig)
        for where, read in (("Einleitung", lambda: text),
                            ("Infobox", lambda: fetch_lead_text(self.lang, item.wiki_titles[self.lang]))):
            source_text = read()
            if symbol in UNIT_FACTORS:
                # Wert mit Einheit auslesen -> kann bestätigen ODER widersprechen
                found = closest_unit_value(source_text, q.value, symbol)
                if found is not None:
                    value, precision = found
                    return [Evidence(self.name, self.origin, url, value / q.unit.factor, None,
                                     note=f"{where}: {value:g} {symbol}", precision=precision / q.unit.factor)]
            elif mentions_value(source_text, q.value):
                return [Evidence(self.name, self.origin, url, None, None, agrees=True, note=where)]
        return [Evidence(self.name, self.origin, url, None, None, agrees=None, note="Wert im Artikel nicht genannt")]


# --------------------------------------------------------------------------- Faktencheck-Plattformen

class FactCheckSearch:
    """Google Fact Check Tools: findet Prüfartikel von Faktencheck-Redaktionen weltweit
    (z. B. Correctiv, dpa, AFP, Snopes, Full Fact). Benötigt einen kostenlosen API-Schlüssel."""

    URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def available(self) -> bool:
        return bool(config.FACTCHECK_API_KEY)

    def search(self, query: str, lang: str = "de") -> list[dict]:
        try:
            data = net.get_json(self.URL, params={"query": query, "languageCode": lang, "pageSize": 5,
                                                  "key": config.FACTCHECK_API_KEY}, cache_hours=24, retries=1)
        except net.FetchError as exc:
            log.warning("Faktencheck-Suche fehlgeschlagen: %s", exc)
            return []
        hits = []
        for claim in data.get("claims", []):
            for review in claim.get("claimReview", [])[:1]:
                hits.append({
                    "claim": claim.get("text", "")[:200],
                    "publisher": review.get("publisher", {}).get("name", ""),
                    "rating": review.get("textualRating", ""),
                    "url": review.get("url", ""),
                })
        return hits


def checkers_for(spec: VideoSpec, with_wikipedia: bool = True) -> list[Checker]:
    checkers: list[Checker] = [WikidataChecker(), WorldBankChecker(), FactbookChecker(), OSMChecker()]
    if with_wikipedia:
        checkers += [WikipediaLangChecker(lang) for lang in config.CHECK_LANGS]
    return checkers
