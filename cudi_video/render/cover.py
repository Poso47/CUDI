"""Gestaltetes Cover (Vorschaubild, 1080x1920 JPG): großes Titelwort, Spitzenwert mit Neugier-Lücke, bestes Bild.

Farben und Schrift folgen dem Look des Videos (`theme.STYLES`, `theme.FORMAT_FONTS`); alles Wichtige liegt in der
Safe-Zone (unten ~20 % und rechts ~11 % verdecken TikTok/Shorts). Das Cover dient zugleich als erstes Frame
(0,2 s) des Videos, damit Plattformen ein starkes Vorschaubild wählen. Nichts wird erfunden: Zahlen stammen aus den
geprüften Werten, der Name von Platz 1 bleibt verborgen (Neugier-Lücke).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import theme
from .theme import H, W, X0, CONTENT_W

log = logging.getLogger(__name__)

FIRST_FRAME_SECONDS = 0.2
SAFE_TOP, SAFE_BOTTOM = 170, 1500            # y-Bereich ohne Plattform-Bedienelemente
UPPER_FORMATS = {"vollbild", "zahl"}          # Anton-Formate: Plakat-Versalien
LEFT_FORMATS = {"magazin", "manuskript"}      # Zeitschrift/Buch: linksbündig
STOP = {"de": set("der die das den dem des ein eine einer und oder von vom zu zur zum im in am an auf für mit aus bei "
                  "nach über unter welt top".split()),
        "en": set("the a an of and or in on at for with to from by world top".split())}
EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿️]")

BADGE = {"numbers": {"de": "TOP {n}", "en": "TOP {n}"}, "facts": {"de": "{n} FAKTEN", "en": "{n} FACTS"}}
TEASER = {"de": "Kennst du Platz 1?", "en": "Can you guess #1?"}
TEASER_FACTS = {"de": "Fakt Nr. 1 gleich im Video", "en": "Fact #1 coming up"}
PLACE = {"de": "Platz 1", "en": "No. 1"}


def clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", EMOJI.sub("", title)).strip(" –-:")


def cover_texts(spec, research, lang: str) -> dict:
    """Texte fürs Cover aus Spec und geprüften Werten: Kopfzeile, Titel, Spitzenwert, Neugier-Zeile."""
    from ..units import quantity

    items = sorted(research.items, key=lambda i: i.rank)
    n = len(items) or spec.count
    kind = "facts" if spec.kind == "facts" else "numbers"
    value = ""
    if kind == "numbers" and items:
        try:
            value = quantity(items[0].value, items[0].unit, spec.unit).display(lang)
        except Exception:                                   # fehlender Wert: Cover ohne Spitzenwert
            value = ""
    return {
        "headline": clean_title(spec.title.get(lang) or next(iter(spec.title.values()))),
        "badge": BADGE[kind][lang].format(n=n),
        "peak": f"{PLACE[lang]}: {value}" if value else "",
        "teaser": (TEASER_FACTS if kind == "facts" else TEASER)[lang],
        "image_path": best_image(items),
    }


def best_image(items) -> str | None:
    """Bestes vorhandenes Bild: Platz 1 (Bildprüfung lief schon bei der Auswahl), sonst das nächste vorhandene."""
    for it in items:
        if it.image_path and Path(it.image_path).exists() and (it.image_kind or "photo") != "flag":
            return it.image_path
    return None


def _key_word(words: list[str], lang: str) -> int:
    """Index des Titelworts, das farbig hervorgehoben wird: längstes Wort, das kein Füllwort/keine Zahl ist."""
    best, size = -1, 0
    for i, w in enumerate(words):
        bare = re.sub(r"\W", "", w).lower()
        if bare and not bare.isdigit() and bare not in STOP[lang] and len(bare) > size:
            best, size = i, len(bare)
    return best


def _backdrop(image_path: str | None) -> Image.Image:
    if image_path:
        try:
            photo = theme.cover_crop(Image.open(image_path).convert("RGB"), (W, H)).convert("RGBA")
            dark = Image.new("RGBA", (W, H), (*theme.BG_TOP, 255))
            alpha = Image.new("L", (1, H))
            for y in range(H):                      # oben und unten dunkler: Titel und Zeile bleiben lesbar
                a = 0.50 + 0.30 * theme.clamp((y - 900) / 600) + 0.15 * theme.clamp(1 - y / 500)
                alpha.putpixel((0, y), int(255 * min(a, 0.88)))
            dark.putalpha(alpha.resize((W, H)))
            photo.alpha_composite(dark)
            return photo
        except OSError:
            pass
    return theme.background(2.0).convert("RGBA")


def make_cover(path: Path, *, headline: str, badge: str = "", peak: str = "", teaser: str = "",
               image_path: str | None = None, style: dict | None = None, lang: str = "de") -> Path:
    theme.apply_style(style)
    fmt = theme.STYLE.get("format", "karte")
    accent, accent2 = theme.ACCENT, theme.ACCENT2
    left = fmt in LEFT_FORMATS
    img = _backdrop(image_path)
    d = ImageDraw.Draw(img)

    text = headline.upper() if fmt in UPPER_FORMATS else headline
    fnt, lines = theme.fit_font(text, "black", 170 if peak else 190, CONTENT_W, 4, min_size=84)
    line_h = int(sum(fnt.getmetrics()) * 0.98)
    pf = theme.fit_font(peak, "black", 120, CONTENT_W - 60, 1, min_size=60)[0] if peak else None
    ph = int(sum(pf.getmetrics()) * 1.05) + 36 if peak else 0
    total = ((104 + 70) if badge else 0) + line_h * len(lines) + 50 + ((ph + 36) if peak else 0) + (90 if teaser else 0)
    y = SAFE_TOP + max(0, (SAFE_BOTTOM - SAFE_TOP - total) // 2)
    if badge:                                        # Kopfzeile: Zahl als Pille
        bf = theme.font("black", 58)
        w = int(bf.getlength(badge)) + 70
        x = X0 if left else (W - w) // 2
        pill = theme.rounded_rect((w, 104), 52, accent)
        theme.paste(img, pill, (x, y))
        ink = theme.BG_TOP if sum(accent) > 380 else theme.WHITE
        d.text((x + 35, y + 52), badge, font=bf, fill=ink, anchor="lm")
        y += 104 + 70

    key = _key_word(text.split(), lang)
    block_h = line_h * len(lines)
    space = fnt.getlength(" ")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    placed = []                                      # (x, y, Wort, Farbe)
    idx = 0
    for row, line in enumerate(lines):
        x = X0 if left else (W - fnt.getlength(line)) / 2
        for word in line.split():
            placed.append((x, y + row * line_h, word, accent if idx == key else theme.WHITE))
            sd.text((x + 5, y + row * line_h + 7), word, font=fnt, fill=(0, 0, 0, 200))
            x += fnt.getlength(word) + space
            idx += 1
    img = Image.alpha_composite(img, shade.filter(theme.ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(img)
    for x, wy, word, color in placed:
        d.text((x, wy), word, font=fnt, fill=color)
    y += block_h + 50

    if peak:                                         # Spitzenwert: Zahl groß, Name von Platz 1 bleibt offen
        pw = int(pf.getlength(peak)) + 80
        x = X0 if left else (W - pw) // 2
        box = theme.rounded_rect((pw, ph), 34, (*theme.CARD, 235))
        theme.paste(img, box, (x, y))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((x, y, x + pw, y + ph), 34, outline=theme.GOLD, width=5)
        d.text((x + pw / 2, y + ph / 2), peak, font=pf, fill=theme.GOLD, anchor="mm")
        y += ph + 36
    if teaser:
        tf = theme.fit_font(teaser, "bold", 64, CONTENT_W, 1, min_size=40)[0]
        tx = X0 if left else W / 2
        d.text((tx + 3, y + 3), teaser, font=tf, fill=(0, 0, 0), anchor="la" if left else "ma")
        d.text((tx, y), teaser, font=tf, fill=accent2 if sum(accent2) > 330 else theme.WHITE, anchor="la" if left else "ma")
        y += 90
    img = img.convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=92)
    return path


def make_cover_for(path: Path, spec, research, lang: str, style: dict) -> Path:
    """Cover für ein Ranking/Fakten-Video aus Spec und Recherche."""
    t = cover_texts(spec, research, lang)
    return make_cover(path, headline=t["headline"], badge=t["badge"], peak=t["peak"], teaser=t["teaser"],
                      image_path=t["image_path"], style=style, lang=lang)


def make_cover_safe(path: Path, spec, research, lang: str, style: dict) -> bool:
    """Cover erzeugen; bei einem Fehler (Bild kaputt, Schrift fehlt) ist False die Antwort – der Aufrufer nimmt dann
    das alte Standbild, das Video entsteht in jedem Fall."""
    try:
        make_cover_for(path, spec, research, lang, style)
        return True
    except Exception as exc:                          # noqa: BLE001 – ein Cover darf nie ein Video verhindern
        log.warning("Cover-Gestaltung fehlgeschlagen (%s) – Standbild wird genommen", exc)
        return False


def stamp_first_frame(video: Path, cover: Path, out: Path, seconds: float = FIRST_FRAME_SECONDS) -> bool:
    """Cover als allererstes Frame (0,2 s) vor das Bild legen, damit TikTok/Shorts ein starkes Vorschaubild nehmen.
    Der Ton bleibt unberührt (nur Überblendung, Länge gleich). Abschaltbar mit CUDI_COVER_FRAME=0; Fehler -> False."""
    if os.environ.get("CUDI_COVER_FRAME", "1") == "0":
        return False
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-loop", "1", "-i", str(cover),
                        "-filter_complex", f"[1:v]scale={W}:{H},format=yuv420p[c];[0:v][c]overlay=0:0:enable='lt(t,{seconds})':shortest=1[v]",
                        "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                        "-g", "60", str(out)], check=True, capture_output=True, timeout=1800)
        return out.exists() and out.stat().st_size > 0
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("Erstes Frame nicht gesetzt (%s)", exc)
        return False
