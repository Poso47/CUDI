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
        return [Evidence(self.name, self.origin, page, float(row["value"]) * factor, f"{row['date']}-12-31")]


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
    def _number(text: str) -> float | None:
        m = re.search(r"([\d,]+(?:\.\d+)?)\s*(million|billion)?", text)
        if not m:
            return None
        value = float(m.group(1).replace(",", ""))
        return value * {"million": 1e6, "billion": 1e9}.get(m.group(2) or "", 1.0)

    def check(self, spec, item):
        loaded = self._load(item.codes["fips"])
        if not loaded:
            return []
        data, _ = loaded
        page = "https://www.cia.gov/the-world-factbook/countries/"
        if spec.source.property == "P2046":
            area = {k.strip(): v for k, v in data.get("Geography", {}).get("Area", {}).items()}
            text = area.get("total", {}).get("text", "")
            value = self._number(text)
            return [Evidence(self.name, self.origin, page, value * 1e6, None, note=text)] if value else []
        pop = data.get("People and Society", {}).get("Population", {})
        text = (pop.get("total") or {}).get("text") or pop.get("text", "")
        value = self._number(text)
        year = re.search(r"\((\d{4})", text)
        date = f"{year.group(1)}-07-01" if year else None
        return [Evidence(self.name, self.origin, page, value, date, note=text)] if value else []


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


class WikipediaLangChecker(Checker):
    """Liest den Wert (mit Einheit) aus der Einleitung einer Wikipedia-Sprachversion.

    Gefundene Werte können den Wikidata-Wert bestätigen oder ihm widersprechen."""

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
        if symbol in UNIT_FACTORS:
            # Wert mit Einheit auslesen -> kann bestätigen ODER widersprechen
            found = closest_unit_value(text, q.value, symbol)
            if found is not None:
                si = found / q.unit.factor
                return [Evidence(self.name, self.origin, url, si, None, note=f"im Text: {found:g} {symbol}")]
        elif mentions_value(text, q.value):
            return [Evidence(self.name, self.origin, url, None, None, agrees=True)]
        return [Evidence(self.name, self.origin, url, None, None, agrees=None, note="Wert in der Einleitung nicht genannt")]


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
