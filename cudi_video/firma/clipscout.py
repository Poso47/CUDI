"""Clip-Scout (kostenlos, kein Claude-Verbrauch): findet Material, das geclippt werden darf – und belegt, warum.

Fünf Aufgaben, jede Quelle einzeln abgesichert (alle BEOBACHTEN, nur Belegtes/Geduldetes mit Bestätigung CLIPPEN):
 0) Entdeckung (`entdecke`): Creator im Hype automatisch finden (Kampagnen, Aufruf-Suche, YouTube-Trends, Reddit-Clip-Subreddit,
    Wikipedia-Top-Personen mit Wikidata-Beruf) -> `clip_entdeckt.json`; jeder Entdeckte läuft durch den Beweis-Sucher.
 a) Trend-Radar: YouTube-Kanalfeeds (RSS, ohne Schlüssel) + öffentliche Twitch-Clips (yt-dlp, ohne Anmeldung) der Creator aus
    `clip_creators.json` -> Aufrufe je Stunde (`clip_radar.json`).
 b) Aufruf-Finder: Videobeschreibungen nach „Clipper gesucht / clips erlaubt / clip my streams“ (de/en).
 c) Kampagnen-Scout: öffentliche Liste contentrewards.com/c/discover (robots.txt wird geprüft, ein Abruf).
 d) Beweis-Sucher: wörtliches Zitat + Link + Datum -> `clip_erlaubnis.json`. „erlaubt“ gibt es NUR mit eindeutigem Aufruf
    des Creators selbst (Beleg). Vier Stufen: erlaubt (Beleg) · geduldet (keine Aussage, aber >= 2 Duldungssignale oder Kampagne,
    und kein Verbot gefunden; nie als Erlaubnis bezeichnet) · unklar (keine Signale) · gesperrt (ausdrückliches Verbot in einer
    Beschreibung gefunden oder Sperr-Eintrag des Nutzers – gewinnt immer).
Nichts wird erfunden: ohne Quellen-Treffer bleibt alles ehrlich leer (mit Hinweis).
"""

from __future__ import annotations

import json
import re
import statistics
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib import robotparser

from . import common
from .common import iso, now, parse_time

CREATORS, RADAR, ERLAUBNIS, ENT = "clip_creators.json", "clip_radar.json", "clip_erlaubnis.json", "clip_entdeckt.json"
MAX_AGE_H = 72                 # nur frische Videos zählen für den Trend
MIN_FAKTOR = 1.5               # Aufrufe/Stunde gegenüber dem Median des Kanals
MAX_BELEGE = 5
KEEP_BELEGE_DAYS = 400
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}
CAMPAIGN_URL = "https://contentrewards.com/c/discover"

# Eindeutiger Aufruf (genügt allein für „erlaubt“) – bewusst eng, „Clip vom Stream“ ist kein Aufruf
STRONG = re.compile(
    r"\bclipper\s+gesucht\b|\bclips? von mir\b.{0,25}(?:hochlad|post|mach|erstell|schneid|upload)|clippt? (?:mich|meine[nm]?)\b|"
    r"freu\w* mich über (?:jeden|alle)\b.{0,40}\bclips?\b|clip-?(?:accounts?|kan(?:al|äle))\b.{0,40}(?:erstell|mach|aufmach)|"
    r"\bclip (?:me|my (?:streams?|content|videos?))\b|\bpost clips of me\b|\bmake clips (?:of|for) me\b|"
    r"\b(?:i|we)(?:'m| am| are)? pay(?:ing)? (?:my |our )?clippers\b|\bclipp(?:ing|er) (?:program|campaign|army|team)\b|"
    r"\bclippers? (?:wanted|needed)\b|\bbecome a clipper\b|\bclips? (?:sind|ist) (?:erlaubt|ausdrücklich erwünscht)\b|"
    r"\bclips? (?:are|is) (?:allowed|welcome)\b",
    re.I)
CALL = re.compile(r"\bclipp(?:er|ing|en|ern)\b|\bclips? (?:schneiden|machen)\b.{0,60}(?:geld|verdien|bezahl|€|\$)", re.I)
RECRUIT = re.compile(r"gesucht|such\w*|werd\w*|team|programm|kampagne|verdien\w*|geld|bezahl\w*|€|\$|join|become|paid|apply|bewerb\w*",
                     re.I)
# Ausdrückliches Verbot (Creator selbst, in Beschreibung) – konservativ: im Zweifel gesperrt
VERBOT = re.compile(
    r"\bno (?:clips?|re-?uploads?)\b|\bkeine? (?:clips?|re-?uploads?)\b|\bdo(?:n'?t| not) (?:re-?upload|clip)\b|"
    r"\bnot allowed to (?:clip|re-?upload)\b|\bclips? (?:are |is |sind |ist )?(?:not allowed|prohibited|forbidden|verboten|nicht erlaubt)\b|"
    r"\bre-?uploads? (?:are |is |sind |ist )?(?:not allowed|prohibited|forbidden|verboten|nicht erlaubt)\b|\bcopyright strikes?\b", re.I)
NOISE = re.compile(r"clipping[- ]?(?:software|tool|mask|path)|hair ?clipper|barber|photoshop|illustrator|premiere", re.I)
LINK = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg/|discord\.com/invite/|whop\.com/|contentrewards\.com/|linktr\.ee/|"
                  r"forms\.gle/|docs\.google\.com/forms/)[^\s)\]>\"']+", re.I)
RISKY = re.compile(r"onlyfans|fansly|nsfw|\b18\+|porn|adult content|erotik|casino|gambl|betting|\bbet\b|sportsbook|stake\.com|"
                   r"roobet|glücksspiel|wetten", re.I)
UGC = re.compile(r"\bugc\b|slideshow|faceless|film yourself|selbst filmen", re.I)
STOP = {"de": {"und", "der", "die", "das", "ist", "nicht", "mit", "für", "auf", "ich", "du", "sie", "ein", "eine", "zu", "von",
               "den", "dem", "wir", "auch", "bitte", "nur", "oder", "wie", "dein", "deine"},
        "en": {"the", "and", "to", "of", "for", "you", "your", "with", "this", "is", "are", "on", "in", "must", "will", "be",
               "it", "that", "from", "our", "we", "please", "only", "or", "not"}}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# --------------------------------------------------------------------------- Creator-Liste

def load_creators(notes: list[str]) -> list[dict]:
    """Nutzerpflege: firma_daten/clip_creators.json. Keine erfundenen Creator – fehlt die Datei, ist die Liste leer."""
    data = common.read_json(CREATORS)
    if not isinstance(data, dict) or not isinstance(data.get("creators"), list):
        notes.append("clip_creators.json fehlt oder ist leer – optional: eigene Creator/Sperrliste eintragen (docs/clip-team.md).")
        return []
    out = []
    for c in data["creators"]:
        if not isinstance(c, dict) or not str(c.get("name") or "").strip():
            continue
        out.append({"name": _norm(c["name"])[:60],
                    "youtube": [str(x).strip() for x in c.get("youtube") or [] if str(x).strip()],
                    "twitch": [str(x).strip().lower() for x in c.get("twitch") or [] if str(x).strip()],
                    "tiktok": [str(x).strip() for x in c.get("tiktok") or [] if str(x).strip()],
                    "gesperrt": bool(c.get("gesperrt"))})
    if not out:
        notes.append("clip_creators.json enthält keinen Creator – optional: eigene Creator/Sperrliste eintragen (docs/clip-team.md).")
    return out


# --------------------------------------------------------------------------- YouTube / Twitch

def parse_feed(xml_bytes: bytes, at=None) -> tuple[str, list[dict]]:
    """YouTube-Atom-Feed -> (Kanalname, Videos mit Aufrufen und Aufrufen je Stunde)."""
    root = ET.fromstring(xml_bytes)
    at = at or now()
    name = root.findtext("a:author/a:name", default="?", namespaces=NS)
    out = []
    for e in root.findall("a:entry", NS):
        published = parse_time(e.findtext("a:published", default="", namespaces=NS))
        vid = e.findtext("yt:videoId", default="", namespaces=NS)
        if not published or not vid:
            continue
        stats = e.find("media:group/media:community/media:statistics", NS)
        views = int(stats.get("views", 0)) if stats is not None and str(stats.get("views", "0")).isdigit() else 0
        hours = max((at - published).total_seconds() / 3600, 1.0)
        out.append({"id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                    "titel": _norm(e.findtext("a:title", default="", namespaces=NS))[:140],
                    "beschreibung": e.findtext("media:group/media:description", default="", namespaces=NS) or "",
                    "veroeffentlicht": iso(published), "aufrufe": views, "alter_stunden": round(hours, 1),
                    "aufrufe_je_stunde": round(views / hours, 1)})
    return name, out


def resolve_channel(entry: str, cache: dict) -> str | None:
    """Kanal-ID (UC…) aus ID, /channel/-Link oder @Handle (öffentliche Kanalseite, einmal je Handle, gemerkt)."""
    m = re.search(r"(UC[\w-]{22})", entry)
    if m:
        return m.group(1)
    handle = entry.strip().split("/")[-1] if "/" in entry else entry.strip()
    handle = handle if handle.startswith("@") else "@" + handle
    if handle in cache:
        return cache[handle]
    html = common.fetch(f"https://www.youtube.com/{handle}", timeout=20, retries=1).text
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', html) \
        or re.search(r'"channelId":"(UC[\w-]{22})"', html)
    if not m:
        return None
    cache[handle] = m.group(1)
    return m.group(1)


def twitch_clips(login: str, limit: int = 20) -> list[dict]:
    """Meistgesehene Twitch-Clips der letzten 24 h (öffentliche Seite, yt-dlp, keine Anmeldung)."""
    res = subprocess.run(["yt-dlp", "--flat-playlist", "--playlist-items", f"1-{limit}", "-J",
                          f"https://www.twitch.tv/{login}/clips?filter=clips&range=24hr"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"Twitch {login}: Clips nicht lesbar")
    out = []
    for e in json.loads(res.stdout).get("entries") or []:
        if not e.get("url"):
            continue
        ts = e.get("timestamp")
        published = datetime.fromtimestamp(ts, timezone.utc) if ts else None
        views = int(e.get("view_count") or 0)
        hours = max((now() - published).total_seconds() / 3600, 1.0) if published else 24.0
        out.append({"id": e.get("id", ""), "url": e["url"], "titel": _norm(e.get("title"))[:140], "aufrufe": views,
                    "veroeffentlicht": iso(published) if published else "", "aufrufe_je_stunde": round(views / hours, 1)})
    return sorted(out, key=lambda c: c["aufrufe"], reverse=True)


# --------------------------------------------------------------------------- Aufruf-Finder

def _snippet(text: str, m: re.Match, width: int = 120) -> str:
    return _norm(text[max(0, m.start() - width): m.end() + width])


def find_call(text: str) -> dict | None:
    """Aufruf in einem Beschreibungstext: {zitat (wörtlich aus dem Text), links, staerke eindeutig|hinweis} oder None."""
    text = text or ""
    links = sorted({l.rstrip(".,!") for l in LINK.findall(text)})
    m = STRONG.search(text)
    if m and not NOISE.search(_snippet(text, m, 60)):
        return {"zitat": _snippet(text, m), "links": links, "staerke": "eindeutig"}
    for m in CALL.finditer(text):
        near = _snippet(text, m, 80)
        if NOISE.search(near):
            continue
        if links or RECRUIT.search(near):
            return {"zitat": _snippet(text, m), "links": links, "staerke": "hinweis"}
    return None


# --------------------------------------------------------------------------- Kampagnen-Scout

def robots_allows(url: str = CAMPAIGN_URL) -> bool:
    base = url.split("/c/")[0]
    rp = robotparser.RobotFileParser()
    rp.parse(common.fetch(base + "/robots.txt", timeout=15, retries=1).text.splitlines())
    return rp.can_fetch(common.USER_AGENT, url) and rp.can_fetch("*", url)


def parse_campaigns(html: str) -> list[dict]:
    """Die Seite schickt ihre Daten als JSON-Schnipsel (Next.js). Fehlen sie, ist die Liste leer (Seite umgebaut)."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    payload = ""
    for c in chunks:
        try:
            payload += json.loads(f'"{c}"')
        except ValueError:
            continue
    dec, found = json.JSONDecoder(), {}
    for m in re.finditer(r'\{"availableBudgetRaw":', payload):
        try:
            obj, _ = dec.raw_decode(payload, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("id"):
            found[obj["id"]] = obj
    return list(found.values())


def language(c: dict) -> str:
    text = f"{c.get('title') or ''} {c.get('description') or ''}".lower()
    if re.search(r"\b(deutsch|german|\[de\]|\(de\))", text):
        return "de"
    words = re.findall(r"[a-zäöüß]+", text)
    n = {l: sum(w in sw for w in words) for l, sw in STOP.items()}
    if n["de"] >= 2 and n["de"] > n["en"]:
        return "de"
    if n["en"] >= 2 and n["en"] > n["de"]:
        return "en"
    return "unklar"


def summarize_campaign(c: dict) -> dict:
    clean = lambda t: (t or "").replace("$$", "$")
    left = float(c.get("availableBudgetRaw") or 0)
    rate = c.get("payoutSortRaw") if c.get("type") == "cpm" else None
    risky = RISKY.search(f"{c.get('title')} {c.get('brand')} {c.get('category')} {c.get('description')}")
    desc = clean(c.get("description"))
    return {"id": str(c["id"]), "titel": _norm(clean(c.get("title")))[:100], "marke": c.get("brand"),
            "art": "ugc" if UGC.search(f"{c.get('title')} {desc}") else "clipping", "sprache": language(c),
            "satz_pro_1000": rate, "restbudget": round(left), "teilnehmer": c.get("creatorCountRaw"),
            "bewerbung_noetig": bool(c.get("requiresApplication")),
            "risiko": ("heikel: " + risky.group(0)) if risky else "",
            "kanaele": sorted(set(re.findall(r"https?://(?:www\.)?youtube\.com/(?:@[\w.-]+|channel/UC[\w-]+)", desc))),
            "link": f"https://contentrewards.com/c/campaigns/{c['id']}",
            "beschreibung": _norm(desc)[:400]}


def campaigns(notes: list[str]) -> list[dict]:
    if not robots_allows():
        notes.append("Kampagnen-Liste: robots.txt erlaubt den Abruf nicht – übersprungen.")
        return []
    raw = parse_campaigns(common.fetch(CAMPAIGN_URL, timeout=30, retries=1).text)
    if not raw:
        notes.append("Kampagnen-Liste: keine Daten gefunden (Seite vermutlich umgebaut).")
    rows = [summarize_campaign(c) for c in raw]
    rows = [r for r in rows if r["art"] == "clipping" and r["sprache"] in ("de", "en") and r["restbudget"] >= 200 and not r["risiko"]]
    return sorted(rows, key=lambda r: (r["satz_pro_1000"] or 1.0) * r["restbudget"], reverse=True)[:25]


# --------------------------------------------------------------------------- Beweise / Erlaubnis

def decide(creator: dict, belege: list[dict], signale: list[str] | None = None, lesbar: bool = True) -> dict:
    """Status aus Beleg-Lage. Sperre des Nutzers und ausdrückliches Verbot gewinnen; „erlaubt“ nur mit eindeutigem Aufruf vom Creator
    selbst (Zitat+Link+Datum); „geduldet“ = Kampagne oder >= 2 Duldungsarten (`signale`, Text beginnt mit „Art:“) ohne Verbot."""
    bedingungen: list[str] = []
    if creator.get("gesperrt"):
        return {"status": "gesperrt", "monetarisierung": "unklar", "signale": [],
                "bedingungen": ["vom Nutzer gesperrt (clip_creators.json)"]}
    ban = [b for b in belege if b.get("art") == "verbot" and b.get("url") and b.get("zitat") and b.get("datum")]
    if ban:
        return {"status": "gesperrt", "monetarisierung": "unklar", "signale": [],
                "bedingungen": [f"ausdrückliches Verbot: „{ban[0]['zitat'][:160]}“ ({ban[0]['datum']}) – {ban[0]['url']}"]}
    good = [b for b in belege if b.get("url") and b.get("zitat") and b.get("datum") and b.get("art") == "beschreibung"
            and b.get("staerke") == "eindeutig"]
    camp = [b for b in belege if b.get("art") == "kampagne"]
    paid = any(b.get("bezahlt") for b in camp) or any(re.search(r"verdien|bezahl|geld|paid|€|\$", b.get("zitat", ""), re.I) for b in good)
    if good:
        links = sorted({l for b in good for l in b.get("links", [])})
        if links:
            bedingungen.append("Regeln laut Link: " + ", ".join(links[:3]))
        return {"status": "erlaubt", "monetarisierung": "ja" if paid else "unklar", "signale": [], "bedingungen": bedingungen}
    signale = list(signale or [])
    arten = {x.split(":")[0] for x in signale}
    if signale and ("Kampagne" in arten or len(arten) >= 2):
        bedingungen.append("nicht ausdrücklich erlaubt – Start nur mit Bestätigung; Credit „Original: <Creator> – <Link>“ ist Pflicht")
        if "Kampagne" in arten:
            bedingungen.append("Beitritt und Regeln der Kampagne beachten")
        if not lesbar:
            bedingungen.append("Verbotssuche nicht möglich (keine Beschreibung lesbar) – vor dem Start Kanalregeln prüfen")
        return {"status": "geduldet", "monetarisierung": "ja" if paid else "unklar", "signale": signale, "bedingungen": bedingungen}
    if camp:
        bedingungen.append("Kampagne gefunden – erst nach bestätigtem Beitritt und mit deren Regeln erlaubt")
    elif belege:
        bedingungen.append("nur schwacher Hinweis – Aufruf nicht eindeutig")
    return {"status": "unklar", "monetarisierung": "ja" if paid else "unklar", "signale": signale, "bedingungen": bedingungen}


def merge_belege(old: list[dict], new: list[dict]) -> list[dict]:
    seen, out = set(), []
    for b in new + old:                                    # Neues zuerst, alte Belege bleiben (nach Alter ausgedünnt)
        if not b.get("url") or not b.get("zitat"):
            continue
        key = (b["url"], b.get("art"))
        t = parse_time(b.get("datum", ""))
        if key in seen or (t and now() - t > timedelta(days=KEEP_BELEGE_DAYS)):
            continue
        seen.add(key)
        out.append(b)
    return out[:MAX_BELEGE]


def evidence_from_videos(videos: list[dict]) -> list[dict]:
    out = []
    for v in videos:
        hit = find_call(v.get("beschreibung", ""))
        if hit:
            out.append({"url": v["url"], "zitat": hit["zitat"][:300], "datum": v["veroeffentlicht"][:10], "art": "beschreibung",
                        "staerke": hit["staerke"], "links": hit["links"][:3]})
        ban = VERBOT.search(v.get("beschreibung", ""))
        if ban:
            out.append({"url": v["url"], "zitat": _snippet(v["beschreibung"], ban, 100)[:300], "datum": v["veroeffentlicht"][:10],
                        "art": "verbot", "staerke": "verbot", "links": []})
    out.sort(key=lambda b: (b["art"] != "verbot", b["staerke"] != "eindeutig"))
    return out


def evidence_from_campaigns(creator: dict, camps: list[dict], channel_ids: list[str]) -> list[dict]:
    out = []
    ids = {c.lower() for c in channel_ids} | {y.lower() for y in creator["youtube"]}
    for c in camps:
        mentions = any(i in k.lower() for k in c["kanaele"] for i in ids if i)
        if mentions:
            out.append({"url": c["link"], "zitat": c["beschreibung"][:200], "datum": now().strftime("%Y-%m-%d"), "art": "kampagne",
                        "staerke": "kampagne", "bezahlt": c["satz_pro_1000"] is not None})
    return out


# --------------------------------------------------------------------------- Entdeckung (alle im Hype BEOBACHTEN)

MAX_NEU, MAX_SCAN, THIN_DAYS, MAX_TWITCH_PROBEN = 50, 60, 14, 10
CLIP_SUBS = ("LivestreamFail",)
SUCHEN = ("clipper gesucht", "clippers wanted")
JOB = re.compile(r"youtuber|streamer|influencer|vlogger|content creator|twitch|let'?s player|gamer", re.I)
NAME_STOP = {"the", "this", "that", "when", "after", "what", "why", "how", "who", "his", "her", "their", "new", "just", "now", "one",
             "man", "woman", "guy", "girl", "twitch", "kick", "youtube", "streamer", "streamers", "stream", "chat", "viewer", "viewers",
             "mod", "mods", "reddit", "clip", "clips", "live", "irl", "nsfw", "update", "breaking", "also", "while", "here", "there",
             "they", "she", "you", "mcdonald", "voice", "your", "our", "its", "and", "for", "from", "with", "not", "all", "some", "every", "another"}
NAME_RE = re.compile(r"^([A-Z][A-Za-z0-9_]{2,24})\b|\b([A-Z][A-Za-z0-9_]{2,24})(?='s\b)")


def _kkey(plattform: str, kanal: str, name: str) -> str:
    base = (kanal or name or "").strip().lower().lstrip("@")
    return f"{plattform}:{base}"


def _cand(name: str, plattform: str, kanal: str, grund: str, quelle: str, punkte: float, signal: dict | None = None,
          link: str = "", bestaetigt: bool = True) -> dict:
    return {"key": _kkey(plattform, kanal, name), "name": _norm(name)[:60], "plattform": plattform, "kanal": kanal,
            "grund": grund, "quellen": [quelle], "signal": dict(signal or {}), "punkte": round(punkte, 1), "link": link,
            "kanal_bestaetigt": bestaetigt}


def src_kampagnen(camps: list[dict]) -> list[dict]:
    """a) contentrewards-Kampagnen, die einen YouTube-Kanal nennen (gleiche Liste wie der Kampagnen-Scout, kein Extra-Abruf)."""
    out = []
    for c in camps:
        for url in c.get("kanaele", []):
            handle = url.rstrip("/").split("/")[-1]
            out.append(_cand(handle.lstrip("@"), "youtube", handle, f"Kampagne „{c['titel'][:60]}“ (contentrewards) nennt den Kanal",
                             "kampagne", 30, {"kampagnen": 1}, c["link"]))
    return out


def youtube_suche(query: str, limit: int = 10) -> list[dict]:
    res = subprocess.run(["yt-dlp", "--flat-playlist", "-J", f"ytsearchdate{limit}:{query}"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=90)
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError("YouTube-Suche nicht lesbar")
    return [e for e in json.loads(res.stdout).get("entries") or [] if isinstance(e, dict)]


def src_aufruf_suche() -> list[dict]:
    """b) Videos, deren TITEL einen Clipper-Aufruf nennt (Beweis folgt erst aus der Beschreibung im Beweis-Sucher)."""
    out = []
    for q in SUCHEN:
        for e in youtube_suche(q):
            title = e.get("title") or ""
            cid = e.get("channel_id") or ""
            if not cid or NOISE.search(title) or not (STRONG.search(title) or CALL.search(title)):
                continue
            out.append(_cand(e.get("channel") or e.get("uploader") or cid, "youtube", cid,
                             f"Videotitel nennt Clipper-Suche: „{_norm(title)[:80]}“", "aufruf", 25, {"aufruf_titel": True},
                             e.get("url") or ""))
    return out


def src_youtube_trends(trends: dict, cache: dict) -> list[dict]:
    """c) Kanäle der YouTube-mostPopular-Videos aus trends.json (Kanal-Handle per oEmbed, ohne Schlüssel; <= 15 neue Abrufe)."""
    out, fetched = [], 0
    for t in trends.get("themen", []):
        for q in t.get("quellen", []):
            if q.get("quelle") != "youtube" or not q.get("kanal") or not q.get("link"):
                continue
            info = cache.get(q["link"])
            if info is None:
                if fetched >= 15:
                    continue
                fetched += 1
                try:
                    j = common.fetch("https://www.youtube.com/oembed", params={"url": q["link"], "format": "json"}, timeout=10, retries=0).json()
                    info = {"name": j.get("author_name") or q["kanal"], "url": j.get("author_url") or ""}
                except Exception:                                  # noqa: BLE001
                    info = {"name": q["kanal"], "url": ""}
                cache[q["link"]] = info
            handle = (info.get("url") or "").rstrip("/").split("/")[-1]
            if handle:
                rang = int(q.get("rang") or 25)
                out.append(_cand(info["name"], "youtube", handle, f"YouTube-Trends {q.get('region', '')} Rang {rang}", "youtube-trends",
                                 max(5, 40 - 1.5 * rang), {"yt_trend_rang": rang, "region": q.get("region", "")}, q["link"]))
    return out


def wikidata_creator(qid: str) -> dict | None:
    """Beruf (Label passt zu YouTuber/Streamer/Influencer …) + YouTube-Kanal-ID (P2397) + Twitch-Name (P5797) aus Wikidata."""
    q = ("SELECT ?occ ?yt ?tw WHERE { VALUES ?e {wd:%s} ?e wdt:P106 ?o . ?o rdfs:label ?occ FILTER(lang(?occ)='en') "
         "OPTIONAL{?e wdt:P2397 ?yt} OPTIONAL{?e wdt:P5797 ?tw} } LIMIT 40" % qid)
    rows = common.fetch("https://query.wikidata.org/sparql", params={"query": q, "format": "json"}, timeout=30, retries=1).json()["results"]["bindings"]
    if not any(JOB.search(r["occ"]["value"]) for r in rows):
        return None
    pick = lambda k: next((r[k]["value"] for r in rows if k in r), "")
    return {"yt": pick("yt"), "tw": pick("tw").lower()}


def src_wikipedia(trends: dict, cache: dict) -> list[dict]:
    """f) Wikipedia-Top-Personen, die laut Wikidata-Beruf Streamer/YouTuber/Influencer sind (<= 5 neue Abfragen je Lauf, Negativtreffer gemerkt)."""
    out, looked = [], 0
    for t in trends.get("themen", []):
        if t.get("kategorie") != "Person":
            continue
        q = next((q for q in t.get("quellen", []) if q.get("quelle") == "wikipedia"), None)
        if not q:
            continue
        title = t["thema"]
        key = f"{q.get('region', 'de')}:{title}"
        info = cache.get(key)
        if info is None:
            if looked >= 5:
                continue
            looked += 1
            time.sleep(1.5)
            try:
                from urllib.parse import quote
                s = common.fetch(f"https://{q.get('region', 'de')}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}",
                                 timeout=10, retries=1).json()
                info = (wikidata_creator(s["wikibase_item"]) if s.get("wikibase_item") else None) or {}
            except Exception:                                      # noqa: BLE001 – später erneut versuchen
                continue
            cache[key] = info
        if not info:
            continue
        rang = int(q.get("rang") or 25)
        plat, kanal = ("youtube", info["yt"]) if info.get("yt") else ("twitch", info["tw"]) if info.get("tw") else ("unbekannt", "")
        out.append(_cand(title, plat, kanal, f"Wikipedia-Top Rang {rang} ({q.get('region', '')}), Beruf laut Wikidata passt",
                         "wikipedia", 20 + max(0, 26 - rang), {"wiki_rang": rang}, q.get("link", "")))
    return out


def streamer_namen(posts: list[dict]) -> dict[str, dict]:
    """Namen aus Beitragstiteln (Titelanfang oder „X's“): Anzahl Beiträge, bester Wert, ein Beleg-Link. Nur Zählung, keine Deutung."""
    found: dict[str, dict] = {}
    for p in posts:
        title = (p.get("title") or "").strip()
        for m in NAME_RE.finditer(title):
            name = m.group(1) or m.group(2)
            if name.lower() in NAME_STOP or re.fullmatch(r"[A-Z]{2,4}|[A-Z][a-z]?[A-Z]{2}", name):
                continue
            e = found.setdefault(name, {"n": 0, "punkte": 0, "link": ""})
            e["n"] += 1
            e["punkte"] = max(e["punkte"], int(p.get("score") or 0))
            e["link"] = e["link"] or p.get("link", "")
    return found


def src_reddit() -> list[dict]:
    """e) Oft genannte Streamer in Clip-Subreddits (Arctic Shift, letzte 48 h)."""
    from ..story.sources import ARCTIC
    out, end = [], int(time.time())
    for sub in CLIP_SUBS:
        data = common.fetch(f"{ARCTIC}/posts/search", params={"subreddit": sub, "after": end - 48 * 3600, "limit": 100, "sort": "desc",
                                                              "fields": "id,title,score,over_18"}, timeout=25, retries=1).json().get("data") or []
        posts = [{**d, "link": f"https://www.reddit.com/r/{sub}/comments/{d.get('id', '')}/"} for d in data if not d.get("over_18")]
        for name, e in streamer_namen(posts).items():
            if e["n"] >= 2 or e["punkte"] >= 150:
                login = name.lower() if re.fullmatch(r"[a-z0-9_]{4,25}", name.lower()) else ""
                out.append(_cand(name, "twitch", login, f"In r/{sub} {e['n']}× in Beitragstiteln genannt (48 h; Name aus Titeln, Kanal vermutet)",
                                 "reddit", 5 * e["n"] + min(e["punkte"] / 50, 10),
                                 {"reddit_beitraege": e["n"], "reddit_sub": sub}, e["link"], bestaetigt=False))
    return out


def merge_entdeckt(cands: list[dict], old: list[dict]) -> list[dict]:
    """Treffer nach Kanal zusammenführen, mit dem Bestand verbinden, höchstens MAX_NEU neue, nach THIN_DAYS ohne Sichtung entfernen."""
    stamp, cutoff = iso(), now() - timedelta(days=THIN_DAYS)
    merged: dict[str, dict] = {}
    for c in cands:
        m = merged.get(c["key"])
        if not m:
            merged[c["key"]] = c
            continue
        m["quellen"] = sorted(set(m["quellen"]) | set(c["quellen"]))
        m["signal"].update(c["signal"])
        if c["punkte"] > m["punkte"]:
            m["grund"], m["link"] = c["grund"], c["link"] or m["link"]
        m["punkte"] = round(min(100.0, m["punkte"] + c["punkte"]), 1)
        m["kanal_bestaetigt"] = m["kanal_bestaetigt"] or c["kanal_bestaetigt"]
        if not m["kanal"] and c["kanal"]:
            m["kanal"] = c["kanal"]
    old_by = {e.get("key"): e for e in old if isinstance(e, dict) and e.get("key")}
    out = []
    for key, e in old_by.items():
        seen = parse_time(e.get("zuletzt", ""))
        if key not in merged and seen and seen >= cutoff:
            out.append(e)                                       # nicht gesehen, aber noch frisch genug
    new = [c for k, c in merged.items() if k not in old_by]
    new.sort(key=lambda c: c["punkte"], reverse=True)
    for c in new[:MAX_NEU] + [c for k, c in merged.items() if k in old_by]:
        before = old_by.get(c["key"]) or {}
        out.append({**before, **{k: v for k, v in c.items()}, "erste_sichtung": before.get("erste_sichtung", stamp), "zuletzt": stamp})
    out.sort(key=lambda e: e.get("punkte", 0), reverse=True)
    return out


def entdecke(notes: list[str], camps: list[dict], old: list[dict], cache: dict) -> list[dict]:
    """Alle Quellen einzeln abgesichert -> zusammengeführte, begrenzte Liste (noch ohne Erlaubnis-Status)."""
    trends = common.read_json("trends.json", {}) or {}
    cands: list[dict] = []
    for name, func in (("Entdeckung Kampagnen", lambda: src_kampagnen(camps)),
                       ("Entdeckung Aufruf-Suche", src_aufruf_suche),
                       ("Entdeckung YouTube-Trends", lambda: src_youtube_trends(trends, cache.setdefault("oembed", {}))),
                       ("Entdeckung Reddit", src_reddit),
                       ("Entdeckung Wikipedia-Personen", lambda: src_wikipedia(trends, cache.setdefault("wikidata", {})))):
        cands += common.run_source(name, func, notes)
    notes.append("Twitch-Top-Liste: ohne Anmeldung gibt es keine öffentliche Quelle – Twitch-Kanäle kommen über Reddit, Wikidata und Kampagnen.")
    return merge_entdeckt(cands, old)


# --------------------------------------------------------------------------- Lauf

def duldung_signale(eintrag: dict | None, scan: dict, belege: list[dict]) -> list[str]:
    """Beobachtete Duldungssignale (Text beginnt mit der Art). Duldung ist keine Erlaubnis."""
    s = (eintrag or {}).get("signal") or {}
    out = []
    if s.get("reddit_beitraege", 0) >= 2:
        out.append(f"Reddit: {s['reddit_beitraege']} Beiträge in r/{s.get('reddit_sub', '?')} über den Creator (48 h)")
    if len(scan["clips"]) >= 3:
        out.append(f"Twitch-Clips: {len(scan['clips'])} öffentliche Clips der letzten 24 h")
    if s.get("yt_trend_rang"):
        out.append(f"Trends: YouTube-Trends {s.get('region', '')} Rang {s['yt_trend_rang']}")
    elif s.get("wiki_rang"):
        out.append(f"Trends: Wikipedia-Top Rang {s['wiki_rang']}")
    if any(b.get("art") == "kampagne" for b in belege):
        out.append("Kampagne: contentrewards-Kampagne nennt den Kanal")
    return out


def _scan_twitch_ok(c: dict, budget: dict | None) -> bool:
    if budget is None:
        return True
    if budget["twitch"] <= 0:
        return False
    budget["twitch"] -= 1
    return True


def _scan_creator(c: dict, cache: dict, notes: list[str], budget: dict | None = None) -> dict:
    cids, videos = [], []
    for entry in c["youtube"]:
        try:
            cid = resolve_channel(entry, cache)
            if not cid:
                notes.append(f"{c['name']}: YouTube-Kanal „{entry}“ nicht gefunden.")
                continue
            cids.append(cid)
            _, vids = parse_feed(common.fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", timeout=20).content)
            median = statistics.median(v["aufrufe_je_stunde"] for v in vids) if vids else 0
            for v in vids:
                v["faktor"] = round(v["aufrufe_je_stunde"] / median, 2) if median else 0
                v["plattform"] = "youtube"
            videos += vids
        except Exception as exc:                          # noqa: BLE001 – ein kaputter Kanal stoppt den Lauf nicht
            notes.append(f"{c['name']}: YouTube {entry} nicht erreichbar ({common.short_error(exc)})")
    clips = []
    for login in c["twitch"]:
        if not _scan_twitch_ok(c, budget):
            continue
        try:
            for t in twitch_clips(login):
                t.update(plattform="twitch", faktor=0)
                clips.append(t)
        except Exception as exc:                          # noqa: BLE001
            notes.append(f"{c['name']}: Twitch {login} nicht erreichbar ({common.short_error(exc)})")
    return {"cids": cids, "videos": videos, "clips": clips}


def _process(c: dict, cache: dict, camps: list[dict], old_by: dict, notes: list[str], eintrag: dict | None = None,
             budget: dict | None = None) -> dict:
    scan = _scan_creator(c, cache, notes, budget)
    belege = merge_belege((old_by.get(c["name"]) or {}).get("belege", []),
                          evidence_from_videos(scan["videos"]) + evidence_from_campaigns(c, camps, scan["cids"]))
    signale = duldung_signale(eintrag, scan, belege)
    unsicher = bool(eintrag) and not eintrag.get("kanal_bestaetigt", True) and not any(b.get("art") == "kampagne" for b in belege)
    verdict = decide(c, belege, [] if unsicher else signale, lesbar=bool(scan["videos"]))
    if unsicher and verdict["status"] == "unklar":
        verdict["bedingungen"].append("Kanal nur aus Beitragstiteln vermutet – nicht bestätigt, daher keine Duldung angenommen")
    erl = {"name": c["name"], "kanaele": {"youtube": scan["cids"] or c["youtube"], "twitch": c["twitch"], "tiktok": c["tiktok"]},
           **verdict, "belege": [{k: b[k] for k in ("url", "zitat", "datum", "art") if k in b} | {"staerke": b.get("staerke", "")}
                                 for b in belege], "geprueft": iso()}
    status = verdict["status"]
    if status == "gesperrt":
        why = "gesperrt: " + (verdict["bedingungen"][0] if verdict["bedingungen"] else "")
    elif status == "erlaubt":
        first = next((b for b in belege if b.get("staerke") == "eindeutig"), belege[0])
        why = "Aufruf des Creators: „" + first["zitat"][:90] + "“"
    elif status == "geduldet":
        why = "geduldet (Signale: " + "; ".join(verdict["signale"]) + ") – nicht ausdrücklich erlaubt"
    else:
        why = "keine belegte Erlaubnis"
    rows = [{"creator": c["name"], "plattform": v["plattform"], "url": v["url"], "titel": v["titel"], "aufrufe": v["aufrufe"],
             "aufrufe_je_stunde": v["aufrufe_je_stunde"], "faktor": v.get("faktor", 0), "veroeffentlicht": v["veroeffentlicht"],
             "erlaubt": status == "erlaubt", "erlaubnis": status, "signale": verdict["signale"], "grund": why}
            for v in [v for v in scan["videos"] if v["alter_stunden"] <= MAX_AGE_H] + scan["clips"]]
    return {"erl": erl, "rows": rows, "scan": scan, "status": status, "signale": verdict["signale"]}


def _manual_keys(c: dict, cids: list[str]) -> set[str]:
    return ({c["name"].lower()} | {y.lower().lstrip("@") for y in c["youtube"]} | {t.lower() for t in c["twitch"]}
            | {x.lower() for x in cids})


def _vorschlag(r: dict) -> dict:
    base = {"art": "clip", "quelle": r["url"], "url": r["url"], "sprache": "de", "titel": r["titel"], "creator": r["creator"],
            "beleg": r["grund"], "erlaubnis": r["erlaubnis"], "credit": f"Original: {r['creator']} – {r['url']}"}
    if r["erlaubnis"] == "geduldet":
        return {**base, "signale": r["signale"], "hinweis": "Geduldet, nicht ausdrücklich erlaubt – Start nur mit Bestätigung "
                "(bestaetigt_erlaubnis) in der App; Credit „Original: <Creator> – <Link>“ ist Pflicht."}
    return {**base, "hinweis": "Erlaubnis im Prüfbericht belegt; vor dem Start in der App bestätigen."}


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    creators = load_creators(notes)
    old = common.read_json(ERLAUBNIS, {}) or {}
    old_by = {c.get("name"): c for c in old.get("creators", []) if isinstance(c, dict)}
    radar_old = common.read_json(RADAR, {}) or {}
    ent_old = common.read_json(ENT, {}) or {}
    cache = dict(radar_old.get("kanal_ids") or {})
    camps = common.run_source("Kampagnen-Scout", lambda: campaigns(notes), notes)
    ent_cache = dict(ent_old.get("cache") or {})
    entdeckt = entdecke(notes, camps, ent_old.get("creators", []), ent_cache)

    radar_rows: list[dict] = []
    erlaubnis: list[dict] = []
    manual_keys: dict[str, str] = {}                       # Schlüssel -> Status des manuellen Creators (Sperre gewinnt)
    for c in creators:
        res = _process(c, cache, camps, old_by, notes)
        erlaubnis.append(res["erl"])
        radar_rows += res["rows"]
        for k in _manual_keys(c, res["scan"]["cids"]):
            manual_keys[k] = res["status"]

    budget = {"twitch": MAX_TWITCH_PROBEN}
    scanned = 0
    for e in entdeckt:
        c = {"name": e["name"], "youtube": [e["kanal"]] if e["plattform"] == "youtube" and e["kanal"] else [],
             "twitch": [e["kanal"]] if e["plattform"] == "twitch" and e["kanal"] else [], "tiktok": [], "gesperrt": False}
        dup = manual_keys.get(e["name"].lower()) or manual_keys.get(str(e["kanal"]).lower().lstrip("@"))
        if dup:
            e.update(erlaubnis=dup, signale=[], bereits_manuell=True)
            continue
        if not (c["youtube"] or c["twitch"]) or scanned >= MAX_SCAN:
            prev = old_by.get(e["name"])
            if prev:                                        # nicht neu geprüft: letzter Stand bleibt
                erlaubnis.append(prev)
                e.update(erlaubnis=prev.get("status", "unklar"), signale=prev.get("signale", []))
            else:
                e.update(erlaubnis="unklar", signale=[])
            continue
        scanned += 1
        res = _process(c, cache, camps, old_by, notes, eintrag=e, budget=budget)
        cids = {x.lower() for x in res["scan"]["cids"]}
        hit = next((manual_keys[k] for k in cids if k in manual_keys), None)
        if hit:                                             # derselbe Kanal wie ein manueller Creator: dessen Status gilt
            e.update(erlaubnis=hit, signale=[], bereits_manuell=True)
            continue
        erlaubnis.append(res["erl"])
        radar_rows += res["rows"]
        speed = max([r["aufrufe_je_stunde"] for r in res["rows"]] or [0])
        e["signal"]["aufrufe_je_stunde"] = speed
        if any(b["art"] == "beschreibung" and b.get("staerke") == "eindeutig" for b in res["erl"]["belege"]):
            e["signal"]["aufruf"] = True
        e.update(erlaubnis=res["status"], signale=res["signale"], aufrufe_je_stunde=speed)
        e["kanal_geprueft"] = bool(res["scan"]["videos"] or res["scan"]["clips"])
    radar_rows.sort(key=lambda r: r["aufrufe_je_stunde"], reverse=True)

    vorschlaege = []
    for stufe in ("erlaubt", "geduldet"):                   # Belegtes zuerst; unklar/gesperrt nie
        for r in radar_rows:
            if r["erlaubnis"] == stufe and (r["faktor"] >= MIN_FAKTOR or r["plattform"] == "twitch") and len(vorschlaege) < 8:
                vorschlaege.append(_vorschlag(r))
    calls = [{"creator": e["name"], **b} for e in erlaubnis for b in e["belege"] if b["art"] == "beschreibung"][:10]
    offen = [{"name": e["name"], "plattform": e["plattform"], "link": e.get("link", ""), "grund": e["grund"],
              "aufrufe_je_stunde": e.get("aufrufe_je_stunde", 0)}
             for e in entdeckt if e.get("erlaubnis") == "unklar" and not e.get("bereits_manuell")][:10]

    n_creators = len(creators) + scanned
    radar = {"erzeugt": iso(), "creators": n_creators, "videos": radar_rows[:60], "vorschlaege": vorschlaege,
             "aufrufe_gefunden": calls, "kampagnen": camps[:15], "kanal_ids": cache, "im_hype_erlaubnis_offen": offen,
             "clip_posts": radar_old.get("clip_posts", []), "hinweise": notes[:20]}
    common.write_json(RADAR, radar)
    common.write_json(ERLAUBNIS, {"erzeugt": iso(), "creators": erlaubnis})
    for k, v in list(ent_cache.items()):                    # Zwischenspeicher klein halten
        if isinstance(v, dict) and len(v) > 300:
            ent_cache[k] = dict(list(v.items())[-300:])
    common.write_json(ENT, {"erzeugt": iso(), "anzahl": len(entdeckt), "hinweise": notes[:20], "cache": ent_cache, "creators": entdeckt})
    stufen = {s: sum(1 for e in erlaubnis if e["status"] == s) for s in ("erlaubt", "geduldet", "unklar", "gesperrt")}
    summary = (f"{len(entdeckt)} Creator entdeckt, {n_creators} geprüft: {stufen['erlaubt']} erlaubt, {stufen['geduldet']} geduldet, "
               f"{stufen['unklar']} unklar, {stufen['gesperrt']} gesperrt; {len(radar_rows)} aktuelle Videos/Clips, "
               f"{len(vorschlaege)} Vorschläge, {len(camps)} offene Kampagnen")
    common.record_status("clipscout", started, True, summary, notes)
    return radar
