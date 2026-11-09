"""Bildseite der Reportage: je Satz ein passendes echtes Bild/Clip, Karte des Ortes, Datum, Quellen-Badge.

Nichts wird erfunden: Orte und Daten kommen aus dem geprüften Satz (Ortskoordinaten aus Wikipedia, nur Erde), Bilder
nur aus freien Quellen (media.py: Pexels, Pixabay, NASA, Openverse, Commons – nur kommerziell nutzbare Lizenzen) und
nur, wenn Bildgüte (Schärfe, Auflösung, kein Doppelbild) und Bildprüfung (CLIP) bestehen. Gibt es nichts Passendes,
zeigt die Szene eine neutrale Grafik (Karte, großes Datum, Zitat) – kein Raten, kein Stimmungsbild fremder Orte.
"""

from __future__ import annotations

import logging
import math
import re
import time
from pathlib import Path

from .. import bildguete, config, media, net
from ..models import RankItem

log = logging.getLogger(__name__)

TIME_BUDGET = 240.0                 # Sekunden für alle Bildsuchen eines Videos (danach: neutrale Grafik)
MAX_QUERIES = 3                     # Suchbegriffe je Satz
MAP_ZOOM, MAP_SIZE = 9, 720
UA = {"User-Agent": "CUDI-Video/1.0 (https://github.com/Poso47/CUDI)"}

MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
           "Dezember"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
           "December"],
}
STOP = set("""der die das den dem des ein eine einer einem einen und oder aber doch auch nach vor bei mit seit von zu
    zum zur im am um an auf aus für über unter durch gegen ohne wie als wenn dass ist sind war waren wird wurde wurden
    hat haben hatte hatten es sie er wir ihr man dort hier dann nun so nur noch schon erst später früher
    the a an and or but of in on at by for with from to as is are was were be been has have had it its they their he she
    this that these those which who whom after before during since into over under about""".split())


# --------------------------------------------------------------------------- Datum

def date_in(text: str, lang: str) -> tuple[str, int | None]:
    """Erste Zeit-Angabe im Satz: („20. Juli 1969“ | „Juli 1969“ | „1969“, Jahr) oder ("", None)."""
    months = "|".join(MONTHS[lang] if lang in MONTHS else MONTHS["de"])
    patterns = [rf"\b\d{{1,2}}\.\s*(?:{months})\s+(\d{{4}})\b", rf"\b(?:{months})\s+(\d{{1,2}},\s*)?(\d{{4}})\b",
                rf"\b\d{{1,2}}\s+(?:{months})\s+(\d{{4}})\b", r"\b(1[0-9]{3}|20[0-9]{2})\b"]
    for pat in patterns:
        if m := re.search(pat, text):
            year = re.search(r"\d{4}", m.group(0))
            return m.group(0).strip(), int(year.group(0)) if year else None
    return "", None


# --------------------------------------------------------------------------- Namen, Orte (Wikipedia)

PHRASE = re.compile(r"[A-ZÄÖÜ][\w\-äöüßÄÖÜ]*(?:\s+(?:[A-ZÄÖÜ][\w\-äöüßÄÖÜ]*|\d+))*")


def phrases(text: str) -> list[str]:
    """Großgeschriebene Wortfolgen (Namen, Orte, Ereignisse) und ihre Teilfolgen, längste zuerst. Satzanfang und
    Funktionswörter fallen heraus; ob etwas existiert, entscheidet danach Wikipedia."""
    out: list[str] = []
    for m in PHRASE.finditer(text):
        words = m.group(0).split()
        for n in range(len(words), 0, -1):
            for i in range(0, len(words) - n + 1):
                chunk = words[i:i + n]
                if chunk[0].lower() in STOP or chunk[-1].lower() in STOP:
                    continue
                if n == 1 and (len(chunk[0]) < 4 or m.start() == 0 and i == 0 and len(words) == 1):
                    continue
                if (c := " ".join(chunk)) not in out:
                    out.append(c)
    return out


def wiki_infos(titles: list[str], lang: str) -> dict[str, dict]:
    """Titel -> {"title", "en", "coords": (lat, lon) | None, "desc"} für Titel, die in der Wikipedia existieren.
    Koordinaten nur von der Erde (Mond-/Marsorte bekommen keine Erdkarte)."""
    out: dict[str, dict] = {}
    titles = list(dict.fromkeys(titles))
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        try:
            data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php", {
                "action": "query", "format": "json", "formatversion": 2, "titles": "|".join(chunk), "redirects": 1,
                "prop": "coordinates|langlinks|description", "lllang": "en", "lllimit": 50, "colimit": 50,
                "coprimary": "primary"}, cache_hours=24 * 7, retries=1, max_wait=10)
        except net.FetchError as exc:
            log.info("Wikipedia (%s) nicht erreichbar: %s", lang, exc)
            continue
        q = data.get("query") or {}
        alias = {}
        for key in ("normalized", "redirects"):
            for r in q.get(key) or []:
                alias[r["from"]] = r["to"]
        found = {}
        for page in q.get("pages") or []:
            if page.get("missing") or page.get("invalid"):
                continue
            desc = page.get("description") or ""
            if re.search(r"disambig|begriffsklärung|list of|liste", desc + " " + page.get("title", ""), re.I):
                continue
            coords = next(((c["lat"], c["lon"]) for c in page.get("coordinates") or []
                           if c.get("globe", "earth") == "earth"), None)
            en = next((l["title"] for l in page.get("langlinks") or [] if l.get("lang") == "en"), None) \
                or (page["title"] if lang == "en" else None)
            found[page["title"]] = {"title": page["title"], "en": en, "coords": coords, "desc": desc}
        for want in chunk:
            seen = want
            for _ in range(3):
                seen = alias.get(seen, seen)
            if seen in found:
                out[want] = found[seen]
    return out


# --------------------------------------------------------------------------- Karte (OpenStreetMap)

def tile_xy(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def render_map(lat: float, lon: float, out: Path, zoom: int = MAP_ZOOM) -> Path | None:
    """Statische Karte aus 3×3 OpenStreetMap-Kacheln um den Ort, mit Markierung und Namensnennung
    („© OpenStreetMap-Mitwirkende“, ODbL). Ohne Kacheln: None (dann zeigt die Szene eine andere neutrale Grafik)."""
    from PIL import Image, ImageDraw, ImageFont

    x, y = tile_xy(lat, lon, zoom)
    cx, cy = int(x), int(y)
    mosaic = Image.new("RGB", (768, 768), (30, 30, 30))
    loaded = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            try:
                path = net.download(f"https://tile.openstreetmap.org/{zoom}/{(cx + dx) % 2 ** zoom}/{cy + dy}.png",
                                    suffix=".png", retries=1, max_wait=8, headers=UA)
                mosaic.paste(Image.open(path).convert("RGB"), ((dx + 1) * 256, (dy + 1) * 256))
                loaded += 1
            except Exception:                                       # noqa: BLE001
                continue
    if loaded < 6:
        return None
    px, py = (x - cx + 1) * 256, (y - cy + 1) * 256
    half = MAP_SIZE // 2 if MAP_SIZE <= 768 else 384
    left = int(min(max(px - half, 0), 768 - MAP_SIZE))
    top = int(min(max(py - half, 0), 768 - MAP_SIZE))
    img = mosaic.crop((left, top, left + MAP_SIZE, top + MAP_SIZE))
    d = ImageDraw.Draw(img)
    mx, my = px - left, py - top
    d.ellipse((mx - 16, my - 16, mx + 16, my + 16), fill=(196, 48, 43), outline=(255, 255, 255), width=4)
    note = "© OpenStreetMap-Mitwirkende"
    try:
        fnt = ImageFont.load_default(20)
    except TypeError:                                               # ältere Pillow
        fnt = ImageFont.load_default()
    w = d.textlength(note, font=fnt)
    d.rectangle((MAP_SIZE - w - 16, MAP_SIZE - 30, MAP_SIZE, MAP_SIZE), fill=(255, 255, 255))
    d.text((MAP_SIZE - w - 8, MAP_SIZE - 26), note, font=fnt, fill=(40, 40, 40))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=90)
    return out


# --------------------------------------------------------------------------- Bild/Clip suchen

def pseudo_item(query: str, desc: str = "") -> RankItem:
    return RankItem(qid="", value=0.0, unit="", labels={"en": query}, descriptions={"en": desc})


def find_media(query: str, desc: str, seen: bildguete.Seen, folder: Path) -> dict | None:
    """Erster Treffer, der zum Suchbegriff passt: Clip (Pexels/Pixabay/NASA) vor Foto; sonst None."""
    item = pseudo_item(query, desc)
    try:
        clips = media.find_clips(item, limit=1, stills=False) if config.RANKING_CLIPS else []
    except Exception as exc:                                        # noqa: BLE001 – Clips sind Zugabe
        log.info("Clipsuche %s: %s", query, exc)
        clips = []
    for clip in clips:
        return {"bild": clip["path"], "bild_art": "video", "credit": clip["credit"], "dauer": clip["duration"]}
    for cand in media.alternatives(item):
        try:
            path = media.download(cand)
        except net.FetchError:
            continue
        good, why = media.verify_photo(item, path, seen)
        if good:
            return {"bild": str(path), "bild_art": "image", "credit": cand.credit}
        log.info("Reportage-Bild %s verworfen: %s", cand.origin, why)
    return None


def short_credit(credit: str) -> str:
    """„Urheber – Lizenz – Quelle“ -> „Urheber (Lizenz)“ fürs Bild; Gemeinfreies braucht keinen Vermerk."""
    artist, lic = (credit.split(" – ") + ["", ""])[:2]
    if re.search(r"public domain|\bcc0\b", lic, re.I) or not artist:
        return ""
    return artist if re.search(r"pexels|pixabay", lic, re.I) or not lic else f"{artist} ({lic})"


def badge(belege: list[dict]) -> str:
    return " · ".join(dict.fromkeys(b["name"] for b in belege))


def anreichern(saetze: list[dict], thema: str, lang: str, folder: Path, hints: list[dict] | None = None,
               seen: bildguete.Seen | None = None) -> tuple[list[dict], list[str]]:
    """Je Satz die Bild-Angaben für die Szene (siehe render/reportage.py). Rückgabe (Liste, Hinweise für den Prüfbericht).

    hints: optional je Satz {"ort", "bild"} von der Schreibaufgabe – sie gelten nur, wenn der Ort wörtlich im Satz oder
    in einem Beleg steht."""
    folder.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    started = time.time()
    seen = seen or bildguete.Seen()
    texts = [s["text"] + " " + " ".join(b["zitat"] for b in s["belege"]) for s in saetze]
    cands = [phrases(s["text"]) for s in saetze]
    infos = wiki_infos(list(dict.fromkeys(c for cs in cands for c in cs[:14] + [thema])), lang)
    theme_info = infos.get(thema)
    dates = [date_in(s["text"], lang) for s in saetze]
    years = sorted({y for _, y in dates if y})
    out = []
    for i, sat in enumerate(saetze):
        mine = [infos[c] for c in cands[i] if c in infos]
        place = next((x for x in mine if x["coords"]), None)
        hint = (hints[i] if hints and i < len(hints) else None) or {}
        if hint.get("ort") and hint["ort"].casefold() in texts[i].casefold() and not place:
            place = next(iter(wiki_infos([hint["ort"]], lang).values()), None)
            place = place if place and place["coords"] else None
        queries, descs = [], {}
        extra = [hint["bild"]] if hint.get("bild") and re.fullmatch(r"[\w .,'\-]{3,60}", str(hint["bild"])) else []
        for info in ([place] if place else []) + mine + ([theme_info] if theme_info else []):
            q = info and (info.get("en") or "")
            if q and q not in queries and q not in extra:
                queries.append(q)
                descs[q] = info.get("desc", "")
        queries = (extra + queries)[:MAX_QUERIES]
        v = {"typ": "reportage", "quelle": badge(sat["belege"]), "zitat": sat["belege"][0]["zitat"] if sat["belege"] else "",
             "datum": dates[i][0], "jahr": dates[i][1], "jahre": years, "ort": (place or {}).get("title", ""),
             "bild": None, "bild_art": "image", "credit": ""}
        if place and place["coords"]:
            try:
                tile = render_map(*place["coords"], folder / f"karte_{i:02d}.jpg")
                v["karte"] = str(tile) if tile else None
            except Exception as exc:                                # noqa: BLE001
                log.info("Karte für %s nicht gerendert: %s", place["title"], exc)
        for q in queries:
            if time.time() - started > TIME_BUDGET:
                notes.append("Zeitbudget der Bildsuche erreicht – übrige Sätze mit neutraler Grafik")
                break
            found = find_media(q, descs.get(q, ""), seen, folder)
            if found:
                v.update(found)
                v["credit"] = short_credit(found["credit"])
                v["credit_voll"] = found["credit"]
                v["suche"] = q
                break
        if not v["bild"]:
            notes.append(f"Satz {i + 1}: kein passendes Bild gefunden – neutrale Grafik ({'Karte' if v.get('karte') else 'Datum' if v['datum'] else 'Zitat'})")
        out.append(v)
    return out, notes


def intro_visual(titel: str, thema: str, lang: str, folder: Path, seen: bildguete.Seen | None = None) -> dict:
    """Bild/Karte für den Einstieg (zum Thema); ohne Treffer ein ruhiges Titel-Zitat."""
    v = {"typ": "reportage", "quelle": "", "zitat": titel, "datum": "", "jahr": None, "jahre": [], "ort": "", "bild": None,
         "bild_art": "image", "credit": ""}
    info = wiki_infos([thema], lang).get(thema) or {}
    query = info.get("en") or thema
    if not re.search(r"[^\x00-\x7f]", query):
        found = find_media(query, info.get("desc", ""), seen or bildguete.Seen(), folder)
        if found:
            v.update(found)
            v["credit"], v["credit_voll"] = short_credit(found["credit"]), found["credit"]
    return v
