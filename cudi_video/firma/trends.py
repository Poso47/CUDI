"""Trend-Scout: was ist gerade im Gespräch? YouTube, Google Trends, Wikipedia, Reddit -> firma_daten/trends.json.

Alles kostenlos; jede Quelle einzeln abgesichert. „warum“ steht nur, was die Daten selbst hergeben
(Platz, Aufrufe, Nachrichtentitel) – keine Vermutungen."""

from __future__ import annotations

import html
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import timedelta

from . import common
from .common import fetch, iso, now, run_source

MAX_TOPICS = 80
KEEP_DAYS = 2                      # Themen, die so lange nirgends mehr auftauchen, fliegen raus
YT_URL = "https://www.googleapis.com/youtube/v3/videos"
YT_CATEGORIES = {"1": "Film & Animation", "2": "Autos", "10": "Musik", "15": "Tiere", "17": "Sport", "19": "Reisen",
                 "20": "Gaming", "22": "Menschen & Blogs", "23": "Comedy", "24": "Unterhaltung", "25": "Nachrichten",
                 "26": "Anleitungen", "27": "Bildung", "28": "Wissen & Technik", "29": "Aktivismus"}
GT_NS = {"ht": "https://trends.google.com/trending/rss"}
WIKI_SKIP = re.compile(r"^(Main_Page|Hauptseite|Special:|Spezial:|Wikipedia:|Portal:|File:|Datei:|Help:|Hilfe:|Category:|"
                       r"Kategorie:|Template:|Vorlage:|Talk:|Diskussion:|User:|Benutzer:|-$)", re.I)
REDDIT_SUBS = ("worldnews", "news", "todayilearned", "interestingasfuck", "technology", "science")
SOURCE_WEIGHT = {"youtube": 1.0, "google": 1.0, "wikipedia": 0.9, "reddit": 0.7}
EVENT_WORDS = re.compile(r"\b(vs\.?|gegen|wahl|wahlen|election|elections|unfall|ergebnis|ergebnisse|finale|erdbeben|"
                         r"earthquake|hurricane|angriff|attack|protest|streik|explosion|insolvenz)\b| – ", re.I)
PERSON_WORDS = re.compile(r"\b(born|geboren|actor|actress|singer|rapper|footballer|politician|president|chancellor|"
                          r"schauspieler\w*|sänger\w*|politiker\w*|fußballspieler|präsident\w*|kanzler\w*|"
                          r"musician|comedian|athlete|boxer|driver|author|autor\w*)\b|\(\*\s?\d|\(born\b", re.I)
EVENT_DESC = re.compile(r"\b(election|wahl|war|krieg|attack|anschlag|shooting|earthquake|erdbeben|hurricane|"
                        r"championship|meisterschaft|final|cup|pokal|season|staffel|flood|überschwemmung|"
                        r"crash|unglück|protest|summit|gipfel|trial|prozess)\b", re.I)


# --------------------------------------------------------------------------- Quellen

def youtube_popular(region: str) -> list[dict]:
    """YouTube „Trends“ (mostPopular). Braucht CUDI_YT_API_KEY oder – falls möglich – den OAuth-Zugang des Uploads."""
    params = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": 25}
    headers = {}
    key = os.environ.get("CUDI_YT_API_KEY", "")
    if key:
        params["key"] = key
    else:
        from ..upload import youtube
        headers["Authorization"] = f"Bearer {youtube.access_token()}"      # wirft ohne CUDI_YT_*; Hinweis genügt
    data = fetch(YT_URL, params=params, headers=headers).json()
    out = []
    for rank, item in enumerate(data.get("items", []), 1):
        sn, st = item.get("snippet", {}), item.get("statistics", {})
        out.append({"quelle": "youtube", "region": region, "rang": rank, "name": html.unescape(sn.get("title", "")),
                    "kanal": sn.get("channelTitle", ""), "aufrufe": int(st.get("viewCount") or 0),
                    "kategorie_quelle": YT_CATEGORIES.get(str(sn.get("categoryId")), ""),
                    "link": f"https://www.youtube.com/watch?v={item.get('id', '')}"})
    return [o for o in out if o["name"]]


def _traffic(text: str) -> int:
    m = re.match(r"\s*([\d.,]+)\s*([KkMm]?)", text or "")
    if not m:
        return 0
    num = float(m.group(1).replace(",", "").replace(".", "") or 0) if m.group(2) == "" else float(m.group(1).replace(",", "."))
    return int(num * {"": 1, "k": 1000, "m": 1_000_000}[m.group(2).lower()])


def google_trends(geo: str) -> list[dict]:
    root = ET.fromstring(fetch("https://trends.google.com/trending/rss", params={"geo": geo}).content)
    out = []
    for rank, item in enumerate(root.iter("item"), 1):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        news = [(n.findtext("ht:news_item_title", "", GT_NS), n.findtext("ht:news_item_source", "", GT_NS))
                for n in item.findall("ht:news_item", GT_NS)]
        out.append({"quelle": "google", "region": geo, "rang": rank, "name": title,
                    "suchen": _traffic(item.findtext("ht:approx_traffic", "", GT_NS)),
                    "nachrichten": [{"titel": html.unescape(t)[:140], "quelle": s} for t, s in news[:2] if t]})
    return out


def wikipedia_top(lang: str) -> list[dict]:
    """Meistgelesene Seiten des Vortags (Wikimedia REST). Fehlen die Daten noch, der Tag davor."""
    for back in (1, 2):
        day = now() - timedelta(days=back)
        url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/"
               f"{day:%Y/%m/%d}")
        try:
            articles = fetch(url, retries=1).json()["items"][0]["articles"]
        except Exception:                              # noqa: BLE001 – 404 = Tag noch nicht fertig
            if back == 2:
                raise
            continue
        out = []
        for art in articles:
            title = art["article"]
            if WIKI_SKIP.match(title):
                continue
            out.append({"quelle": "wikipedia", "region": lang, "rang": len(out) + 1,
                        "name": title.replace("_", " "), "aufrufe": int(art["views"]),
                        "tag": f"{day:%Y-%m-%d}", "link": f"https://{lang}.wikipedia.org/wiki/{title}"})
            if len(out) >= 25:
                break
        return out
    return []


def wikipedia_kategorie(entry: dict) -> dict:
    """Person/Ereignis/Thema aus der Kurzbeschreibung der Wikipedia-Seite (nur Daten, keine Vermutung)."""
    from urllib.parse import quote
    lang, title = entry["region"], entry["name"].replace(" ", "_")
    data = fetch(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}",
                 timeout=8, retries=1).json()
    time.sleep(0.3)                                       # Wikimedia-Regeln: nicht hämmern
    return {"beschreibung": (data.get("description") or "")[:100],
            "kategorie": classify(data.get("description", ""), data.get("extract", "")[:160], entry["name"])}


def classify(description: str, extract: str = "", name: str = "") -> str:
    if PERSON_WORDS.search(f"{description} {extract}"):
        return "Person"
    if EVENT_DESC.search(description) or EVENT_WORDS.search(name):
        return "Ereignis"
    return "Thema"


def reddit_hot() -> list[dict]:
    """Reddit „top day“ + „rising“ über den öffentlichen RSS-Feed (geht oft nicht aus der Cloud), sonst das Archiv."""
    out: list[dict] = []
    for sort, params in (("top", {"t": "day", "limit": 40}), ("rising", {"limit": 40})):
        try:
            resp = fetch(f"https://www.reddit.com/r/all/{sort}/.rss", params=params, retries=1)
            ns = "{http://www.w3.org/2005/Atom}"
            for entry in ET.fromstring(resp.content).findall(f"{ns}entry"):
                cat = entry.find(f"{ns}category")
                title = html.unescape(entry.findtext(f"{ns}title") or "").strip()
                link = entry.find(f"{ns}link")
                if title:
                    out.append({"quelle": "reddit", "region": "all", "rang": len(out) + 1, "name": title,
                                "subreddit": cat.get("term", "") if cat is not None else "", "art": sort,
                                "link": link.get("href", "") if link is not None else ""})
        except Exception:                              # noqa: BLE001 – RSS gesperrt -> Archiv
            continue
    return out or _reddit_archiv()


def _reddit_archiv() -> list[dict]:
    from ..story.sources import ARCTIC
    end = int(time.time() // 3600 * 3600) - 3 * 3600               # die letzten 3 h sind noch ohne Stimmen
    posts = []
    for sub in REDDIT_SUBS:
        try:
            data = fetch(f"{ARCTIC}/posts/search", params={"subreddit": sub, "after": end - 24 * 3600, "before": end,
                                                          "limit": 100, "sort": "desc",
                                                          "fields": "id,title,score,num_comments,over_18,subreddit"},
                         retries=1, timeout=25).json().get("data") or []
        except Exception:                              # noqa: BLE001
            continue
        posts += [d for d in data if not d.get("over_18") and d.get("title")]
    posts.sort(key=lambda d: (d.get("score") or 0) + 2 * (d.get("num_comments") or 0), reverse=True)
    return [{"quelle": "reddit", "region": "all", "rang": i, "name": html.unescape(d["title"]).strip(),
             "subreddit": d.get("subreddit", ""), "art": "archiv", "punkte": int(d.get("score") or 0),
             "kommentare": int(d.get("num_comments") or 0),
             "link": f"https://www.reddit.com/r/{d.get('subreddit', '')}/comments/{d.get('id', '')}/"}
            for i, d in enumerate(posts[:40], 1)]


# --------------------------------------------------------------------------- Zusammenführen

_STOP = {"the", "a", "an", "of", "and", "in", "on", "der", "die", "das", "und", "von", "im", "in", "den", "ein", "eine"}


def key_of(name: str) -> str:
    return " ".join(w for w in re.findall(r"\w+", name.lower()) if w not in _STOP)


def _same(a: str, b: str) -> bool:
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(small) >= 2 and small <= big:                 # „Taylor Swift“ in „Taylor Swift Eras Tour“
        return True
    return len(ta & tb) / len(ta | tb) >= 0.7


def source_score(entry: dict, total: int) -> float:
    """0..100 aus Rang (und Stärke der Quelle): Platz 1 = volle Punktzahl, letzter Platz ~ 40 %."""
    pos = 1 - 0.6 * (entry["rang"] - 1) / max(total - 1, 1)
    return 100 * pos * SOURCE_WEIGHT.get(entry["quelle"], 0.6)


def warum(entry: dict) -> str:
    q, r, reg = entry["quelle"], entry["rang"], entry.get("region", "")
    if q == "youtube":
        return (f"Platz {r} der YouTube-Trends ({reg}) mit {entry.get('aufrufe', 0):,} Aufrufen"
                f"{' (' + entry['kategorie_quelle'] + ')' if entry.get('kategorie_quelle') else ''}").replace(",", ".")
    if q == "google":
        news = entry.get("nachrichten") or []
        extra = f"; Meldung: „{news[0]['titel']}“ ({news[0]['quelle']})" if news else ""
        suchen = f" mit über {entry['suchen']:,} Suchen".replace(",", ".") if entry.get("suchen") else ""
        return f"Platz {r} der Google-Trends ({reg}){suchen}{extra}"
    if q == "wikipedia":
        return f"Platz {r} der meistgelesenen Wikipedia-Seiten ({reg}) am {entry.get('tag', '')}: {entry.get('aufrufe', 0):,} Aufrufe".replace(",", ".")
    return (f"Reddit r/{entry.get('subreddit', '')} ({entry.get('art', '')}), Platz {r}"
            + (f", {entry['punkte']:,} Punkte".replace(",", ".") if entry.get("punkte") else ""))


def merge(entries: list[dict], previous: list[dict] | None = None) -> list[dict]:
    """Einträge aller Quellen zu Themen verschmelzen; frühere Themen (bis KEEP_DAYS) bleiben mit altem Zeitpunkt."""
    totals: dict[tuple, int] = {}
    for e in entries:
        totals[(e["quelle"], e["region"])] = totals.get((e["quelle"], e["region"]), 0) + 1
    topics: list[dict] = []
    for e in entries:
        k = key_of(e["name"])
        if not k:
            continue
        topic = next((t for t in topics if _same(t["_key"], k)), None)
        if topic is None:
            topic = {"_key": k, "thema": e["name"], "kategorie": e.get("kategorie") or "Thema", "quellen": [],
                     "_scores": [], "warum": []}
            topics.append(topic)
        if e.get("kategorie") and topic["kategorie"] == "Thema":
            topic["kategorie"] = e["kategorie"]
        if e["quelle"] == "wikipedia" and len(e["name"]) <= len(topic["thema"]):
            topic["thema"] = e["name"]                       # Seitentitel ist der sauberste Name
        slim = {k2: v for k2, v in e.items() if k2 in ("quelle", "region", "rang", "aufrufe", "suchen", "kanal",
                                                       "subreddit", "link", "beschreibung")}
        topic["quellen"].append(slim)
        topic["_scores"].append(source_score(e, totals[(e["quelle"], e["region"])]))
        topic["warum"].append(warum(e))
    stamp = iso()
    old = {t.get("_key") or key_of(t.get("thema", "")): t for t in (previous or [])}
    result = []
    for t in topics:
        scores = sorted(t.pop("_scores"), reverse=True)
        miss = 1.0
        for sc in scores:                                  # mehrere Quellen verstärken sich, ohne 100 zu sprengen
            miss *= 1 - sc / 100
        score = round(100 * (1 - miss), 1)
        key = t.pop("_key")
        before = old.pop(key, None)
        result.append({**t, "score": score, "warum": " · ".join(t["warum"][:3]),
                       "erstmals": (before or {}).get("erstmals", stamp), "zuletzt": stamp})
    cutoff = now() - timedelta(days=KEEP_DAYS)
    for t in old.values():                                    # nicht mehr gesehen: abklingen lassen
        seen = common.parse_time(t.get("zuletzt", ""))
        if seen and seen >= cutoff:
            result.append({**t, "score": round(t.get("score", 0) * 0.6, 1)})
    result.sort(key=lambda t: t["score"], reverse=True)
    return result[:MAX_TOPICS]


# --------------------------------------------------------------------------- Lauf

def collect(notes: list[str]) -> list[dict]:
    entries: list[dict] = []
    jobs = [("YouTube DE", lambda: youtube_popular("DE")), ("YouTube US", lambda: youtube_popular("US")),
            ("Google Trends DE", lambda: google_trends("DE")), ("Google Trends US", lambda: google_trends("US")),
            ("Wikipedia de", lambda: wikipedia_top("de")), ("Wikipedia en", lambda: wikipedia_top("en")),
            ("Reddit", reddit_hot)]
    for name, func in jobs:
        entries += run_source(name, func, notes)
    # Kategorien der obersten Wikipedia-Seiten (ein Aufruf je Seite; bei Störung ohne Kategorie weiter)
    wiki = [e for e in entries if e["quelle"] == "wikipedia"][:12]
    for e in wiki:
        try:
            e.update(wikipedia_kategorie(e))
        except Exception as exc:                          # noqa: BLE001
            notes.append(f"Wikipedia-Kategorien: abgebrochen ({common.short_error(exc)})")
            break
    for e in entries:
        if not e.get("kategorie") and EVENT_WORDS.search(e["name"]):
            e["kategorie"] = "Ereignis"
    return entries


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    entries = collect(notes)
    prev = (common.read_json("trends.json", {}) or {}).get("themen", [])
    if not entries and prev:                                  # alles ausgefallen: alte Daten nicht überschreiben
        common.record_status("trends", started, False, "alle Quellen ausgefallen", notes)
        return {"themen": prev, "hinweise": notes}
    themen = merge(entries, prev)
    data = {"erzeugt": iso(), "anzahl": len(themen), "hinweise": notes, "themen": themen}
    changed = common.write_json("trends.json", data)
    ok = bool(entries)
    common.record_status("trends", started, ok, f"{len(themen)} Themen aus {len({e['quelle'] for e in entries})} Quellen"
                         + ("" if changed else " (unverändert)"), notes)
    return data
