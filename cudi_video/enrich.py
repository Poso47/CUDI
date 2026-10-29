"""Optionale Anreicherung: Wikipedia-Einleitung und Commons-Bild mit Lizenz.

Fehlt etwas (Rate-Limit, kein Bild, unklare Lizenz), läuft die Pipeline ohne weiter.
Bilder werden nur verwendet, wenn Urheber und freie Lizenz bekannt sind.
"""

from __future__ import annotations

import hashlib
import logging
import re
from html import unescape
from urllib.parse import quote

from bs4 import BeautifulSoup

from . import net
from .models import RankItem, Research

log = logging.getLogger(__name__)

THUMB_WIDTH = 1280
NON_FREE = re.compile(r"non-free|fair use|copyrighted", re.I)


def fetch_summary(lang: str, title: str) -> str | None:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}"
    try:
        data = net.get_json(url, cache_hours=24, retries=2, max_wait=15)
    except net.FetchError as exc:
        log.warning("Wikipedia-Zusammenfassung nicht verfügbar (%s): %s", title, exc)
        return None
    if data.get("type") == "disambiguation":
        return None
    return data.get("extract") or None


def _strip_html(html: str) -> str:
    return unescape(BeautifulSoup(html or "", "lxml").get_text(" ", strip=True))


def fetch_license(filename: str) -> dict | None:
    try:
        data = net.get_json(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
                "iiprop": "extmetadata|size", "format": "json", "formatversion": 2,
            },
            cache_hours=24 * 30, retries=2, max_wait=15,
        )
        info = data["query"]["pages"][0]["imageinfo"][0]
    except (net.FetchError, KeyError, IndexError) as exc:
        log.warning("Lizenz für %s nicht ermittelbar: %s", filename, exc)
        return None
    meta = info.get("extmetadata", {})
    license_name = meta.get("LicenseShortName", {}).get("value", "")
    artist = _strip_html(meta.get("Artist", {}).get("value", ""))
    if not license_name or NON_FREE.search(license_name):
        return None
    return {"license": license_name, "artist": artist or "unbekannt", "width": info.get("width", 0)}


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


def fetch_image(item: RankItem) -> None:
    if not item.image_file:
        return
    lic = fetch_license(item.image_file)
    if not lic:
        return
    use_thumb = lic["width"] > THUMB_WIDTH or item.image_file.lower().endswith(".svg")
    url = thumb_url(item.image_file, THUMB_WIDTH) if use_thumb else original_url(item.image_file)
    try:
        path = net.download(url, suffix=".img", retries=2, max_wait=15)
    except net.FetchError as exc:
        log.warning("Bild-Download fehlgeschlagen (%s): %s", item.image_file, exc)
        return
    item.image_path = str(path)
    item.image_credit = f"{lic['artist']} – {lic['license']} – Wikimedia Commons: File:{item.image_file}"


def enrich(research: Research, langs: list[str], images: bool = True) -> Research:
    for item in research.items:
        for lang in langs:
            title = item.wiki_titles.get(lang)
            if title and lang not in item.summary:
                text = fetch_summary(lang, title)
                if text:
                    item.summary[lang] = text
        if images and not item.image_path:
            fetch_image(item)
    missing = [it.labels.get("en", it.qid) for it in research.items if not it.image_path]
    if missing:
        research.warnings.append(f"Ohne Bild (Grafik-Platzhalter): {', '.join(missing)}")
    return research
