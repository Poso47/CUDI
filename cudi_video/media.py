"""Weitere kostenlose Bildquellen für Ranking-Plätze – wenn das Wikidata-Foto fehlt, gesperrt, ohne freie
Lizenz oder zu klein ist.

* **Openverse** (WordPress-Stiftung, ohne Schlüssel): durchsucht Flickr, Wikimedia und weitere offene
  Sammlungen; nur Lizenzen, die kommerzielle Nutzung UND Bearbeitung (Zuschnitt, Zoom) erlauben.
* **NASA Image and Video Library** (gemeinfrei, ohne Schlüssel): Astronauten- und Satellitenfotos – stark bei
  Seen, Inseln, Wüsten, Bergen, Flüssen.

Qualität vor Menge: Ein Bild zählt nur, wenn die unterscheidenden Wörter des Namens im Titel oder in den
Schlagworten stehen (keine fremde Brücke unter falschem Namen) und es groß genug für die Karte ist.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from . import net
from .models import RankItem

log = logging.getLogger(__name__)

MIN_WIDTH = 1000             # kleiner sieht auf der 1080er-Karte unscharf aus
GOOD_WIDTH = 1200            # ab hier ist ein Foto „gut genug“, weitere Quellen werden nicht gefragt
PLAIN_AGENT = {"User-Agent": "CUDI-Video/1.0"}      # Flickr lehnt Kennungen mit Klammern/Links ab (HTTP 403)

GENERIC = set("""the of and de la le el di da von der die das und im am in at on
    bridge brücke bruecke grand great big large high long tower turm building gebäude mount mountain berg peak
    lake see river fluss island insel falls fall waterfall wasserfall viaduct viadukt causeway tunnel dam
    city stadt national park sea meer ocean desert wüste glacier gletscher volcano vulkan station center centre
    international world trade financial hotel plaza square tower towers new north south east west""".split())


NOT_PHOTO = re.compile(r"\b(map|karte|location|locator|logo|diagram|plan|schema|flag|coat of arms|wappen)\b|\.svg\b",
                       re.I)


@dataclass
class Candidate:
    url: str
    width: int
    height: int
    credit: str               # „Urheber – Lizenz – Quelle“ (gleiches Format wie Commons-Bilder)
    origin: str

    @property
    def score(self) -> float:
        aspect = self.width / max(1, self.height)
        # Ab ~Full-HD-Breite zählt jedes Foto gleich (die Karte ist 960 px breit) – dann entscheidet die Reihenfolge
        # der Quellen: Pexels/Pixabay laden zuverlässig, Wikimedia-Dateien werden aus Rechenzentren oft gedrosselt.
        quality = min(self.width, 1800) * (1.0 if 1.1 <= aspect <= 2.2 else 0.75)    # Karte ist quer (≈ 1,7 : 1)
        return quality * (0.9 if "wikimedia.org" in self.url else 1.0)


def key_tokens(name: str) -> list[str]:
    """Unterscheidende Wörter eines Namens: „Danyang–Kunshan Grand Bridge“ -> danyang, kunshan."""
    words = re.findall(r"[^\W_]+", name.lower())
    out = [w for w in words if w not in GENERIC and (len(w) >= 3 or any(c.isdigit() for c in w))]
    return out or [w for w in words if len(w) >= 3]


def names_match(item: RankItem, text: str) -> bool:
    """Stehen alle unterscheidenden Wörter des Namens im Text? Gezählt wird der spezifischste Name (en/de mit den
    meisten unterscheidenden Wörtern): „The Clock Towers“ ließe nur „clock“ übrig und passte auf jeden Uhrturm –
    daher muss hier „Abraj Al Bait“ (abraj, bait) passen."""
    hay = set(re.findall(r"[^\W_]+", text.lower()))
    names = [n for n in {item.labels.get("en", ""), item.labels.get("de", "")} if n]
    sets = [key_tokens(n) for n in names]
    best = max((len(t) for t in sets), default=0)
    return any(t and len(t) == best and all(w in hay for w in t) for t in sets)


def _cc_name(code: str, version: str) -> str:
    code = (code or "").lower()
    if code in ("cc0", "pdm"):
        return {"cc0": "CC0", "pdm": "Public Domain"}[code]
    return f"CC {code.upper()} {version}".strip()


def openverse(item: RankItem) -> list[Candidate]:
    name = item.labels.get("en") or item.labels.get("de")
    if not name:
        return []
    data = net.get_json("https://api.openverse.org/v1/images/",
                        params={"q": name, "license_type": "commercial,modification", "page_size": 20,
                                "mature": "false"},
                        cache_hours=24 * 30, retries=1, max_wait=10)
    out = []
    for r in data.get("results", []):
        lic = (r.get("license") or "").lower()
        if "nd" in lic or "nc" in lic:                       # Sicherheitsnetz zur Filterung der API
            continue
        text = " ".join([r.get("title") or ""] + [t.get("name", "") for t in r.get("tags") or []])
        if not names_match(item, text) or (r.get("width") or 0) < MIN_WIDTH or not r.get("url") \
                or NOT_PHOTO.search(f"{r.get('title') or ''} {r['url']}"):
            continue
        creator = (r.get("creator") or "").strip()
        if not creator and lic not in ("cc0", "pdm"):
            continue                                          # Namensnennung nötig, Urheber fehlt
        source = (r.get("source") or r.get("provider") or "Openverse").replace("_", " ").title()
        out.append(Candidate(r["url"], r.get("width") or 0, r.get("height") or 0,
                             f"{creator or 'unbekannt'} – {_cc_name(lic, r.get('license_version') or '')} – "
                             f"{source} via Openverse: {r.get('foreign_landing_url') or r['url']}", "Openverse"))
    return out


def nasa(item: RankItem) -> list[Candidate]:
    name = item.labels.get("en")
    if not name:
        return []
    data = net.get_json("https://images-api.nasa.gov/search", params={"q": name, "media_type": "image"},
                        cache_hours=24 * 30, retries=1, max_wait=10)
    out = []
    for hit in data.get("collection", {}).get("items", [])[:15]:
        meta = (hit.get("data") or [{}])[0]
        if not names_match(item, f"{meta.get('title', '')} {' '.join(meta.get('keywords') or [])}"):
            continue
        nasa_id = meta.get("nasa_id")
        if not nasa_id:
            continue
        url = f"https://images-assets.nasa.gov/image/{nasa_id}/{nasa_id}~large.jpg"
        out.append(Candidate(url, 1600, 1100, f"NASA – Public Domain – NASA Image Library: {nasa_id}", "NASA"))
        if len(out) >= 3:
            break
    return out


def pexels_photos(item: RankItem) -> list[Candidate]:
    from . import config

    name = item.labels.get("en") or item.labels.get("de")
    if not config.PEXELS_API_KEY or not name:
        return []
    data = net.get_json("https://api.pexels.com/v1/search", params={"query": name, "per_page": 15},
                        headers={"Authorization": config.PEXELS_API_KEY}, cache_hours=24 * 7, retries=1, max_wait=10)
    out = []
    for p in data.get("photos", []):
        # Pexels: Beschreibung in „alt“ und in der Adresse („…/photo/burj-khalifa-at-dusk-123/“)
        if not names_match(item, f"{p.get('alt', '')} {_words_of(p.get('url', ''))}") or (p.get("width") or 0) < MIN_WIDTH:
            continue
        src = (p.get("src") or {}).get("original")
        if not src:
            continue
        w, h = p["width"], p.get("height") or p["width"]
        scale = min(1.0, 1920 / max(w, 1))
        out.append(Candidate(f"{src}?auto=compress&cs=tinysrgb&w=1920", int(w * scale), int(h * scale),
                             f"{p.get('photographer', 'Pexels')} – Pexels-Lizenz – Pexels: {p.get('url', '')}", "Pexels"))
    return out


def pixabay_photos(item: RankItem) -> list[Candidate]:
    from . import config

    name = item.labels.get("en") or item.labels.get("de")
    if not config.PIXABAY_API_KEY or not name:
        return []
    data = net.get_json("https://pixabay.com/api/", params={"key": config.PIXABAY_API_KEY, "q": name[:100],
                                                            "image_type": "photo", "per_page": 20, "safesearch": "true"},
                        cache_hours=24, retries=1, max_wait=10)      # Bildadressen von Pixabay laufen nach 24 h ab
    out = []
    for h in data.get("hits", []):
        if not names_match(item, h.get("tags", "")) or not h.get("largeImageURL"):
            continue
        w, hh = h.get("imageWidth") or 1280, h.get("imageHeight") or 853
        out.append(Candidate(h["largeImageURL"], 1280, int(1280 * hh / max(w, 1)),
                             f"{h.get('user', 'Pixabay')} – Pixabay-Lizenz – Pixabay: {h.get('pageURL', '')}", "Pixabay"))
    return out


def alternatives(item: RankItem) -> list[Candidate]:
    """Weitere Fotos des Platzes, bestes zuerst. Fällt eine Quelle aus, zählen die anderen."""
    found: list[Candidate] = []
    for source in (pexels_photos, pixabay_photos, openverse, nasa):
        try:
            found += source(item)
        except net.FetchError as exc:
            log.info("%s für %s nicht erreichbar: %s", source.__name__, item.qid, exc)
    return sorted(found, key=lambda c: c.score, reverse=True)


def download(candidate: Candidate):
    headers = None if "wikimedia.org" in candidate.url else PLAIN_AGENT
    return net.download(candidate.url, suffix=".img", retries=1, max_wait=10, headers=headers)


# --------------------------------------------------------------------------- Videoclips je Platz

MAX_CLIPS = 3                # so viele kurze Ausschnitte werden je Platz zusammengeschnitten
MIN_CLIP_SECONDS = 3.0


@dataclass
class Clip:
    url: str
    width: int
    duration: float
    credit: str               # „Urheber – Lizenz – Quelle“
    origin: str
    suffix: str = ".mp4"
    key: str = ""             # gleiche Aufnahme nicht doppelt


def _words_of(url: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", url.lower()))


def pexels_clips(item: RankItem) -> list[Clip]:
    from . import config

    name = item.labels.get("en") or item.labels.get("de")
    if not config.PEXELS_API_KEY or not name:
        return []
    data = net.get_json("https://api.pexels.com/videos/search", params={"query": name, "per_page": 15},
                        headers={"Authorization": config.PEXELS_API_KEY}, cache_hours=24 * 7, retries=1, max_wait=10)
    out = []
    for v in data.get("videos", []):
        # Pexels hat keine Titel – die Beschreibung steckt in der Adresse („…/video/burj-khalifa-at-night-123/“)
        if not names_match(item, _words_of(v.get("url", ""))) or (v.get("duration") or 0) < MIN_CLIP_SECONDS:
            continue
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                 and 1280 <= (f.get("width") or 0) <= 1920]
        if not files:
            continue
        f = max(files, key=lambda f: f["width"])
        out.append(Clip(f["link"], f["width"], v["duration"],
                        f"{(v.get('user') or {}).get('name', 'Pexels')} – Pexels-Lizenz – Pexels", "Pexels",
                        key=f"pexels:{v['id']}"))
    return out


def pixabay_clips(item: RankItem) -> list[Clip]:
    from . import config

    name = item.labels.get("en") or item.labels.get("de")
    if not config.PIXABAY_API_KEY or not name:
        return []
    data = net.get_json("https://pixabay.com/api/videos/", params={"key": config.PIXABAY_API_KEY, "q": name[:100],
                                                                   "per_page": 20, "safesearch": "true"},
                        cache_hours=24 * 7, retries=1, max_wait=10)
    out = []
    for h in data.get("hits", []):
        if not names_match(item, h.get("tags", "")) or (h.get("duration") or 0) < MIN_CLIP_SECONDS:
            continue
        sizes = [v for v in (h.get("videos") or {}).values() if v.get("url") and 1280 <= (v.get("width") or 0) <= 1920]
        if not sizes:
            continue
        v = max(sizes, key=lambda v: v["width"])
        out.append(Clip(v["url"], v["width"], h["duration"], f"{h.get('user', 'Pixabay')} – Pixabay-Lizenz – Pixabay",
                        "Pixabay", key=f"pixabay:{h['id']}"))
    return out


def nasa_clips(item: RankItem) -> list[Clip]:
    name = item.labels.get("en")
    if not name:
        return []
    data = net.get_json("https://images-api.nasa.gov/search", params={"q": name, "media_type": "video"},
                        cache_hours=24 * 30, retries=1, max_wait=10)
    out = []
    for hit in data.get("collection", {}).get("items", [])[:10]:
        meta = (hit.get("data") or [{}])[0]
        if not names_match(item, f"{meta.get('title', '')} {' '.join(meta.get('keywords') or [])}"):
            continue
        try:
            files = net.get_json(hit["href"], cache_hours=24 * 30, retries=1, max_wait=10)
        except (net.FetchError, KeyError):
            continue
        mp4 = [u for u in files if isinstance(u, str) and u.endswith(".mp4")]
        pick = next((u for tag in ("~medium.mp4", "~large.mp4", "~orig.mp4") for u in mp4 if u.endswith(tag)), None)
        if pick:
            out.append(Clip(pick.replace("http://", "https://"), 1280, 10.0,
                            f"NASA – Public Domain – NASA Image Library: {meta.get('nasa_id', '')}", "NASA",
                            key=f"nasa:{meta.get('nasa_id', pick)}"))
    return out


def commons_clips(item: RankItem) -> list[Clip]:
    from .enrich import NON_FREE, credit_author
    from .story.visuals import CLIP_SKIP, _best_derivative

    name = item.labels.get("en") or item.labels.get("de")
    if not name:
        return []
    data = net.get_json("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "formatversion": 2, "generator": "search",
        "gsrsearch": f"{name} filetype:video", "gsrnamespace": 6, "gsrlimit": 15, "prop": "videoinfo",
        "viprop": "url|size|mime|derivatives|extmetadata",
        "viextmetadatafilter": "LicenseShortName|Artist|Attribution|AttributionRequired",
    }, cache_hours=24 * 7, retries=1, max_wait=10)
    out = []
    for page in sorted(data.get("query", {}).get("pages", []), key=lambda pg: pg.get("index", 99)):
        title = page.get("title", "")
        if not names_match(item, title) or any(x in title.lower() for x in CLIP_SKIP):
            continue
        info = (page.get("videoinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        artist = credit_author(meta, lic) if lic and not NON_FREE.search(lic) else None
        src = _best_derivative(info)
        if artist and src and MIN_CLIP_SECONDS <= (info.get("duration") or 0) <= 600:
            out.append(Clip(src, 1280, info["duration"], f"{artist[:60]} – {lic} – Wikimedia Commons", "Commons",
                            suffix=".webm", key=title))
    return out


def find_clips(item: RankItem, limit: int = MAX_CLIPS) -> list[dict]:
    """Bis zu `limit` passende Clips laden – Stockvideos in HD zuerst, dann NASA, dann Commons.
    Ergebnis: [{"path": …, "credit": …, "duration": …}] (leer = Foto mit Zoom wie bisher)."""
    found: list[Clip] = []
    for source in (pexels_clips, pixabay_clips, nasa_clips, commons_clips):
        if len(found) >= limit * 2:
            break
        try:
            found += source(item)
        except net.FetchError as exc:
            log.info("%s für %s nicht erreichbar: %s", source.__name__, item.qid, exc)
    out, seen = [], set()
    for clip in found:
        if clip.key in seen:
            continue
        try:
            headers = None if "wikimedia.org" in clip.url else PLAIN_AGENT
            path = net.download(clip.url, suffix=clip.suffix, retries=1, max_wait=10, timeout=120, headers=headers)
        except net.FetchError as exc:
            log.info("Clip %s nicht geladen: %s", clip.origin, exc)
            continue
        if path.stat().st_size > 60_000_000:          # sehr große Dateien bremsen den Schnitt
            continue
        seen.add(clip.key)
        out.append({"path": str(path), "credit": clip.credit, "duration": clip.duration, "kind": "video"})
        if len(out) >= limit:
            break
    return out + _stills(item, limit - len(out), bool(out))


def _stills(item: RankItem, room: int, has_clips: bool) -> list[dict]:
    """Zu wenige Clips: weitere Fotos des Platzes als bewegte Standbilder (langsamer Schwenk) dazwischen.
    Ohne Clip nur, wenn mindestens zwei verschiedene Fotos zusammenkommen – ein einzelnes zeigt die Karte
    ohnehin mit Zoom."""
    if room <= 0:
        return []
    own = [{"path": item.image_path, "credit": item.image_credit or "", "duration": 0, "kind": "image"}] \
        if item.image_path and item.image_kind == "photo" else []
    extra = []
    try:
        candidates = alternatives(item)
    except Exception as exc:                                     # Fotos sind Zugabe, nie ein Abbruchgrund
        log.info("Weitere Fotos für %s nicht verfügbar: %s", item.qid, exc)
        candidates = []
    known = {item.image_credit}
    for cand in candidates:
        if len(own) + len(extra) >= room or cand.credit in known:
            continue
        try:
            path = download(cand)
        except net.FetchError:
            continue
        known.add(cand.credit)
        extra.append({"path": str(path), "credit": cand.credit, "duration": 0, "kind": "image"})
    stills = (own + extra)[:room]
    if not has_clips and len(stills) < 2:
        return []
    return stills
