"""Messung (kostenlos, kein Claude-Verbrauch): Aufrufe/Likes/Kommentare eigener Posts als Zeitreihe in `messung.json`.

Post-Links kommen aus `uploads.json` (Feld `url`, bei YouTube sonst `video_id`) und `clip_radar.json` -> `clip_posts`.
Gelesen werden nur öffentliche Zahlen per yt-dlp, ohne Konto und ohne Cookies. Nicht lesbar = Hinweis, nie geschätzt.
Der Lern-Analyst nutzt die Reihe, wenn YouTube-/TikTok-API fehlen (`latest`).
"""

from __future__ import annotations

import subprocess
import time
from datetime import timedelta

from . import common
from .common import iso, now, parse_time

FILE = "messung.json"
MAX_POSTS = 40                  # je Lauf
MAX_POINTS = 200                # je Post
MIN_GAP_H = 1.0                 # nicht öfter als stündlich einen Punkt anhängen
KEEP_DAYS = 120
PLATFORMS = (("tiktok.com", "tiktok"), ("youtube.com", "youtube"), ("youtu.be", "youtube"), ("instagram.com", "instagram"),
             ("twitch.tv", "twitch"))


def platform(url: str) -> str:
    return next((name for host, name in PLATFORMS if host in url), "web")


def post_urls() -> list[dict]:
    """Eigene Post-Links ohne Doppelte: [{url, plattform, quelle}]."""
    out: dict[str, dict] = {}
    for r in (common.read_json("uploads.json", {}) or {}).get("eintraege", []):
        url = r.get("url") or (f"https://www.youtube.com/watch?v={r['video_id']}" if r.get("ziel") == "youtube" and r.get("video_id") else "")
        if str(url).startswith("http"):
            out.setdefault(url, {"url": url, "plattform": platform(url), "quelle": "uploads"})
    for p in (common.read_json("clip_radar.json", {}) or {}).get("clip_posts", []):
        url = p.get("url") if isinstance(p, dict) else p
        if isinstance(url, str) and url.startswith("http"):
            out.setdefault(url, {"url": url, "plattform": platform(url), "quelle": "clip_posts"})
    return list(out.values())


def read_stats(url: str) -> dict | None:
    """Öffentliche Zahlen per yt-dlp (ohne Konto); None = nicht lesbar."""
    res = subprocess.run(["yt-dlp", "--skip-download", "--no-playlist", "--print",
                          "%(view_count)s|%(like_count)s|%(comment_count)s", url],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    parts = ((res.stdout or "").strip().splitlines() or [""])[-1].split("|")
    if len(parts) < 3 or not parts[0].isdigit():
        return None
    num = lambda x: int(x) if x.isdigit() else None
    return {"zeit": iso(), "aufrufe": int(parts[0]), "likes": num(parts[1]), "kommentare": num(parts[2])}


def add_point(entry: dict, point: dict) -> bool:
    """Punkt anhängen (nicht öfter als stündlich, begrenzte Länge). True = angehängt."""
    series = entry.setdefault("verlauf", [])
    last = parse_time(series[-1]["zeit"]) if series else None
    if last and (parse_time(point["zeit"]) - last) < timedelta(hours=MIN_GAP_H):
        return False
    series.append(point)
    del series[:-MAX_POINTS]
    return True


def latest(url: str, data: dict | None = None) -> dict | None:
    """Letzte Messung eines Posts (für den Lern-Analysten) oder None."""
    data = data if data is not None else (common.read_json(FILE, {}) or {})
    series = (data.get("posts", {}).get(url) or {}).get("verlauf") or []
    return series[-1] if series else None


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    old = common.read_json(FILE, {}) or {}
    posts = old.get("posts", {})
    urls = post_urls()
    if not urls:
        notes.append("Noch keine Post-Links (uploads.json / clip_radar.json clip_posts) – nichts zu messen.")
    measured = failed = 0
    for p in urls[:MAX_POSTS]:
        entry = posts.setdefault(p["url"], {"plattform": p["plattform"], "quelle": p["quelle"], "verlauf": []})
        try:
            point = read_stats(p["url"])
        except Exception as exc:                          # noqa: BLE001 – ein Post stoppt den Lauf nicht
            point = None
            entry["fehler"] = common.short_error(exc)
        if point is None:
            failed += 1
            entry.setdefault("fehler", "Zahlen nicht öffentlich lesbar")
            continue
        entry.pop("fehler", None)
        measured += add_point(entry, point)
    if failed:
        notes.append(f"{failed} Post(s) nicht lesbar (Plattform sperrt oder Link ungültig).")
    cutoff = now() - timedelta(days=KEEP_DAYS)
    posts = {u: e for u, e in posts.items()
             if e.get("verlauf") and (parse_time(e["verlauf"][-1]["zeit"]) or now()) >= cutoff or u in {p["url"] for p in urls}}
    views = [e["verlauf"][-1]["aufrufe"] for e in posts.values() if e.get("verlauf")]
    data = {"erzeugt": iso(), "posts": posts, "anzahl": len(posts), "gesamt_aufrufe": sum(views), "hinweise": notes[:10]}
    common.write_json(FILE, data)
    common.record_status("messung", started, True,
                         f"{len(posts)} Posts, {measured} neue Messpunkte, {sum(views)} Aufrufe gesamt" if posts
                         else "Keine Post-Links vorhanden – nichts gemessen", notes)
    return data
