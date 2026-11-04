"""Bilder und Clips je Szene.

Reihenfolge („Videos bevorzugt“): Stockvideos von Pexels/Pixabay (kostenlose Schlüssel, freie Lizenz) oder –
ohne Schlüssel – freie Clips von Wikimedia Commons (nur wenn der Titel zum Suchbegriff passt), KI-Bilder von
Pollinations (ohne Schlüssel, werden im Video animiert), eigene Clips aus video_assets/backgrounds
(z. B. eigene Gameplay-Aufnahmen), sonst ein Farbverlauf.
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from .. import config, net

log = logging.getLogger(__name__)

CLIP_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv")


@dataclass
class Visual:
    kind: str                 # video | image | none
    path: str | None = None
    credit: str = ""          # für Beschreibung/Prüfbericht
    query: str = ""
    start: float = 0.0        # Startpunkt in eigenen Clips

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- Stockvideos

def pexels(query: str, used: set) -> Visual | None:
    if not config.PEXELS_API_KEY:
        return None
    for orientation in ("portrait", None):          # Hochformat bevorzugt, sonst mittig zugeschnitten
        params = {"query": query, "per_page": 15, "size": "medium"}
        if orientation:
            params["orientation"] = orientation
        data = net.get_json("https://api.pexels.com/videos/search", params=params,
                            headers={"Authorization": config.PEXELS_API_KEY}, cache_hours=24 * 7, retries=2)
        for video in data.get("videos", []):
            key = f"pexels:{video['id']}"
            if key in used or video.get("duration", 0) < 4:
                continue
            files = [f for f in video.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 720]
            if not files:
                continue
            best = min(files, key=lambda f: abs((f.get("height") or 0) - 1920) + (f.get("width") or 0) // 4)
            path = net.download(best["link"], suffix=".mp4", timeout=120)
            used.add(key)
            return Visual("video", str(path), f"Pexels – {video.get('user', {}).get('name', 'unbekannt')}", query)
    return None


def pixabay(query: str, used: set) -> Visual | None:
    if not config.PIXABAY_API_KEY:
        return None
    data = net.get_json("https://pixabay.com/api/videos/", params={"key": config.PIXABAY_API_KEY, "q": query,
                                                                  "per_page": 20, "safesearch": "true"},
                        cache_hours=24 * 7, retries=2)
    for hit in data.get("hits", []):
        key = f"pixabay:{hit['id']}"
        if key in used or hit.get("duration", 0) < 4:
            continue
        for size in ("large", "medium"):
            file = hit.get("videos", {}).get(size) or {}
            if file.get("url") and (file.get("height") or 0) >= 720:
                path = net.download(file["url"], suffix=".mp4", timeout=120)
                used.add(key)
                return Visual("video", str(path), f"Pixabay – {hit.get('user', 'unbekannt')}", query)
    return None


# --------------------------------------------------------------------------- KI-Bilder

_ai_lock = threading.Lock()
_ai_last = [0.0]
_ai_failures = [0]
AI_INTERVAL = 16.0          # ohne Zugang erlaubt Pollinations nur etwa ein Bild alle 15 Sekunden
AI_MAX_FAILURES = 2         # danach in diesem Lauf keine KI-Bilder mehr anfragen (Dienst überlastet)


def ai_image(prompt: str, seed: int) -> Visual | None:
    """KI-Bild (Pollinations) im Hochformat – ohne Zugang 576×1024 mit Logo, mit Zugang 1080×1920."""
    size = "width=1080&height=1920&nologo=true" if config.POLLINATIONS_TOKEN else "width=576&height=1024"
    url = f"https://image.pollinations.ai/prompt/{quote(prompt[:400])}?{size}&seed={seed}&model=flux"
    headers = {"Authorization": f"Bearer {config.POLLINATIONS_TOKEN}"} if config.POLLINATIONS_TOKEN else None
    cached = net.cached_file(url, ".jpg")
    if cached is None and _ai_failures[0] >= AI_MAX_FAILURES:
        return None
    try:
        if cached is None:
            with _ai_lock:                          # nacheinander und mit Abstand – sonst 402/503
                wait = AI_INTERVAL - (time.time() - _ai_last[0])
                if wait > 0 and not config.POLLINATIONS_TOKEN:
                    time.sleep(wait)
                try:
                    cached = net.download(url, suffix=".jpg", retries=3, max_wait=30, timeout=180, headers=headers,
                                          retry_on=(402, 429, 500, 502, 503, 504))
                finally:
                    _ai_last[0] = time.time()
        with Image.open(cached) as img:
            img.verify()
    except Exception as exc:                        # Bild ist optional
        _ai_failures[0] += 1
        log.warning("KI-Bild nicht verfügbar (%s): %s", prompt[:60], exc)
        return None
    _ai_failures[0] = 0
    return Visual("image", str(cached), "KI-Bild (Pollinations)", prompt)


# --------------------------------------------------------------------------- freie Fotos (Wikimedia Commons)

NON_FREE = ("non-free", "fair use", "copyrighted", "all rights reserved")


def commons_photo(query: str, used: set) -> Visual | None:
    """Frei lizenziertes Foto von Wikimedia Commons (ohne Schlüssel) – Hochformat bevorzugt.

    Nur Bilder mit Urheber (oder gemeinfrei): die Lizenz verlangt sonst eine Namensnennung."""
    from ..enrich import credit_author

    data = net.get_json("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "formatversion": 2, "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo",
        "iiprop": "url|size|extmetadata", "iiurlwidth": 1080,
        "iiextmetadatafilter": "LicenseShortName|Artist|Attribution|AttributionRequired",
    }, cache_hours=24 * 7, retries=2, max_wait=20)
    pages = sorted(data.get("query", {}).get("pages", []), key=lambda pg: pg.get("index", 99))
    candidates = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = meta.get("LicenseShortName", {}).get("value", "")
        if (not license_name or any(x in license_name.lower() for x in NON_FREE) or page["title"] in used
                or (info.get("width") or 0) < 800 or (info.get("height") or 0) < 800 or not info.get("thumburl")):
            continue
        artist = credit_author(meta, license_name)
        if not artist:
            continue
        portrait = info["height"] >= info["width"]
        candidates.append((not portrait, page, info, license_name, artist))
    if not candidates:
        return None
    _, page, info, license_name, artist = min(candidates, key=lambda c: c[0])
    path = net.download(info["thumburl"], suffix=".jpg", retries=2, max_wait=20)
    used.add(page["title"])
    return Visual("image", str(path), f"Foto: {artist[:60]} – {license_name} – Wikimedia Commons", query)


# --------------------------------------------------------------------------- freie Clips (Wikimedia Commons)

CLIP_SKIP = ("interview", "lecture", "speech", "conference", "presentation", "talk", "song", "music", "trailer",
             "news", "documentary", "podcast", "webinar", "tutorial", "wikipedia", "wikimania", "session", "slides")
QUERY_STOP = {"dark", "close", "view", "shot", "scene", "with", "from", "into", "over", "under", "very", "light"}


def _query_words(query: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{4,}", query.lower()) if w not in QUERY_STOP]


def _best_derivative(info: dict) -> str:
    """Größte WebM-Ableitung (Commons rechnet jedes Video in mehrere Größen um): bis 1080p bei kurzen Clips,
    bis 720p bei längeren – sonst wären es schnell 50 MB und mehr für ein paar Sekunden Bild."""
    top = 1080 if (info.get("duration") or 0) <= 30 else 720
    ders = [d for d in info.get("derivatives", []) if "webm" in (d.get("type") or "")
            and 480 <= (d.get("height") or 0) <= top and d.get("src")]
    return max(ders, key=lambda d: d["height"])["src"] if ders else ""


def commons_video(query: str, used: set) -> Visual | None:
    """Frei lizenzierter Videoclip von Wikimedia Commons (ohne Schlüssel) – nur, wenn der Dateititel ein
    Wort des Suchbegriffs enthält (sonst lieber ein KI-Bild als ein unpassender Clip); mit Urheberangabe."""
    from ..enrich import credit_author

    words = _query_words(query)
    if not words:
        return None
    searches = [" ".join(words)] + (words if len(words) > 1 else [])
    for search in searches:
        data = net.get_json("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "format": "json", "formatversion": 2, "generator": "search",
            "gsrsearch": f"{search} filetype:video", "gsrnamespace": 6, "gsrlimit": 15, "prop": "videoinfo",
            "viprop": "url|size|mime|derivatives|extmetadata",
            "viextmetadatafilter": "LicenseShortName|Artist|Attribution|AttributionRequired",
        }, cache_hours=24 * 7, retries=2, max_wait=20)
        for page in sorted(data.get("query", {}).get("pages", []), key=lambda pg: pg.get("index", 99)):
            title = page.get("title", "")
            low = title.lower()
            if title in used or not any(w in low for w in words) or any(x in low for x in CLIP_SKIP):
                continue
            info = (page.get("videoinfo") or [{}])[0]
            if not 3 <= (info.get("duration") or 0) <= 120:
                continue
            meta = info.get("extmetadata", {})
            license_name = meta.get("LicenseShortName", {}).get("value", "")
            if not license_name or any(x in license_name.lower() for x in NON_FREE):
                continue
            artist = credit_author(meta, license_name)
            src = _best_derivative(info)
            if not artist or not src:
                continue
            path = net.download(src, suffix=".webm", retries=2, max_wait=20, timeout=180)
            used.add(title)
            return Visual("video", str(path), f"Clip: {artist[:60]} – {license_name} – Wikimedia Commons", query)
    return None


# --------------------------------------------------------------------------- eigene Clips

def own_clips(mood: str) -> list[Path]:
    """Eigene Clips: video_assets/backgrounds/<stimmung>/ oder video_assets/backgrounds/."""
    base = config.ASSETS_DIR / "backgrounds"
    for folder in (base / mood, base):
        if folder.exists():
            clips = sorted(p for p in folder.iterdir() if p.suffix.lower() in CLIP_SUFFIXES)
            if clips:
                return clips
    return []


def own_clip(mood: str, rnd: random.Random) -> Visual | None:
    clips = own_clips(mood)
    if not clips:
        return None
    clip = rnd.choice(clips)
    return Visual("video", str(clip), "eigener Clip", clip.stem, start=rnd.uniform(0, 60))


# --------------------------------------------------------------------------- Auswahl je Szene

ORDER = {
    "videos": ("stock", "ai", "photo", "own"),
    "images": ("ai", "photo", "stock", "own"),
    "gameplay": ("own", "stock", "ai", "photo"),
    "cartoon": ("ai", "photo", "own", "stock"),
}

# Cartoon-Stil: gleiche Zeichenart und – wo eine Person vorkommt – dieselbe Hauptfigur in jeder Szene
CARTOON_STYLE = {
    "creepy": "dark moody palette, deep blues and greens, eerie but not gory",
    "suspense": "tense dramatic lighting, strong contrast",
    "funny": "bright playful colors, exaggerated expressions",
    "drama": "warm emotional colors, expressive faces",
    "revenge": "bold confident colors, smug expressions",
    "wholesome": "soft pastel colors, gentle warm light",
}
PERSON = re.compile(r"\b(man|woman|person|people|guy|girl|boy|narrator|figure|he|she|they|i|me|someone|couple|"
                    r"friend|husband|wife|mother|father|mom|dad|kid|child|teen|student|driver|neighbor)\b", re.I)
FIGURES = {
    "m": "a man in his thirties with short dark hair, stubble and a gray hoodie",
    "f": "a woman in her thirties with shoulder-length brown hair and a green jacket",
    "": "a young adult with short brown hair and a yellow raincoat",
}


def cartoon_prompt(prompt: str, mood: str, figure: str) -> str:
    """Szenen-Bildidee als Cartoon: Foto-Stil der Stimmung raus, Zeichenstil und Hauptfigur rein."""
    from .moods import MOODS

    subject = prompt.replace(MOODS[mood]["image_style"], "").replace("vertical composition", "").replace("no text", "")
    subject = re.sub(r"(\s*,\s*)+", ", ", subject).strip(" ,")
    who = f", the main character is {figure}" if figure and PERSON.search(subject) else ""
    return (f"{subject}{who}, 2D cartoon illustration, clean bold outlines, flat shading, consistent character design, "
            f"{CARTOON_STYLE.get(mood, '')}, vertical composition, no text")


def pick_visuals(scenes: list[dict], mood: str, mode: str = "videos", seed: int = 1,
                 progress=lambda done, total: None, figure: str = "") -> tuple[list[Visual], list[str]]:
    """Ein Bild/Clip je Szene. Gibt (Visuals, Hinweise) zurück. figure: Hauptfigur im Cartoon-Modus."""
    notes: list[str] = []
    _ai_failures[0] = 0
    rnd = random.Random(seed)
    used: set = set()
    order = ORDER.get(mode, ORDER["videos"])
    has_stock = bool(config.PEXELS_API_KEY or config.PIXABAY_API_KEY)
    if "stock" in order and not has_stock and mode == "videos":
        notes.append("Videoclips kommen ohne Schlüssel von Wikimedia Commons (frei, mit Urheberangabe), wo passende "
                     "vorhanden sind – sonst animierte KI-Bilder. Mit einem kostenlosen Pexels- oder Pixabay-Schlüssel "
                     "(CUDI_PEXELS_API_KEY / CUDI_PIXABAY_API_KEY) gibt es mehr passende Clips.")
    if mode == "gameplay" and not own_clips(mood):
        notes.append("Keine eigenen Clips in video_assets/backgrounds gefunden – nutze Stockvideos/KI-Bilder.")

    def one(i: int, scene: dict) -> Visual:
        for source in order:
            try:
                if source == "stock":
                    found = (pexels(scene["query"], used) or pixabay(scene["query"], used)
                             or commons_video(scene["query"], used))
                elif source == "ai" and mode == "cartoon":   # gleicher Seed: gleiche Zeichenart in allen Szenen
                    found = ai_image(cartoon_prompt(scene["prompt"], mood, figure), seed * 1000)
                elif source == "ai":
                    found = ai_image(scene["prompt"], seed * 1000 + i)
                elif source == "photo":
                    found = commons_photo(scene["query"].replace(" dark", ""), used)
                else:
                    found = own_clip(mood, random.Random(seed * 1000 + i))
            except net.FetchError as exc:
                log.warning("%s für Szene %d nicht verfügbar: %s", source, i + 1, exc)
                found = None
            if found:
                return found
        return Visual("none", None, "", scene.get("query", ""))

    total = len(scenes)
    visuals: list[Visual | None] = [None] * total
    # Stock-Suchen nacheinander (keine doppelten Clips); KI-Bilder werden in ai_image ohnehin nacheinander geholt
    with ThreadPoolExecutor(max_workers=1) as pool:
        futures = {pool.submit(one, i, scene): i for i, scene in enumerate(scenes)}
        for done, future in enumerate(futures, start=1):
            visuals[futures[future]] = future.result()
            progress(done, total)
    if _ai_failures[0] >= AI_MAX_FAILURES:
        notes.append("Der KI-Bilddienst war überlastet – stattdessen freie Fotos von Wikimedia Commons "
                     "(mit Urheberangabe). Später erneut versuchen oder einen Pollinations-Zugang eintragen.")
    missing = sum(1 for v in visuals if v.kind == "none")
    if missing:
        notes.append(f"{missing} Szene(n) ohne Bild/Clip – dort läuft ein animierter Farbverlauf.")
    return visuals, notes


def cache_key(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]
