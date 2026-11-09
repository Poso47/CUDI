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

from .. import bildcheck, config, net

log = logging.getLogger(__name__)

CLIP_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv")


@dataclass
class Visual:
    kind: str                 # video | image | none
    path: str | None = None
    credit: str = ""          # für Beschreibung/Prüfbericht
    query: str = ""
    start: float = 0.0        # Startpunkt in eigenen Clips
    score: float | None = None   # Bildprüfung (CLIP): Wahrscheinlichkeit des Motivs, None = nicht geprüft

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- Stockvideos

def _pick(cands: list, motif: str) -> Visual | None:
    """Kandidaten [(Vorschaubilder-Funktion, Lade-Funktion)] -> Visual.

    Ohne Motiv oder ohne Bildprüfung: der erste (Tag-Abgleich hat vorgefiltert). Mit Motiv: bis zu 8 Kandidaten per
    CLIP prüfen (Zeitbudget), der mit dem besten Wert unter den passenden gewinnt – passt keiner: None."""
    if not cands:
        return None
    if not motif or not bildcheck.available():
        return cands[0][1]()
    started, best = time.time(), None
    for frames, build in cands[:bildcheck.MAX_CANDIDATES]:
        if best and time.time() - started > bildcheck.BUDGET_SECONDS:
            break
        try:
            ok, score = bildcheck.judge(motif, frames())
        except (net.FetchError, OSError) as exc:
            log.info("Vorschau nicht ladbar: %s", exc)
            continue
        if ok and (best is None or score > best[0]):
            best = (score, build)
            if score >= bildcheck.GOOD_ENOUGH:
                break
    if not best:
        return None
    found = best[1]()
    found.score = round(best[0], 2)
    return found


def _images(urls: list[str]) -> list:
    from PIL import Image

    def one(url):
        return Image.open(net.download(url, suffix=".jpg", timeout=30, retries=1, max_wait=10)).convert("RGB")

    with ThreadPoolExecutor(max_workers=3) as pool:          # die drei Vorschaubilder parallel laden
        return list(pool.map(one, urls))


def pexels(query: str, used: set, match=None, motif: str = "") -> Visual | None:
    """match: optionale Prüfung der Beschreibung (Pexels-Videos haben nur die Adresse: „…/video/a-shark-swimming-123/“).
    motif: zusätzlich visuelle Prüfung (bildcheck) über die Vorschaubilder des Clips."""
    if not config.PEXELS_API_KEY:
        return None
    for orientation in ("portrait", None):          # Hochformat bevorzugt, sonst mittig zugeschnitten
        params = {"query": query, "per_page": 15 if not motif else 20, "size": "medium"}
        if orientation:
            params["orientation"] = orientation
        data = net.get_json("https://api.pexels.com/videos/search", params=params,
                            headers={"Authorization": config.PEXELS_API_KEY}, cache_hours=24 * 7, retries=2)
        cands = []
        for video in data.get("videos", []):
            key = f"pexels:{video['id']}"
            if key in used or video.get("duration", 0) < 4:
                continue
            if match and not match(re.sub(r"[^a-z]+", " ", str(video.get("url", "")).lower().split("pexels.com")[-1])):
                continue
            files = [f for f in video.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 720]
            if not files:
                continue
            best = min(files, key=lambda f: abs((f.get("height") or 0) - 1920) + (f.get("width") or 0) // 4)

            def frames(video=video):
                pics = [p.get("picture") for p in video.get("video_pictures") or [] if p.get("picture")]
                return _images(bildcheck.spread(pics or [video.get("image")]))

            def build(video=video, best=best, key=key):
                path = net.download(best["link"], suffix=".mp4", timeout=120)
                used.add(key)
                return Visual("video", str(path), f"Pexels – {video.get('user', {}).get('name', 'unbekannt')}", query)

            cands.append((frames, build))
        found = _pick(cands, motif)
        if found:
            return found
    return None


def pexels_photo(query: str, used: set, match=None, motif: str = "") -> Visual | None:
    """Hochwertiges Foto im Hochformat von Pexels (kostenloser Schlüssel) – vor Wikimedia, das aus Rechenzentren
    oft gedrosselt wird."""
    if not config.PEXELS_API_KEY:
        return None
    data = net.get_json("https://api.pexels.com/v1/search", params={"query": query, "per_page": 15 if not motif else 20,
                                                                    "orientation": "portrait"},
                        headers={"Authorization": config.PEXELS_API_KEY}, cache_hours=24 * 7, retries=2)
    cands = []
    for photo in data.get("photos", []):
        key = f"pexels-foto:{photo['id']}"
        src = (photo.get("src") or {}).get("original")
        if key in used or not src or (photo.get("height") or 0) < 1200:
            continue
        slug = re.sub(r"[^a-z]+", " ", str(photo.get("url", "")).lower().split("pexels.com")[-1])
        if match and not match(f"{photo.get('alt', '')} {slug}"):
            continue

        def build(photo=photo, src=src, key=key):
            path = net.download(f"{src}?auto=compress&cs=tinysrgb&h=1920", suffix=".jpg", timeout=60)
            used.add(key)
            return Visual("image", str(path), f"Foto: {photo.get('photographer', 'unbekannt')} – Pexels", query)

        cands.append((lambda photo=photo: _images([(photo.get("src") or {}).get("medium") or photo["src"]["original"]]),
                      build))
    return _pick(cands, motif)


def pixabay(query: str, used: set, match=None, motif: str = "") -> Visual | None:
    if not config.PIXABAY_API_KEY:
        return None
    data = net.get_json("https://pixabay.com/api/videos/", params={"key": config.PIXABAY_API_KEY, "q": query,
                                                                  "per_page": 20, "safesearch": "true"},
                        cache_hours=24 * 7, retries=2)
    cands = []
    for hit in data.get("hits", []):
        key = f"pixabay:{hit['id']}"
        if key in used or hit.get("duration", 0) < 4:
            continue
        if match and not match(str(hit.get("tags", ""))):
            continue
        for size in ("large", "medium"):
            file = hit.get("videos", {}).get(size) or {}
            if file.get("url") and (file.get("height") or 0) >= 720:
                def frames(hit=hit):             # kleinste Fassung laden und daraus 3 Bilder ziehen
                    tiny = next((hit["videos"][s]["url"] for s in ("tiny", "small") if (hit["videos"].get(s) or {}).get("url")),
                                None)
                    if not tiny:
                        raise net.FetchError("keine kleine Fassung")
                    return bildcheck.video_frames(net.download(tiny, suffix=".mp4", timeout=60, retries=1, max_wait=10),
                                                  hit.get("duration", 0))

                def build(hit=hit, file=file, key=key):
                    path = net.download(file["url"], suffix=".mp4", timeout=120)
                    used.add(key)
                    return Visual("video", str(path), f"Pixabay – {hit.get('user', 'unbekannt')}", query)

                cands.append((frames, build))
                break
    return _pick(cands, motif)


def pixabay_photo(query: str, used: set, match=None, motif: str = "") -> Visual | None:
    """Foto von Pixabay (Schlagworte „tags“ für den Motiv-Abgleich), Hochformat bevorzugt."""
    if not config.PIXABAY_API_KEY:
        return None
    data = net.get_json("https://pixabay.com/api/", params={"key": config.PIXABAY_API_KEY, "q": query[:100],
                                                            "image_type": "photo", "per_page": 20,
                                                            "safesearch": "true"},
                        cache_hours=24, retries=2)
    hits = [h for h in data.get("hits", []) if f"pixabay-foto:{h['id']}" not in used and h.get("largeImageURL")
            and (not match or match(str(h.get("tags", ""))))]
    hits.sort(key=lambda h: (h.get("imageHeight") or 0) < (h.get("imageWidth") or 0))     # Hochformat zuerst
    cands = []
    for hit in hits:
        def build(hit=hit):
            path = net.download(hit["largeImageURL"], suffix=".jpg", timeout=60)
            used.add(f"pixabay-foto:{hit['id']}")
            return Visual("image", str(path), f"Foto: {hit.get('user', 'unbekannt')} – Pixabay", query)

        cands.append((lambda hit=hit: _images([hit.get("webformatURL") or hit["largeImageURL"]]), build))
    return _pick(cands, motif)


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


def commons_photo(query: str, used: set, match=None, motif: str = "") -> Visual | None:
    """Frei lizenziertes Foto von Wikimedia Commons (ohne Schlüssel) – Hochformat bevorzugt.

    Nur Bilder mit Urheber (oder gemeinfrei): die Lizenz verlangt sonst eine Namensnennung.
    match: optionale Prüfung des Dateititels (Bildpassung für Fakten)."""
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
                or (match and not match(re.sub(r"[^A-Za-z]+", " ", page["title"])))
                or (info.get("width") or 0) < 800 or (info.get("height") or 0) < 800 or not info.get("thumburl")):
            continue
        artist = credit_author(meta, license_name)
        if not artist:
            continue
        portrait = info["height"] >= info["width"]
        candidates.append((not portrait, page, info, license_name, artist))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    cands = []
    for _, page, info, license_name, artist in candidates:
        def build(page=page, info=info, license_name=license_name, artist=artist):
            path = net.download(info["thumburl"], suffix=".jpg", retries=2, max_wait=20)
            used.add(page["title"])
            return Visual("image", str(path), f"Foto: {artist[:60]} – {license_name} – Wikimedia Commons", query)

        cands.append((lambda info=info: _images([info["thumburl"]]), build))
    return _pick(cands, motif)


# --------------------------------------------------------------------------- freie Clips (Wikimedia Commons)

CLIP_SKIP = ("interview", "lecture", "speech", "conference", "presentation", "talk", "song", "music", "trailer",
             "news", "documentary", "podcast", "webinar", "tutorial", "wikipedia", "wikimania", "session", "slides")
QUERY_STOP = {"dark", "close", "view", "shot", "scene", "with", "from", "into", "over", "under", "very", "light",
              "line", "part", "side", "back", "front", "time", "night", "life"}


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
            # Bei mehreren Suchwörtern müssen mindestens zwei im Titel stehen – sonst kommt z. B. für
            # „dark tree line“ ein Rafting-Clip, nur weil „line“ im Titel steht.
            if title in used or sum(w in low for w in words) < min(2, len(words)) or any(x in low for x in CLIP_SKIP):
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
    "cartoon": ("ai", "repeat", "photo", "own", "stock"),   # lieber das vorige Cartoon-Bild als ein Foto
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
    subject = re.sub(r"(\s*,\s*)+", ", ", subject).strip(" ,")[:150]
    who = f", the main character is {figure[:110]}" if figure and PERSON.search(subject) else ""
    # Stil zuerst: der Bilddienst bekommt höchstens 400 Zeichen – die Cartoon-Vorgaben dürfen nicht wegfallen
    return (f"flat 2D cartoon, cel shading, thick clean outlines, simple shapes, comic book style, consistent "
            f"character design, vertical, no text: {subject}{who}, {CARTOON_STYLE.get(mood, '')}")


def _prewarm(scenes: list[dict], workers: int = 4) -> None:
    """Tempo: Suchanfragen und Clip-Downloads der Stock-Quellen für alle Szenen GLEICHZEITIG in den Datei-Cache holen.
    Die eigentliche Auswahl läuft danach unverändert nacheinander (keine doppelten Clips) und findet alles im Cache.
    Ergebnisse werden hier verworfen; jeder Fehler ist egal (dann holt die Auswahl es wie bisher selbst)."""
    def warm(scene: dict) -> None:
        try:
            pexels(scene["query"], set()) or pixabay(scene["query"], set())
        except Exception as exc:                          # noqa: BLE001 - nur Vorwärmen
            log.info("Vorwärmen für %r übersprungen: %s", scene.get("query"), exc)

    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(scenes)))) as pool:
        list(pool.map(warm, scenes))


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

    last_ai: list[Visual | None] = [None]

    def one(i: int, scene: dict) -> Visual:
        for source in order:
            if source == "repeat":
                if last_ai[0] is not None:
                    return last_ai[0]
                continue
            try:
                if source == "stock":
                    found = (pexels(scene["query"], used) or pixabay(scene["query"], used)
                             or commons_video(scene["query"], used))
                elif source == "ai" and mode == "cartoon":   # gleicher Seed: gleiche Zeichenart in allen Szenen
                    found = ai_image(cartoon_prompt(scene["prompt"], mood, figure), seed * 1000)
                elif source == "ai":
                    found = ai_image(scene["prompt"], seed * 1000 + i)
                elif source == "photo":
                    found = (pexels_photo(scene["query"], used)
                             or commons_photo(scene["query"].replace(" dark", ""), used))
                else:
                    found = own_clip(mood, random.Random(seed * 1000 + i))
            except net.FetchError as exc:
                log.warning("%s für Szene %d nicht verfügbar: %s", source, i + 1, exc)
                found = None
            if found:
                if found.kind == "image" and source == "ai":
                    last_ai[0] = found
                return found
        return Visual("none", None, "", scene.get("query", ""))

    total = len(scenes)
    visuals: list[Visual | None] = [None] * total
    if "stock" in order and order[0] == "stock" and has_stock:
        _prewarm(scenes)
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
