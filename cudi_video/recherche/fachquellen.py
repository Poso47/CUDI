"""Fachquellen mit offener Schnittstelle (kein Schlüssel): Eurostat (monatliche Inflation), Weltbank (Kennzahlen je Land),
Europe PMC (Studien). Der Code formuliert den Text selbst aus den gelieferten Zahlen – Treffer tragen `text` (kein Seitenabruf nötig)."""

from __future__ import annotations

import re
from datetime import date

import requests

from . import cache, web

LAENDER = {  # Name (klein) -> (ISO2, Eurostat-Code oder None, deutscher Name, englischer Name)
    "deutschland": ("DE", "DE", "Deutschland", "Germany"), "germany": ("DE", "DE", "Deutschland", "Germany"),
    "österreich": ("AT", "AT", "Österreich", "Austria"), "austria": ("AT", "AT", "Österreich", "Austria"),
    "schweiz": ("CH", None, "Schweiz", "Switzerland"), "switzerland": ("CH", None, "Schweiz", "Switzerland"),
    "frankreich": ("FR", "FR", "Frankreich", "France"), "france": ("FR", "FR", "Frankreich", "France"),
    "italien": ("IT", "IT", "Italien", "Italy"), "italy": ("IT", "IT", "Italien", "Italy"),
    "spanien": ("ES", "ES", "Spanien", "Spain"), "spain": ("ES", "ES", "Spanien", "Spain"),
    "niederlande": ("NL", "NL", "Niederlande", "Netherlands"), "netherlands": ("NL", "NL", "Niederlande", "Netherlands"),
    "polen": ("PL", "PL", "Polen", "Poland"), "poland": ("PL", "PL", "Polen", "Poland"),
    "belgien": ("BE", "BE", "Belgien", "Belgium"), "portugal": ("PT", "PT", "Portugal", "Portugal"),
    "griechenland": ("GR", "EL", "Griechenland", "Greece"), "schweden": ("SE", "SE", "Schweden", "Sweden"),
    "großbritannien": ("GB", None, "Großbritannien", "United Kingdom"), "uk": ("GB", None, "Großbritannien", "United Kingdom"),
    "united kingdom": ("GB", None, "Großbritannien", "United Kingdom"),
    "usa": ("US", None, "USA", "United States"), "united states": ("US", None, "USA", "United States"),
    "china": ("CN", None, "China", "China"), "japan": ("JP", None, "Japan", "Japan"), "indien": ("IN", None, "Indien", "India"),
    "india": ("IN", None, "Indien", "India"), "brasilien": ("BR", None, "Brasilien", "Brazil"),
    "türkei": ("TR", None, "Türkei", "Turkey"), "kanada": ("CA", None, "Kanada", "Canada"),
}
INDIKATOREN = [  # (Muster, Kennung, Weltbank-Code, deutscher Name, englischer Name, Einheit)
    (r"inflation|teuerung|verbraucherpreis|\bcpi\b|preissteigerung", "inflation", "FP.CPI.TOTL.ZG",
     "Inflationsrate (Verbraucherpreise, Jahresänderung)", "inflation, consumer prices (annual %)", "%"),
    (r"arbeitslos|unemployment|erwerbslos", "arbeitslos", "SL.UEM.TOTL.ZS", "Arbeitslosenquote", "unemployment rate", "%"),
    (r"einwohner|bevölkerung|population", "bevoelkerung", "SP.POP.TOTL", "Bevölkerung", "population", ""),
    (r"\bbip\b|wirtschaftsleistung|\bgdp\b|bruttoinlandsprodukt", "bip", "NY.GDP.MKTP.CD", "Bruttoinlandsprodukt (US-Dollar)",
     "GDP (current US$)", "US-Dollar"),
    (r"lebenserwartung|life expectancy", "lebenserwartung", "SP.DYN.LE00.IN", "Lebenserwartung bei Geburt (Jahre)", "life expectancy", "Jahre"),
]
MONATSNAMEN = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_manr"
WELTBANK = "https://api.worldbank.org/v2/country/{land}/indicator/{code}"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def land_erkennen(anfrage: str):
    low = anfrage.lower()
    for name, v in LAENDER.items():
        if re.search(r"(?<![\wäöü])" + re.escape(name) + r"(?![\wäöü])", low):
            return v
    return None


def indikator_erkennen(anfrage: str):
    for muster, *rest in INDIKATOREN:
        if re.search(muster, anfrage.lower()):
            return tuple(rest)
    return None


def _zahl(x: float, nachkomma: int = 1) -> str:
    return f"{x:,.{nachkomma}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _json(url: str, params: dict | None = None):
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    if (hit := cache.lade("api", key, 6)) is not None:
        return hit
    r = requests.get(url, params=params, headers={"User-Agent": web.USER_AGENT}, timeout=20)
    r.raise_for_status()
    data = r.json()
    cache.speichere("api", key, data)
    return data


def eurostat_inflation(land, sprache: str = "de", abruf=None) -> list[dict]:
    """Neueste Jahresänderungsrate des harmonisierten Verbraucherpreisindex (HICP) je EU-Land."""
    if not land or not land[1]:
        return []
    since = f"{date.today().year - 1}-01"
    data = (abruf or _json)(EUROSTAT, {"geo": land[1], "coicop": "CP00", "unit": "RCH_A", "format": "JSON", "lang": "EN",
                                       "sinceTimePeriod": since})
    zeiten = (data.get("dimension") or {}).get("time", {}).get("category", {}).get("index", {})
    werte = data.get("value") or {}
    best = None
    for periode, idx in zeiten.items():
        v = werte.get(str(idx))
        if v is not None and (best is None or periode > best[0]):
            best = (periode, float(v))
    if not best:
        return []
    jahr, monat = best[0].split("-")[:2]
    name = land[2] if sprache == "de" else land[3]
    text = (f"Laut Eurostat (HICP, harmonisierter Verbraucherpreisindex) betrug die Inflationsrate in {name} im "
            f"{MONATSNAMEN[int(monat) - 1]} {jahr} {_zahl(best[1])} Prozent gegenüber dem Vorjahresmonat."
            if sprache == "de" else
            f"According to Eurostat (HICP), the inflation rate in {name} was {best[1]:.1f} percent in {jahr}-{monat} compared with the same month a year earlier.")
    letzter = (date(int(jahr), int(monat), 28) if int(monat) != 12 else date(int(jahr), 12, 28)).isoformat()
    return [{"url": f"https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_manr/default/table?lang=en&geo={land[1]}",
             "titel": f"Eurostat: HICP-Inflationsrate {name}, {jahr}-{monat}", "datum": letzter, "auszug": text, "text": text,
             "weg": "Eurostat-API", "daten": {"wert": best[1], "periode": best[0], "einheit": "%"}}]


def weltbank(land, ind, sprache: str = "de", abruf=None) -> list[dict]:
    if not land or not ind:
        return []
    _, code, name_de, name_en, einheit = ind
    data = (abruf or _json)(WELTBANK.format(land=land[0], code=code), {"format": "json", "mrnev": 1})
    rows = data[1] if isinstance(data, list) and len(data) > 1 else []
    row = next((r for r in rows if r.get("value") is not None), None)
    if not row:
        return []
    v, jahr = float(row["value"]), str(row["date"])
    name = land[2] if sprache == "de" else land[3]
    wert = f"{_zahl(v, 2 if einheit in ('%', 'Jahre') else 0)} {('Prozent' if einheit == '%' else einheit)}".strip()
    text = (f"Laut Weltbank (World Development Indicators) betrug die Kennzahl „{name_de}“ für {name} im Jahr {jahr}: {wert}."
            if sprache == "de" else f"According to the World Bank, {name_en} for {name} in {jahr} was {v:g}.")
    return [{"url": f"https://data.worldbank.org/indicator/{code}?locations={land[0]}", "titel": f"Weltbank: {name_de}, {name}, {jahr}",
             "datum": f"{jahr}-12-31", "auszug": text, "text": text, "weg": "Weltbank-API",
             "daten": {"wert": v, "periode": jahr, "einheit": einheit}}]


def europe_pmc(anfrage: str, n: int = 4, abruf=None) -> list[dict]:
    data = (abruf or _json)(EPMC, {"query": anfrage, "format": "json", "pageSize": n, "resultType": "core", "sort": "P_PDATE_D desc"})
    out = []
    for r in (data.get("resultList") or {}).get("result", [])[:n]:
        abstract = re.sub(r"<[^>]+>", " ", r.get("abstractText") or "")
        abstract = " ".join(abstract.split())
        if not r.get("title") or len(abstract) < 120:
            continue
        titel = " ".join(re.sub(r"<[^>]+>", " ", r["title"]).split())
        out.append({"url": f"https://europepmc.org/article/{r.get('source', 'MED')}/{r.get('id', '')}", "titel": titel,
                    "datum": r.get("firstPublicationDate"), "auszug": abstract[:300], "text": titel + ". " + abstract,
                    "weg": "Europe PMC"})
    return out


def finde(anfrage: str, sprache: str = "de", bereich: str | None = None) -> list[dict]:
    """Fachquellen, die zur Anfrage passen (Zahlen-Kennzahlen je Land, Studien). Jede Quelle einzeln abgesichert; leere Liste = nichts passt."""
    out: list[dict] = []
    land, ind = land_erkennen(anfrage), indikator_erkennen(anfrage)
    versuche = []
    if ind and ind[0] == "inflation" and land and land[1]:
        versuche.append(("Eurostat", lambda: eurostat_inflation(land, sprache)))
    if ind and land:
        versuche.append(("Weltbank", lambda: weltbank(land, ind, sprache)))
    if bereich in ("wissen", "wissenschaft", "medizin") or re.search(r"\bstudie\b|\bstudy\b|klinisch|clinical|therapie|wirkung von", anfrage, re.I):
        versuche.append(("Europe PMC", lambda: europe_pmc(anfrage)))
    for _, func in versuche:
        try:
            out += func()
        except Exception:                                      # noqa: BLE001 – Quelle weg = nächste
            continue
    return out
