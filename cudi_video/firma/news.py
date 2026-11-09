"""News-Reporter: Schlagzeilen aus frei zugänglichen Quellen -> firma_daten/news.json.

Nur Titel, Kurzzeile (höchstens ~160 Zeichen), Link und Quelle – keine Volltexte. „bestätigt“ gilt erst,
wenn mindestens zwei unabhängige Quellen dieselbe Meldung bringen (Titel-/Wortähnlichkeit), sonst „unbestätigt“."""

from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from .. import eigentuemer as eig
from . import common
from .common import fetch, iso, now, run_source

MAX_ITEMS = 60
MAX_AGE_H = 36
FEEDS = [
    ("Tagesschau", "tagesschau", "de", "https://www.tagesschau.de/index~rss2.xml"),
    ("Deutsche Welle", "dw", "de", "https://rss.dw.com/xml/rss-de-all"),
    ("BBC World", "bbc", "en", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Deutsche Welle (en)", "dw", "en", "https://rss.dw.com/xml/rss-en-all"),
    ("NPR", "npr", "en", "https://feeds.npr.org/1001/rss.xml"),
]
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
_STOP = set("""der die das den dem des ein eine einen einer und oder aber mit von für auf bei nach über unter vor aus als
nicht auch sich sind wird wurde werden sein hat haben noch nur wie was wer wenn dass diese dieser zum zur beim ist
the and for with from that this have has was were will are not but its his her after over into about says said
more than new amid against been their they them what when who how why may could would""".split())
SKIP_PUBLISHER_PARTS = {"co", "com", "org", "net", "gov", "ac"}


# --------------------------------------------------------------------------- Hilfen

def clean(text: str, limit: int = 160) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def publisher_of(url_or_domain: str) -> str:
    """Betreiber aus der Adresse (bbc.co.uk und bbc.com -> bbc), damit eine Quelle nicht doppelt zählt."""
    host = (urlparse(url_or_domain).netloc or url_or_domain).lower().split(":")[0]
    labels = [p for p in host.split(".") if p and p != "www"]
    if len(labels) > 1:
        labels.pop()                                     # Endung (de, com, uk …)
    while len(labels) > 1 and labels[-1] in SKIP_PUBLISHER_PARTS:
        labels.pop()                                     # co.uk, net.au …
    return labels[-1] if labels else host


def tokens(title: str) -> set[str]:
    words = re.findall(r"[^\W_]{3,}", title.lower())
    return {w[:6] for w in words if w not in _STOP}


def names(title: str) -> set[str]:
    """Eigennamen-Stämme (großgeschrieben, nicht am Satzanfang) – Kennzeichen derselben Meldung."""
    words = re.findall(r"[^\W\d_][^\W_]{2,}", title)
    return {w.lower()[:6] for i, w in enumerate(words) if i and w[0].isupper() and w.lower() not in _STOP}


def similar(a: set[str], b: set[str], na: set[str] | None = None, nb: set[str] | None = None) -> bool:
    common_t = a & b
    if na is not None and nb is not None and na and nb and not (na & nb):
        return False                                  # kein gemeinsamer Name/Ort → andere Meldung
    if len(common_t) >= 3:
        return True
    return len(common_t) >= 2 and len(common_t) / len(a | b) >= 0.3


def _when(text: str) -> datetime | None:
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- Quellen

def rss(name: str, pub: str, lang: str, url: str) -> list[dict]:
    root = ET.fromstring(fetch(url, timeout=15).content)
    ns = "{http://www.w3.org/2005/Atom}"
    out = []
    for item in list(root.iter("item")) + list(root.iter(f"{ns}entry")):
        title = clean(item.findtext("title") or item.findtext(f"{ns}title") or "", 160)
        link = item.findtext("link") or ""
        if not link:
            el = item.find(f"{ns}link")
            link = el.get("href", "") if el is not None else ""
        when = _when(item.findtext("pubDate") or item.findtext(f"{ns}updated") or item.findtext(f"{ns}published") or "")
        if title and link:
            out.append({"titel": title, "kurz": clean(item.findtext("description") or item.findtext(f"{ns}summary") or ""),
                        "link": link.strip(), "quelle": name, "betreiber": pub, "sprache": lang,
                        "zeit": iso(when) if when else ""})
    return out


def gdelt() -> list[dict]:
    """GDELT DOC API (frei, ohne Schlüssel): aktuelle Artikel, nur Titel/Domain/Link."""
    out = []
    for lang, name in (("english", "en"), ("german", "de")):
        if out:
            time.sleep(5.5)                              # GDELT erlaubt eine Anfrage je 5 Sekunden
        data = fetch(GDELT, params={"query": f"sourcelang:{lang}", "mode": "artlist", "format": "json",
                                    "maxrecords": 60, "timespan": "6h", "sort": "hybridrel"},
                     timeout=25, retries=1).json()
        for art in data.get("articles") or []:
            title, url, domain = clean(art.get("title", ""), 160), art.get("url", ""), art.get("domain", "")
            when = None
            try:
                when = datetime.strptime(art.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
            if title and url and domain:
                out.append({"titel": title, "kurz": "", "link": url, "quelle": domain, "betreiber": publisher_of(domain),
                            "sprache": name, "zeit": iso(when) if when else "", "gdelt": True})
    return out


def wikipedia_events() -> list[dict]:
    """Wikipedia „Current events“: eine Zeile je Meldung mit dem zitierten Medium als Quelle."""
    data = fetch("https://en.wikipedia.org/w/api.php",
                 params={"action": "parse", "page": "Portal:Current_events", "prop": "text", "format": "json",
                         "formatversion": 2}, timeout=25, retries=2).json()
    page = data["parse"]["text"]
    out = []
    for li in re.findall(r"<li>((?:(?!<ul>|</li>).)*?)</li>", page, re.S):
        m = re.search(r'<a [^>]*class="external text"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', li)
        if not m:
            continue
        text = clean(li, 400)
        text = re.sub(r"\s*\([^()]*\)\s*$", "", text).strip()           # „(Reuters)“ am Ende ist die Quelle
        if len(text) < 25:
            continue
        pub = m.group(2).strip().strip("()").strip()
        out.append({"titel": clean(text, 140), "kurz": clean(text, 160) if len(text) > 140 else "",
                    "link": html.unescape(m.group(1)), "quelle": f"Wikipedia · {pub}", "betreiber": publisher_of(m.group(1)),
                    "sprache": "en", "zeit": "", "wikipedia": True})
        if len(out) >= 40:
            break
    return out


# --------------------------------------------------------------------------- Gruppieren

def cluster(items: list[dict]) -> list[dict]:
    groups: list[dict] = []
    for it in items:
        tok, nm = tokens(it["titel"]), names(it["titel"])
        if len(tok) < 2:
            continue
        for g in groups:
            # mit einzelnen Meldungen vergleichen, nicht mit der wachsenden Wortmenge der Gruppe
            # (sonst rutschen fremde Meldungen über gemeinsame Allerweltswörter hinein)
            if g["sprache"] == it["sprache"] and any(similar(tok, t, nm, n) for t, n in zip(g["toks"], g["names"])):
                g["items"].append(it)
                g["toks"].append(tok)
                g["names"].append(nm)
                break
        else:
            groups.append({"toks": [tok], "names": [nm], "sprache": it["sprache"], "items": [it]})
    out = []
    for g in groups:
        its = g["items"]
        pubs = {i["betreiber"] for i in its}
        reps = list({i["betreiber"]: i for i in its}.values())
        ana = eig.gruppiere(reps)          # gleicher Eigentümer/Geldgeber/Agentur/Staat zählt nur einmal
        order = sorted(range(len(reps)), key=lambda k: (bool(ana["zaehlt_nicht"][k]), k))
        first = next((i for i in its if not i.get("gdelt") and not i.get("wikipedia")), its[0])
        times = [i["zeit"] for i in its if i["zeit"]]
        out.append({
            "titel": first["titel"], "kurz": first["kurz"], "link": first["link"], "quelle": first["quelle"],
            "sprache": g["sprache"], "zeit": max(times) if times else "",
            "status": "bestätigt" if ana["n"] >= 2 else "unbestätigt", "n_quellen": len(pubs),
            "unabhaengig_n": ana["n"], "abhaengig": ana["abhaengig"][:6], "eigentuemer_unbekannt": ana["unbekannt"][:6],
            "quellen": [{"quelle": reps[k]["quelle"], "titel": reps[k]["titel"], "link": reps[k]["link"],
                         "eigentuemer": ana["eigentuemer"][k], "gruppe": ana["gruppe"][k], "zaehlt_nicht": ana["zaehlt_nicht"][k]}
                        for k in order][:5],
        })
    out.sort(key=lambda m: (m["status"] == "bestätigt", m["unabhaengig_n"], m["n_quellen"], m["zeit"]), reverse=True)
    return out[:MAX_ITEMS]


def run() -> dict:
    started = time.monotonic()
    eig.neuer_lauf()
    notes: list[str] = []
    items: list[dict] = []
    for name, pub, lang, url in FEEDS:
        items += run_source(name, lambda n=name, p=pub, l=lang, u=url: rss(n, p, l, u), notes)
    items += run_source("GDELT", gdelt, notes)
    items += run_source("Wikipedia Current events", wikipedia_events, notes)
    limit = now() - timedelta(hours=MAX_AGE_H)
    items = [i for i in items if not i["zeit"] or (common.parse_time(i["zeit"]) or now()) >= limit]
    if not items and common.read_json("news.json"):
        common.record_status("news", started, False, "alle Quellen ausgefallen", notes)
        return common.read_json("news.json")
    meldungen = cluster(items)
    confirmed = sum(m["status"] == "bestätigt" for m in meldungen)
    data = {"erzeugt": iso(), "anzahl": len(meldungen), "bestaetigt": confirmed, "hinweise": notes,
            "regel": "bestätigt = mindestens 2 unabhängige Quellen (nicht derselbe Eigentümer, Geldgeber, dieselbe Agentur oder derselbe "
                     "Staat; unbekannter Eigentümer zählt nur nach Domain und ist vermerkt); nur Titel, Kurzzeile und Link", "meldungen": meldungen}
    changed = common.write_json("news.json", data)
    common.record_status("news", started, bool(items), f"{len(meldungen)} Meldungen, davon {confirmed} bestätigt"
                         + ("" if changed else " (unverändert)"), notes)
    return data
