"""Unabhängige Quellen, die einen Wert bestätigen oder ihm widersprechen können.

Jeder Prüfer liefert "Evidence": entweder einen eigenen Wert (Weltbank, Factbook,
OpenStreetMap) oder nur die Aussage, ob der Wert dort genannt wird (Wikipedia in
anderen Sprachen, Webseiten aus den Einzelnachweisen). Fällt eine Quelle aus, wird sie übersprungen.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup

from .. import config, net
from ..enrich import fetch_summary
from ..models import RankItem
from ..spec import VideoSpec
from ..units import quantity
from .numbers import UNIT_FACTORS, closest_unit_value, mentions_value, shifted_unit_value

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

    _cache_lock = threading.Lock()        # Faktencheck läuft parallel: Region-Cache nur nacheinander lesen/schreiben

    @classmethod
    def _regions(cls) -> dict:
        cache = config.CACHE_DIR / "factbook_regions.json"
        try:
            return json.loads(cache.read_text()) if cache.exists() else {}
        except ValueError:
            return {}

    @classmethod
    def _remember(cls, code: str, region: str) -> None:
        with cls._cache_lock:
            regions = cls._regions()
            regions[code] = region
            net._atomic_write(config.CACHE_DIR / "factbook_regions.json", json.dumps(regions).encode())

    def _load(self, fips: str) -> tuple[dict, str] | None:
        code = fips.lower()
        with self._cache_lock:
            regions = self._regions()
        order = ([regions[code]] if code in regions else []) + [r for r in self.REGIONS if r != regions.get(code)]
        for region in order:
            url = f"{self.BASE}/{region}/{code}.json"
            try:
                data = net.get_json(url, cache_hours=24 * 7, retries=0)
            except net.FetchError:
                continue
            if regions.get(code) != region:
                self._remember(code, region)
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
    MAX_FAILURES = 2                     # Overpass hängt öfter: danach in diesem Lauf überspringen
    _slot = threading.Semaphore(1)        # Overpass erlaubt nur wenige gleichzeitige Abfragen je Rechner
    _failures = [0]

    @classmethod
    def reset(cls) -> None:
        cls._failures[0] = 0

    def applies(self, spec, item):
        return spec.source.property in self.TAGS and self._failures[0] < self.MAX_FAILURES

    def check(self, spec, item):
        tag = self.TAGS[spec.source.property]
        query = f'[out:json][timeout:25];nwr["wikidata"="{item.qid}"];out tags 5;'
        with self._slot:
            if self._failures[0] >= self.MAX_FAILURES:
                return []
            try:
                data = net.get_json(config.OVERPASS_URL, params={"data": query}, cache_hours=24 * 7, retries=1,
                                    max_wait=10, timeout=30)
            except net.FetchError:
                self._failures[0] += 1
                raise
            self._failures[0] = 0
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
        # Erst die Einleitung, dann die Infobox (eine Anfrage mehr, nur wenn nötig). In der Infobox stehen
        # mehr Zahlen gleicher Einheit (Fallhöhe neben Meereshöhe) – daher dort ein engeres Fenster.
        texts = []
        for where, window, read in (("Einleitung", 0.3, lambda: text),
                                    ("Infobox", 0.15, lambda: fetch_lead_text(self.lang, item.wiki_titles[self.lang]))):
            source_text = read()
            texts.append(source_text)
            if symbol in UNIT_FACTORS:
                # Wert mit Einheit auslesen -> kann bestätigen ODER widersprechen
                found = closest_unit_value(source_text, q.value, symbol, window=window)
                if found is not None:
                    value, precision = found
                    return [Evidence(self.name, self.origin, url, value / q.unit.factor, None,
                                     note=f"{where}: {value:g} {symbol}", precision=precision / q.unit.factor)]
            elif mentions_value(source_text, q.value):
                return [Evidence(self.name, self.origin, url, None, None, agrees=True, note=where)]
        if symbol in UNIT_FACTORS:
            # Genau eine Zehnerpotenz daneben (111 m statt 1.112 m)? -> Kommafehler auf einer Seite
            shifted = shifted_unit_value(" ".join(texts), q.value, symbol)
            if shifted is not None:
                value, precision = shifted
                return [Evidence(self.name, self.origin, url, value / q.unit.factor, None,
                                 note=f"um Faktor 10 abweichend: {value:g} {symbol}", precision=precision / q.unit.factor)]
        return [Evidence(self.name, self.origin, url, None, None, agrees=None, note="Wert im Artikel nicht genannt")]


# --------------------------------------------------------------------------- Quellen außerhalb Wikipedias

def _domain(url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


class ExternalSourcesChecker(Checker):
    """Liest die Einzelnachweise/Weblinks des Wikipedia-Artikels und prüft den Wert auf den verlinkten Seiten
    selbst (Fachdatenbanken, Behörden, Lexika, Presse) – Wikipedia ist hier nur das Verzeichnis, nicht der Beleg.

    Eine Seite zählt nur als Bestätigung, wenn sie den Wert (mit Einheit) nennt. Nennt sie einen anderen Wert,
    wird das im Prüfbericht vermerkt, aber nicht als Widerspruch gewertet: Webseiten nennen oft Zahlen anderer
    Bauwerke, Teilstrecken oder ältere Stände."""

    name = "Web"
    origin = "unabhängige Quelle außerhalb Wikipedias"
    LANGS = ("en", "de")
    MAX_PAGES = 6               # höchstens so viele Seiten je Platz laden
    MAX_DOMAINS = 2             # so viele bestätigende Websites reichen
    TIMEOUT = 10
    TOLERANCE = 0.002           # Webseite muss den Wert fast genau nennen (sonst eigene Rundung als Toleranz)
    SKIP = re.compile(r"(wikipedia|wikimedia|wikidata|wiktionary|wikisource|wikivoyage|archive\.org|archive\.(today|is|ph)"
                      r"|google\.|facebook\.|twitter\.|(^|\.)x\.com$|instagram\.|youtube\.|youtu\.be|tiktok\.|linkedin\."
                      r"|doi\.org|jstor\.org|worldcat\.org|openstreetmap\.|viaf\.org|d-nb\.info|id\.loc\.gov|isni\.org"
                      r"|bnf\.fr|wmflabs|toolforge|geohack|amazon\.|ebay\.|flickr\.|pinterest\.|reddit\.|imdb\.com"
                      r"|semanticscholar|handle\.net|ncbi\.nlm|pubmed|archive-it)", re.I)
    PREFERRED = ("skyscrapercenter.com", "ctbuh.org", "emporis", "peakbagger.com", "britannica.com", ".gov", "gov.",
                 "structurae", "summitpost.org", "highbridge", "unesco.org", "nationalgeographic", "guinnessworldrecords",
                 "worldatlas.com", "bbc.", "reuters.com", "nytimes.com", "spiegel.de", "zeit.de", "faz.net")

    def applies(self, spec, item):
        return any(lang in item.wiki_titles for lang in self.LANGS)

    @classmethod
    def links(cls, item: RankItem) -> list[str]:
        """Verlinkte Webseiten der Artikel (en, de), bevorzugte Fachquellen zuerst, je Website nur eine."""
        urls: list[str] = []
        for lang in cls.LANGS:
            title = item.wiki_titles.get(lang)
            if not title:
                continue
            try:
                data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php",
                                    params={"action": "query", "prop": "extlinks", "titles": title, "ellimit": 200,
                                            "redirects": 1, "format": "json", "formatversion": 2},
                                    cache_hours=24, retries=1, max_wait=10)
            except net.FetchError:
                continue
            for page in data.get("query", {}).get("pages", []):
                urls += [link.get("url", "") for link in page.get("extlinks", [])]
        seen, out = set(), []
        for url in urls:
            if url.startswith("//"):
                url = "https:" + url
            domain = _domain(url)
            if not url.startswith("http") or not domain or domain in seen or cls.SKIP.search(domain) \
                    or url.lower().split("?")[0].endswith((".pdf", ".jpg", ".png", ".zip", ".xls", ".xlsx")):
                continue
            seen.add(domain)
            out.append(url)
        return sorted(out, key=lambda u: not any(p in _domain(u) for p in cls.PREFERRED))

    @classmethod
    def page_text(cls, url: str) -> str:
        path = net.download(url, suffix=".html", retries=0, timeout=cls.TIMEOUT, max_wait=0)
        raw = path.read_bytes()[:3_000_000]
        soup = BeautifulSoup(raw, "lxml")
        for junk in soup.select("script, style, noscript, nav, footer"):
            junk.decompose()
        return soup.get_text(" ", strip=True)[:400_000]

    def check(self, spec, item):
        q = quantity(item.value, item.unit, spec.unit)
        symbol = q.unit.symbol if q.unit else ""
        out: list[Evidence] = []
        confirmed = 0
        for url in self.links(item)[: self.MAX_PAGES]:
            domain = _domain(url)
            try:
                text = self.page_text(url)
            except (net.FetchError, OSError, ValueError):
                continue
            source = f"Web: {domain}"
            if symbol in UNIT_FACTORS:
                found = closest_unit_value(text, q.value, symbol, window=0.15)
                if found is None:
                    continue
                value, precision = found
                if abs(value - q.value) <= max(self.TOLERANCE * abs(q.value), precision):
                    out.append(Evidence(source, self.origin, url, value / q.unit.factor, None,
                                        note=f"{value:g} {symbol}", precision=precision / q.unit.factor))
                    confirmed += 1
                else:
                    out.append(Evidence(source, self.origin, url, None, None, agrees=None,
                                        note=f"nennt {value:g} {symbol} – nicht gewertet"))
            elif mentions_value(text, q.value):
                out.append(Evidence(source, self.origin, url, None, None, agrees=True, note="Wert genannt"))
                confirmed += 1
            if confirmed >= self.MAX_DOMAINS:
                break
        return out


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


class RechercheChecker(Checker):
    """Aktuelle Werte aus dem Web (Recherche-Agent): sucht „<Objekt> <Thema>“, liest die Treffer und prüft den Wert nahe dem Objektnamen.
    Jede Seite bringt ihr Datum mit – bei Abweichung entscheidet der Abgleich (neuere unabhängige Quellen -> „korrigiert“, mit Datum).
    Nur für freie Themen (confirmed_only), höchstens MAX_ITEMS Objekte je Lauf; Wikipedia zählt hier nicht (kein fakten/geschichte-Bereich)."""

    name = "Recherche"
    origin = "aktuelle Webquelle (gelesen, datiert)"
    MAX_ITEMS = 4
    MAX_PAGES = 3
    _done = 0

    @classmethod
    def reset(cls) -> None:
        cls._done = 0

    def applies(self, spec, item):
        return bool(spec.confirmed_only) and self._done < self.MAX_ITEMS

    def check(self, spec, item):
        from .. import recherche
        from ..eigentuemer import host_von
        from ..recherche import lesen, wikipedia

        type(self)._done += 1
        label = item.labels.get("de") or item.labels.get("en") or next(iter(item.labels.values()), "")
        q = quantity(item.value, item.unit, spec.unit)
        symbol = q.unit.symbol if q.unit else ""
        if not label or symbol not in UNIT_FACTORS:
            return []
        recherche.neuer_lauf()
        title = (getattr(spec, "title", None) or {}).get("de", "") if isinstance(getattr(spec, "title", None), dict) else ""
        res = recherche.suche([f"{label} {title}".strip(), f"{label} {symbol}"], "de", None, "fakten")
        out: list[Evidence] = []
        for t in res["treffer"]:
            if wikipedia.ist_wikipedia(t["url"]) or len(out) >= self.MAX_PAGES:
                continue
            page = lesen.lese(t["url"])
            if not page["ok"]:
                continue
            low, pos = page["text"].casefold(), page["text"].casefold().find(label.casefold())
            if pos < 0:
                continue
            near = page["text"][max(0, pos - 300): pos + 500]
            found = closest_unit_value(near, q.value, symbol, window=0.3)
            if found is None:
                continue
            value, precision = found
            out.append(Evidence(f"Recherche: {host_von(t['url'])}", self.origin, page["url"], value / q.unit.factor, page["datum"],
                                note=f"{value:g} {symbol} (Seite vom {page['datum'] or 'unbekannt'}, {page['eigentuemer']})",
                                precision=precision / q.unit.factor))
        return out


def checkers_for(spec: VideoSpec, with_wikipedia: bool = True) -> list[Checker]:
    checkers: list[Checker] = [WikidataChecker(), WorldBankChecker(), FactbookChecker(), OSMChecker()]
    if with_wikipedia:
        checkers += [WikipediaLangChecker(lang) for lang in config.CHECK_LANGS]
    if config.CHECK_WEB:
        checkers.append(ExternalSourcesChecker())
        from .. import recherche
        if recherche.aktiv() and spec.confirmed_only:
            RechercheChecker.reset()
            checkers.append(RechercheChecker())
    return checkers
