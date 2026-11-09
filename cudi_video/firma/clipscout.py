"""Clip-Scout (kostenlos, kein Claude-Verbrauch): findet Material, das geclippt werden darf – und belegt, warum.

Vier Aufgaben, jede Quelle einzeln abgesichert:
 a) Trend-Radar: YouTube-Kanalfeeds (RSS, ohne Schlüssel) + öffentliche Twitch-Clips (yt-dlp, ohne Anmeldung) der Creator aus
    `clip_creators.json` -> Aufrufe je Stunde (`clip_radar.json`).
 b) Aufruf-Finder: Videobeschreibungen nach „Clipper gesucht / clips erlaubt / clip my streams“ (de/en).
 c) Kampagnen-Scout: öffentliche Liste contentrewards.com/c/discover (robots.txt wird geprüft, ein Abruf).
 d) Beweis-Sucher: wörtliches Zitat + Link + Datum -> `clip_erlaubnis.json`. „erlaubt“ gibt es NUR mit eindeutigem Aufruf
    des Creators selbst (Beleg); Kampagnen und schwache Hinweise bleiben „unklar“; ein Sperr-Eintrag des Nutzers gewinnt immer.
Nichts wird erfunden: ohne Creator-Liste bleibt alles ehrlich leer (mit Hinweis).
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

CREATORS, RADAR, ERLAUBNIS = "clip_creators.json", "clip_radar.json", "clip_erlaubnis.json"
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
        notes.append("clip_creators.json fehlt oder ist leer – bitte Creator eintragen (Beispiel: docs/clip-team.md).")
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
        notes.append("clip_creators.json enthält keinen Creator – bitte eintragen (Beispiel: docs/clip-team.md).")
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

def decide(creator: dict, belege: list[dict]) -> dict:
    """Status aus Beleg-Lage. Sperre des Nutzers gewinnt; „erlaubt“ nur mit eindeutigem Aufruf vom Creator selbst (Zitat+Link+Datum)."""
    bedingungen: list[str] = []
    if creator.get("gesperrt"):
        return {"status": "gesperrt", "monetarisierung": "unklar", "bedingungen": ["vom Nutzer gesperrt (clip_creators.json)"]}
    good = [b for b in belege if b.get("url") and b.get("zitat") and b.get("datum") and b.get("art") == "beschreibung"
            and b.get("staerke") == "eindeutig"]
    camp = [b for b in belege if b.get("art") == "kampagne"]
    paid = any(b.get("bezahlt") for b in camp) or any(re.search(r"verdien|bezahl|geld|paid|€|\$", b.get("zitat", ""), re.I) for b in good)
    if good:
        links = sorted({l for b in good for l in b.get("links", [])})
        if links:
            bedingungen.append("Regeln laut Link: " + ", ".join(links[:3]))
        return {"status": "erlaubt", "monetarisierung": "ja" if paid else "unklar", "bedingungen": bedingungen}
    if camp:
        bedingungen.append("Kampagne gefunden – erst nach bestätigtem Beitritt und mit deren Regeln erlaubt")
    elif belege:
        bedingungen.append("nur schwacher Hinweis – Aufruf nicht eindeutig")
    return {"status": "unklar", "monetarisierung": "ja" if paid else "unklar", "bedingungen": bedingungen}


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
    out.sort(key=lambda b: b["staerke"] != "eindeutig")
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


# --------------------------------------------------------------------------- Lauf

def _scan_creator(c: dict, cache: dict, notes: list[str]) -> dict:
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
        try:
            for t in twitch_clips(login):
                t.update(plattform="twitch", faktor=0)
                clips.append(t)
        except Exception as exc:                          # noqa: BLE001
            notes.append(f"{c['name']}: Twitch {login} nicht erreichbar ({common.short_error(exc)})")
    return {"cids": cids, "videos": videos, "clips": clips}


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    creators = load_creators(notes)
    old = common.read_json(ERLAUBNIS, {}) or {}
    old_by = {c.get("name"): c for c in old.get("creators", []) if isinstance(c, dict)}
    radar_old = common.read_json(RADAR, {}) or {}
    cache = dict(radar_old.get("kanal_ids") or {})
    camps = common.run_source("Kampagnen-Scout", lambda: campaigns(notes), notes)

    radar_rows: list[dict] = []
    erlaubnis: list[dict] = []
    for c in creators:
        scan = _scan_creator(c, cache, notes)
        recent = [v for v in scan["videos"] if v["alter_stunden"] <= MAX_AGE_H]
        belege = merge_belege((old_by.get(c["name"]) or {}).get("belege", []),
                              evidence_from_videos(scan["videos"]) + evidence_from_campaigns(c, camps, scan["cids"]))
        verdict = decide(c, belege)
        erlaubnis.append({"name": c["name"], "kanaele": {"youtube": scan["cids"] or c["youtube"], "twitch": c["twitch"], "tiktok": c["tiktok"]},
                          **verdict, "belege": [{k: b[k] for k in ("url", "zitat", "datum", "art") if k in b} | {"staerke": b.get("staerke", "")}
                                                for b in belege], "geprueft": iso()})
        if c.get("gesperrt"):
            why = "vom Nutzer gesperrt"
        elif verdict["status"] == "erlaubt":
            why = "Aufruf des Creators: „" + belege[0]["zitat"][:90] + "“"
        else:
            why = "keine belegte Erlaubnis"
        for v in recent + scan["clips"]:
            radar_rows.append({"creator": c["name"], "plattform": v["plattform"], "url": v["url"], "titel": v["titel"],
                               "aufrufe": v["aufrufe"], "aufrufe_je_stunde": v["aufrufe_je_stunde"], "faktor": v.get("faktor", 0),
                               "veroeffentlicht": v["veroeffentlicht"], "erlaubt": verdict["status"] == "erlaubt", "grund": why})
    radar_rows.sort(key=lambda r: r["aufrufe_je_stunde"], reverse=True)

    vorschlaege = []
    for r in radar_rows:
        if r["erlaubt"] and (r["faktor"] >= MIN_FAKTOR or r["plattform"] == "twitch") and len(vorschlaege) < 5:
            vorschlaege.append({"art": "clip", "quelle": r["url"], "url": r["url"], "sprache": "de",
                                "titel": r["titel"], "creator": r["creator"], "beleg": r["grund"],
                                "hinweis": "Erlaubnis im Prüfbericht belegt; vor dem Start in der App bestätigen."})
    calls = [{"creator": e["name"], **b} for e in erlaubnis for b in e["belege"] if b["art"] == "beschreibung"][:10]

    radar = {"erzeugt": iso(), "creators": len(creators), "videos": radar_rows[:60], "vorschlaege": vorschlaege,
             "aufrufe_gefunden": calls, "kampagnen": camps[:15], "kanal_ids": cache,
             "clip_posts": radar_old.get("clip_posts", []), "hinweise": notes[:20]}
    common.write_json(RADAR, radar)
    common.write_json(ERLAUBNIS, {"erzeugt": iso(), "creators": erlaubnis})
    n_ok = sum(1 for e in erlaubnis if e["status"] == "erlaubt")
    summary = (f"{len(creators)} Creator, {n_ok} mit belegter Erlaubnis, {len(radar_rows)} aktuelle Videos/Clips, "
               f"{len(vorschlaege)} Vorschläge, {len(camps)} offene Kampagnen") if creators else \
        f"Keine Creator eingetragen (clip_creators.json), {len(camps)} offene Kampagnen gelesen"
    common.record_status("clipscout", started, True, summary, notes)
    return radar
