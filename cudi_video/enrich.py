"""Optionale Anreicherung: Wikipedia-Einleitung und Commons-Bild mit Lizenz.

Fehlt etwas (Rate-Limit, kein Bild, unklare Lizenz), läuft die Pipeline ohne weiter.
Bilder werden nur verwendet, wenn Urheber und freie Lizenz bekannt sind.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from html import unescape
from urllib.parse import quote

from bs4 import BeautifulSoup

from . import net
from .models import RankItem, Research

log = logging.getLogger(__name__)

THUMB_WIDTH = 1280
NON_FREE = re.compile(r"non-free|fair use|copyrighted|all rights reserved", re.I)
PUBLIC_DOMAIN = re.compile(r"public domain|^pd\b|cc0|no restrictions|gemeinfrei", re.I)
UNKNOWN_AUTHOR = re.compile(r"^\W*(unknown|unbekannt|anonym\w*|n/?a|none|not (stated|given)|see (below|source))\b", re.I)
RETRY_PAUSE = 20        # Sekunden Pause vor dem zweiten Versuch, wenn Wikimedia gedrosselt hat


def fetch_summary(lang: str, title: str) -> str | None:
    """Einleitung des Artikels (None bei Begriffsklärung). Wirft net.FetchError bei Verbindungsproblemen."""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}"
    data = net.get_json(url, cache_hours=24, retries=2, max_wait=15)
    if data.get("type") == "disambiguation":
        return None
    return data.get("extract") or None


def _strip_html(html: str) -> str:
    return unescape(BeautifulSoup(html or "", "lxml").get_text(" ", strip=True))


def credit_author(meta: dict, license_name: str) -> str | None:
    """Urheber für den Bildnachweis aus den Commons-Metadaten.

    None, wenn die Lizenz eine Namensnennung verlangt (CC BY, CC BY-SA, GFDL …), aber kein
    brauchbarer Urheber angegeben ist – solche Bilder werden nicht verwendet. Gemeinfreie Bilder
    (Public Domain, CC0) dürfen auch ohne Urheber genutzt werden."""
    author = ""
    for field in ("Artist", "Attribution"):
        text = _strip_html(meta.get(field, {}).get("value", ""))
        if text and not UNKNOWN_AUTHOR.search(text):
            author = text
            break
    if author:
        return author
    flag = str(meta.get("AttributionRequired", {}).get("value", "")).lower()
    required = flag == "true" if flag in ("true", "false") else not PUBLIC_DOMAIN.search(license_name)
    return None if required else "Urheber unbekannt"


def fetch_license(filename: str) -> dict | None:
    """Urheber und freie Lizenz (sonst None). Wirft net.FetchError bei Verbindungsproblemen."""
    data = net.get_json(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
            "iiprop": "extmetadata|size", "format": "json", "formatversion": 2,
        },
        cache_hours=24 * 30, retries=2, max_wait=15,
    )
    try:
        info = data["query"]["pages"][0]["imageinfo"][0]
    except (KeyError, IndexError):
        log.warning("Lizenz für %s nicht ermittelbar", filename)
        return None
    meta = info.get("extmetadata", {})
    license_name = meta.get("LicenseShortName", {}).get("value", "")
    if not license_name or NON_FREE.search(license_name):
        return None
    artist = credit_author(meta, license_name)
    if not artist:
        log.info("Bild %s nicht verwendet: %s verlangt Namensnennung, Urheber fehlt", filename, license_name)
        return None
    return {"license": license_name, "artist": artist, "width": info.get("width", 0)}


def thumb_url(filename: str, width: int) -> str:
    name = filename.replace(" ", "_")
    md5 = hashlib.md5(name.encode()).hexdigest()
    q = quote(name)
    suffix = ".png" if name.lower().endswith((".svg", ".tif", ".tiff")) else ""
    return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{md5[0]}/{md5[:2]}/{q}/{width}px-{q}{suffix}"


def original_url(filename: str) -> str:
    name = filename.replace(" ", "_")
    md5 = hashlib.md5(name.encode()).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[:2]}/{quote(name)}"


def fetch_image(item: RankItem) -> bool:
    """Bild mit Lizenz laden. False, wenn es an der Verbindung scheiterte (neuer Versuch lohnt sich)."""
    if not item.image_file:
        return True
    try:
        lic = fetch_license(item.image_file)
        if not lic:
            return True
        use_thumb = lic["width"] > THUMB_WIDTH or item.image_file.lower().endswith(".svg")
        url = thumb_url(item.image_file, THUMB_WIDTH) if use_thumb else original_url(item.image_file)
        path = net.download(url, suffix=".img", retries=2, max_wait=15)
    except net.FetchError as exc:
        log.warning("Bild nicht geladen (%s): %s", item.image_file, exc)
        return False
    item.image_path = str(path)
    item.image_credit = f"{lic['artist']} – {lic['license']} – Wikimedia Commons: File:{item.image_file}"
    return True


def _enrich_item(item: RankItem, langs: list[str], images: bool) -> bool:
    """Fehlende Einleitungen und Bild laden. False, wenn etwas an der Verbindung scheiterte."""
    ok = True
    for lang in langs:
        title = item.wiki_titles.get(lang)
        if title and lang not in item.summary:
            try:
                text = fetch_summary(lang, title)
            except net.FetchError as exc:
                log.warning("Wikipedia-Zusammenfassung nicht verfügbar (%s): %s", title, exc)
                ok = False
                continue
            if text:
                item.summary[lang] = text
    if images and not item.image_path:
        ok = fetch_image(item) and ok
    return ok


def enrich(research: Research, langs: list[str], images: bool = True) -> Research:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:            # mehrere Plätze gleichzeitig
        done = list(pool.map(lambda it: _enrich_item(it, langs, images), research.items))
    failed = [item for item, ok in zip(research.items, done) if not ok]
    if failed:
        # Wikimedia drosselt zeitweise – nach einer kurzen Pause klappt es meist.
        log.info("Zweiter Versuch für %d Einträge in %d s", len(failed), RETRY_PAUSE)
        time.sleep(RETRY_PAUSE)
        net.reset_blocks()
        for item in failed:
            _enrich_item(item, langs, images)
    missing = [it.labels.get(langs[0], it.qid) for it in research.items if not it.image_path]
    if missing:
        research.warnings.append(f"Ohne Bild (Grafik-Platzhalter): {', '.join(missing)}")
    return research
