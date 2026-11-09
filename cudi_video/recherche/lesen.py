"""Eine Webseite lesen wie ein Mensch: Haupttext, Veröffentlichungs-/Änderungsdatum, Betreiber, Eigentümer, Seitentyp."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

from .. import eigentuemer
from . import cache, web

TEXT_MAX = 60_000
MONATE = {m: i + 1 for i, names in enumerate([
    ("januar", "jan", "january", "janvier", "enero"), ("februar", "feb", "february", "février", "febrero"),
    ("märz", "maerz", "mär", "mar", "march", "mars", "marzo"), ("april", "apr", "avril", "abril"),
    ("mai", "may", "mayo"), ("juni", "jun", "june", "juin", "junio"), ("juli", "jul", "july", "juillet", "julio"),
    ("august", "aug", "août", "agosto"), ("september", "sep", "sept", "septembre", "septiembre"),
    ("oktober", "okt", "oct", "october", "octobre", "octubre"), ("november", "nov", "novembre", "noviembre"),
    ("dezember", "dez", "dec", "december", "décembre", "diciembre")]) for m in names}
_MON = "|".join(sorted((re.escape(m) for m in MONATE), key=len, reverse=True))

META_PUB = ("article:published_time", "og:article:published_time", "datepublished", "date", "dc.date", "dc.date.issued",
            "dcterms.created", "dcterms.issued", "pubdate", "publishdate", "publish-date", "sailthru.date", "parsely-pub-date",
            "article.published", "citation_publication_date", "citation_date", "dc.date.created", "og:published_time")
META_MOD = ("article:modified_time", "og:updated_time", "datemodified", "last-modified", "dcterms.modified", "dc.date.modified",
            "og:article:modified_time", "revised", "article.updated")

BEHOERDE = re.compile(r"(^|\.)(bund\.de|bmwk\.de|bmf\.de|bmi\.bund\.de|destatis\.de|bundesbank\.de|bundestag\.de|bundesregierung\.de|"
                      r"arbeitsagentur\.de|rki\.de|umweltbundesamt\.de|dwd\.de|eur-lex\.europa\.eu|europa\.eu|ecb\.europa\.eu|"
                      r"who\.int|un\.org|oecd\.org|imf\.org|worldbank\.org|nasa\.gov|noaa\.gov|cdc\.gov|nih\.gov|census\.gov|"
                      r"bls\.gov|ons\.gov\.uk|insee\.fr|istat\.it|ine\.es|cbs\.nl|statistik\.at|bfs\.admin\.ch|admin\.ch|"
                      r"gov\.uk|gov|gouv\.fr|gob\.es|gov\.[a-z]{2})$")
STUDIE = re.compile(r"(^|\.)(pubmed\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov|europepmc\.org|arxiv\.org|doi\.org|nature\.com|"
                    r"sciencedirect\.com|springer\.com|thelancet\.com|bmj\.com|jamanetwork\.com|science\.org|plos\.org|"
                    r"researchgate\.net|semanticscholar\.org|biorxiv\.org|medrxiv\.org|cochranelibrary\.com|ssrn\.com|"
                    r"[a-z0-9-]+\.edu|uni-[a-z-]+\.de|[a-z-]+-uni\.de|ac\.uk)$")
FORUM = re.compile(r"(^|\.)(reddit\.com|quora\.com|stackexchange\.com|stackoverflow\.com|gutefrage\.net|forum\.[a-z.]+|"
                   r"x\.com|twitter\.com|facebook\.com|tiktok\.com|instagram\.com|youtube\.com|answers\.[a-z.]+)$")
BLOG = re.compile(r"(^|\.)(blogspot\.[a-z.]+|medium\.com|substack\.com|wordpress\.com|tumblr\.com|jimdo(site)?\.com|wixsite\.com|"
                  r"blog\.[a-z.]+|[a-z0-9-]+\.blog)$")


# --------------------------------------------------------------------------- Datum

def parse_datum(text) -> str | None:
    """Erstes lesbares Datum -> "JJJJ-MM-TT" (nur 1990 … morgen). Versteht ISO, 12.10.2026, 12. Oktober 2026, October 12, 2026."""
    s = " ".join(str(text or "").split())
    if not s:
        return None
    cands: list[tuple[int, int, int]] = []
    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", s):
        cands.append((int(m[1]), int(m[2]), int(m[3])))
    for m in re.finditer(r"(?<!\d)(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})(?!\d)", s):
        cands.append((int(m[3]), int(m[2]), int(m[1])))
    for m in re.finditer(r"(?<!\d)(\d{1,2})\.?\s+(" + _MON + r")\.?,?\s+(\d{4})(?!\d)", s, re.I):
        cands.append((int(m[3]), MONATE[m[2].lower()], int(m[1])))
    for m in re.finditer(r"\b(" + _MON + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})(?!\d)", s, re.I):
        cands.append((int(m[3]), MONATE[m[1].lower()], int(m[2])))
    if not cands:
        for m in re.finditer(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)", s):        # 10/12/2026 -> uneindeutig, nur wenn sicher
            a, b = int(m[1]), int(m[2])
            if a > 12 >= b:
                cands.append((int(m[3]), b, a))
            elif b > 12 >= a:
                cands.append((int(m[3]), a, b))
    limit = date.today() + timedelta(days=1)
    for y, mo, d in cands:
        try:
            dt = date(y, mo, d)
        except ValueError:
            continue
        if date(1990, 1, 1) <= dt <= limit:
            return dt.isoformat()
    return None


def parse_monat(text) -> str | None:
    """„im Oktober 2026“ / „October 2026“ / „2026-10“ -> "JJJJ-MM" (Bezugszeitraum einer Aussage)."""
    s = " ".join(str(text or "").split())
    m = re.search(r"\b(" + _MON + r")\.?\s+(\d{4})\b", s, re.I)
    if m and 1990 <= int(m[2]) <= date.today().year + 1:
        return f"{int(m[2]):04d}-{MONATE[m[1].lower()]:02d}"
    m = re.search(r"(?<!\d)(\d{4})-(\d{2})(?!\d|-\d)", s)
    if m and 1990 <= int(m[1]) <= date.today().year + 1 and 1 <= int(m[2]) <= 12:
        return f"{m[1]}-{m[2]}"
    return None


def _json_ld(soup) -> tuple[list[str], list[str]]:
    pub, mod = [], []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "datePublished" and isinstance(v, str):
                    pub.append(v)
                elif k in ("dateModified", "dateUpdated") and isinstance(v, str):
                    mod.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    for tag in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
        try:
            walk(json.loads(tag.string or tag.get_text() or ""))
        except ValueError:
            continue
    return pub, mod


def daten_finden(soup, text: str, header_modified: str = "") -> dict:
    """{"veroeffentlicht", "geaendert", "datum_quelle"}: Meta-Tags vor JSON-LD vor <time> vor Text vor HTTP-Header."""
    pub = mod = None
    src = ""
    metas = {}
    for m in soup.find_all("meta"):
        key = (m.get("property") or m.get("name") or m.get("itemprop") or m.get("http-equiv") or "").strip().lower()
        if key and m.get("content"):
            metas.setdefault(key, m["content"])
    for k in META_PUB:
        if k in metas and (d := parse_datum(metas[k])):
            pub, src = d, "meta"
            break
    for k in META_MOD:
        if k in metas and (d := parse_datum(metas[k])):
            mod, src = d, src or "meta"
            break
    if not (pub and mod):
        jp, jm = _json_ld(soup)
        if not pub:
            pub = next((d for d in map(parse_datum, jp) if d), None)
            src = src or ("json-ld" if pub else "")
        if not mod:
            mod = next((d for d in map(parse_datum, jm) if d), None)
            src = src or ("json-ld" if mod else "")
    if not (pub or mod):
        for t in soup.find_all("time"):
            d = parse_datum(t.get("datetime") or t.get_text(" "))
            if d:
                pub, src = d, "time-Tag"
                break
    if not (pub or mod):
        head = text[:3000]
        m = re.search(r"(Stand|Aktualisiert(?: am)?|Zuletzt aktualisiert|Updated|Last updated|Last modified|Veröffentlicht(?: am)?|"
                      r"Published(?: on)?|Erschienen am|Datum)\s*[:\-–]?\s*(.{0,40})", head, re.I)
        d = parse_datum(m[2]) if m else None
        d = d or parse_datum(head[:600])
        if d:
            pub, src = d, "Text"
    if not (pub or mod) and header_modified:
        try:
            from email.utils import parsedate_to_datetime
            mod = parsedate_to_datetime(header_modified).astimezone(timezone.utc).date().isoformat()
            src = "HTTP-Header"
        except (TypeError, ValueError):
            pass
    return {"veroeffentlicht": pub, "geaendert": mod, "datum_quelle": src}


def effektives_datum(info: dict) -> str | None:
    ds = [d for d in (info.get("veroeffentlicht"), info.get("geaendert")) if d]
    return max(ds) if ds else None


# --------------------------------------------------------------------------- Text, Typ

def haupttext(html: str, soup=None) -> str:
    """trafilatura, falls installiert; sonst Heuristik: <article>/<main>, Absätze und Überschriften ohne Menüs/Werbung."""
    try:
        import trafilatura  # type: ignore

        out = trafilatura.extract(html, include_comments=False, include_tables=True, favor_precision=True)
        if out and len(out) > 200:
            return re.sub(r"[ \t]+", " ", out).strip()[:TEXT_MAX]
    except Exception:                                        # noqa: BLE001 – nicht installiert/Fehler: Heuristik
        pass
    from bs4 import BeautifulSoup

    soup = soup or BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe", "svg", "button"]):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": re.compile(r"cookie|consent|banner|newsletter|share|social|comment|related|teaser-list", re.I)}):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    parts = []
    for el in root.find_all(["h1", "h2", "h3", "p", "li", "td", "blockquote"]):
        t = " ".join(el.get_text(" ", strip=True).split())
        if len(t) >= (35 if el.name in ("p", "li", "td", "blockquote") else 8):
            parts.append(t)
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return "\n".join(out)[:TEXT_MAX]


def seitentyp(host: str, info: dict | None = None) -> str:
    """Primärquelle/Behörde · Studie · Medium · Blog · Forum · Wikipedia · Unbekannt – nach Adresse und Eigentümer-Tabelle."""
    h = eigentuemer.host_von(host)
    if re.search(r"(^|\.)(wikipedia|wikimedia|wikidata)\.org$", h):
        return "Wikipedia"
    if FORUM.search(h):
        return "Forum/Soziales Netz"
    if BEHOERDE.search(h) or (info or {}).get("staatsnah") and not re.search(r"(rt|sputnik|xinhua|cgtn|tass)", h):
        return "Behörde/Primärquelle"
    if STUDIE.search(h):
        return "Studie/Fachquelle"
    if BLOG.search(h):
        return "Blog"
    if info and info.get("bekannt"):
        return "Medium"
    return "Unbekannt"


def lese(url: str, nutze_cache: bool = True) -> dict:
    """Seite laden und auswerten -> {ok, url, titel, text, veroeffentlicht, geaendert, datum, datum_quelle, betreiber,
    eigentuemer, typ, fehler}. Fehler stehen im Ergebnis (ok False), nichts wird geworfen."""
    from bs4 import BeautifulSoup

    key = url.split("#")[0]
    if nutze_cache and (hit := cache.lade("seite", key)):
        return hit
    host = eigentuemer.host_von(url)
    base = {"ok": False, "url": url, "host": host, "titel": "", "text": "", "veroeffentlicht": None, "geaendert": None,
            "datum": None, "datum_quelle": "", "betreiber": host, "eigentuemer": "", "typ": "Unbekannt", "fehler": ""}
    if not cache.verbrauche("seiten"):
        return {**base, "fehler": "Seitenbegrenzung erreicht", "begrenzt": True}
    try:
        seite = web.hole(url)
        html = seite["text"]
        if seite["typ"] in ("application/json",):
            soup, text = BeautifulSoup("", "lxml"), html[:TEXT_MAX]
            titel = ""
        else:
            soup = BeautifulSoup(html, "lxml")
            titel = ""
            og = soup.find("meta", property="og:title")
            titel = " ".join(((og.get("content") if og else "") or (soup.title.get_text() if soup.title else "")).split())
            datum_soup = BeautifulSoup(html, "lxml")                # Datum VOR dem Entfernen von Kopf/Fuß lesen
            text = haupttext(html, soup)
        daten = daten_finden(datum_soup if seite["typ"] != "application/json" else soup, text, seite.get("last_modified", ""))
        info = eigentuemer.eigentuemer(host)
        res = {**base, "ok": bool(len(text) >= 80), "url": seite["url"], "titel": titel[:200], "text": text, **daten,
               "datum": effektives_datum(daten), "betreiber": info["name"], "eigentuemer": eigentuemer.anzeige(info),
               "typ": seitentyp(host, info), "fehler": "" if len(text) >= 80 else "kein lesbarer Text (evtl. Paywall/Skript-Seite)"}
    except web.WebFehler as exc:
        res = {**base, "fehler": str(exc)}
    except Exception as exc:                                          # noqa: BLE001 – eine Seite darf nie den Lauf stoppen
        res = {**base, "fehler": f"{type(exc).__name__}"}
    if res["ok"]:
        cache.speichere("seite", key, res)
    return res
