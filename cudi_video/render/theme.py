"""Farben, Schriften, Designs und Zeichen-Hilfen für den Infografik-Stil.

Look eines Videos (`pick_style`): Farben/Design (`STYLES`: Hintergrund, Untertitel-Stil, Effekt) passend zum
Thema, dazu ein Format (`FORMAT_NAMES`, render/formats.py: ganz anderer Bildaufbau, Zooms, Übergänge) und ein
Bewegungsprofil (`MOTIONS`, für das Format „karte“) – je Video verschieden, fest je Video-ID.
"""

from __future__ import annotations

import functools
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .. import config

W, H = config.WIDTH, config.HEIGHT

# Sichere Zone: TikTok/Shorts-Bedienelemente verdecken unten ~20 % und rechts ~11 %.
X0 = 80
CONTENT_W = 880
SUB_Y = 1385          # Mitte der Untertitel

BG_TOP = (9, 12, 30)
BG_BOTTOM = (26, 12, 52)
ACCENT = (34, 211, 238)
ACCENT2 = (139, 92, 246)
GOLD = (251, 191, 36)
SILVER = (203, 213, 225)
BRONZE = (234, 138, 60)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)
CARD = (22, 27, 54)
TRACK = (40, 46, 82)


STYLES = {
    "neon":    dict(bg_top=(9, 12, 30), bg_bottom=(26, 12, 52), accent=(34, 211, 238), accent2=(139, 92, 246),
                    card=(22, 27, 54), track=(40, 46, 82), muted=(148, 163, 184), bg="glow", subs="box", effect="none",
                    label={"de": "Neon", "en": "Neon"}),
    "natur":   dict(bg_top=(5, 22, 16), bg_bottom=(12, 40, 28), accent=(52, 211, 153), accent2=(250, 204, 21),
                    card=(14, 38, 30), track=(30, 62, 50), muted=(167, 196, 180), bg="blur", subs="box",
                    effect="particles", label={"de": "Natur", "en": "Nature"}),
    "doku":    dict(bg_top=(22, 15, 9), bg_bottom=(44, 29, 17), accent=(245, 158, 11), accent2=(217, 119, 6),
                    card=(42, 30, 20), track=(70, 52, 36), muted=(214, 196, 170), bg="blur", subs="outline",
                    effect="grain", label={"de": "Doku", "en": "Documentary"}),
    "minimal": dict(bg_top=(10, 10, 12), bg_bottom=(20, 20, 24), accent=(239, 68, 68), accent2=(115, 115, 125),
                    card=(30, 30, 34), track=(52, 52, 58), muted=(163, 163, 170), bg="flat", subs="color",
                    effect="none", label={"de": "Minimal", "en": "Minimal"}),
    "ozean":   dict(bg_top=(3, 16, 38), bg_bottom=(5, 40, 68), accent=(56, 189, 248), accent2=(45, 212, 191),
                    card=(9, 33, 60), track=(24, 58, 92), muted=(148, 180, 210), bg="glow", subs="box",
                    effect="particles", label={"de": "Ozean", "en": "Ocean"}),
    "kino":    dict(bg_top=(8, 8, 10), bg_bottom=(16, 14, 12), accent=(255, 214, 10), accent2=(245, 158, 11),
                    card=(24, 22, 20), track=(60, 56, 50), muted=(200, 196, 188), bg="glow", subs="outline",
                    effect="grain", label={"de": "Kino", "en": "Cinema"}),
    "pop":     dict(bg_top=(38, 6, 44), bg_bottom=(86, 12, 68), accent=(250, 204, 21), accent2=(236, 72, 153),
                    card=(58, 14, 62), track=(90, 30, 92), muted=(230, 190, 230), bg="glow", subs="outline",
                    effect="rays", label={"de": "Pop", "en": "Pop"}),
    # Buchlook (Format „manuskript“, render/manuskript.py): fast schwarz, Vignette, Raster, Lichtpunkte; wird nicht
    # zufällig gewählt (nicht in STYLE_FIT/TOPIC_WORDS), sondern gehört fest zum Format
    "manuskript": dict(bg_top=(21, 20, 18), bg_bottom=(2, 2, 2), accent=(233, 227, 211), accent2=(184, 160, 110),
                       card=(30, 29, 27), track=(52, 50, 46), muted=(150, 145, 132), bg="manuskript", subs="none",
                       effect="staub", label={"de": "Manuskript", "en": "Manuscript"}),
}
# Bewegungsprofile: Karte (card), Titelzeilen (title), Rang-Abzeichen (badge), Listenzeilen (rows), Foto-Schwenk (pan)
MOTIONS = {
    "gleiten": dict(card="slide", title="left", badge="pop", rows="right", pan=-0.4),
    "aufsteigen": dict(card="rise", title="rise", badge="drop", rows="rise", pan=0.9),
    "zoom": dict(card="zoom", title="scale", badge="pop", rows="fade", pan=2.2),
    "schwung": dict(card="swing", title="right", badge="slide", rows="left", pan=3.4),
}
# Welche Designs zu welchem Thema passen (Icon der Vorlage bzw. Fakten-Ranking); gewählt wird je Video verschieden
STYLE_FIT = {
    "mountain": ["natur", "kino", "doku", "minimal"], "lake": ["ozean", "natur", "kino", "minimal"],
    "waterfall": ["natur", "kino", "ozean"], "island": ["ozean", "natur", "pop", "kino"],
    "building": ["neon", "doku", "kino", "minimal"], "globe": ["neon", "doku", "minimal", "ozean", "kino"],
    "people": ["pop", "neon", "minimal"], "facts": ["neon", "pop", "minimal", "ozean", "doku", "kino"],
}
# Farben nach Themenwörtern im Titel (v. a. freie Themen und Fakten-Rankings ohne Vorlagen-Icon)
TOPIC_WORDS = {
    ("natur", "kino"): ["wald", "pflanz", "baum", "tier", "vogel", "berg", "natur", "wüste", "vulkan", "dschungel",
                        "forest", "plant", "tree", "animal", "bird", "mountain", "nature", "desert", "volcano"],
    ("ozean", "natur"): ["meer", "ozean", "tiefsee", "wasser", "fluss", "hai", "fisch", "wal", "insel", "strand",
                         "ocean", "sea", "lake", "water", "river", "shark", "fish", "whale", "island", "beach"],
    ("doku", "kino", "minimal"): ["geschicht", "antik", "römer", "mittelalter", "pharao", "burg", "schloss", "könig",
                                  "krieg", "history", "ancient", "roman", "medieval", "castle", "king", "empire"],
    ("neon", "minimal", "kino"): ["gehirn", "psych", "unterbewusst", "bewusst", "traum", "technik", "computer", "roboter",
                                  "weltall", "planet", "stern", "brain", "mind", "dream", "tech", "robot", "space",
                                  "galaxy", "universe"],
    ("pop", "neon"): ["lustig", "essen", "süß", "promi", "musik", "spiel", "funny", "food", "sweet",
                      "celebrit", "music", "game", "candy"],
}


def palette_options(icon: str | None, kind: str, topic: str) -> list[str]:
    """Designs, deren Farben zum Thema passen: Themenwörter im Titel, sonst Icon der Vorlage, sonst alle."""
    text = topic.lower()
    found: list[str] = []
    for names, words in TOPIC_WORDS.items():
        if any(w in text for w in words):
            found += [n for n in names if n not in found]
    if found:
        return found
    return STYLE_FIT.get("facts" if kind == "facts" else (icon or ""), [n for n in STYLES if n != "manuskript"])


STYLE: dict = {**STYLES["neon"], "name": "neon", **MOTIONS["gleiten"], "motion": "gleiten", "format": "karte"}


FORMAT_NAMES = ["karte", "vollbild", "kreis", "magazin", "polaroid", "zahl", "manuskript"]     # Bildaufbau, s. render/formats.py


def pick_style(spec_id: str, icon: str | None, kind: str = "numbers", wanted: str = "", topic: str = "",
               design: str = "") -> dict:
    """Look eines Videos: Farben passend zum Thema, dazu Format (ganz anderer Bildaufbau) und Bewegungsprofil –
    je Video verschieden, aber fest je Video-ID. `wanted` = im Auftrag gewähltes Format, `design` = gewählte Farben
    (App-Bearbeitung; leer = passend zum Thema)."""
    import hashlib

    def h(salt: str, n: int) -> int:
        return int(hashlib.md5(f"{spec_id}{salt}".encode()).hexdigest(), 16) % n

    options = palette_options(icon, kind, topic)
    name = design if design in STYLES and design != "manuskript" else options[h("design", len(options))]
    fmt = wanted if wanted in FORMAT_NAMES else FORMAT_NAMES[h("format", len(FORMAT_NAMES))]
    if fmt == "manuskript":
        name = "manuskript"                  # der Buchlook hat eigene Farben (fast schwarz, Off-White)
    motion = list(MOTIONS)[h("motion", len(MOTIONS))]
    return {"name": name, "format": fmt, "motion": motion}


def apply_style(style: dict | None) -> None:
    """Design für die Szenen setzen (jeder Render-Prozess ruft das selbst auf – Szenen laufen parallel)."""
    style = style or {}
    name = style.get("name") if style.get("name") in STYLES else "neon"
    motion = style.get("motion") if style.get("motion") in MOTIONS else "gleiten"
    fmt = style.get("format") if style.get("format") in FORMAT_NAMES else "karte"
    if STYLE.get("name") == name and STYLE.get("motion") == motion and STYLE.get("format") == fmt:
        return
    s = STYLES[name]
    STYLE.clear()
    STYLE.update({**s, "name": name, **MOTIONS[motion], "motion": motion, "format": fmt})
    g = globals()
    for key, const in (("bg_top", "BG_TOP"), ("bg_bottom", "BG_BOTTOM"), ("accent", "ACCENT"), ("accent2", "ACCENT2"),
                       ("card", "CARD"), ("track", "TRACK"), ("muted", "MUTED")):
        g[const] = s[key]
    background_base.cache_clear()
    full_shade.cache_clear()
    from . import scenes                          # dort per „from .theme import …“ gebundene Farben mitziehen
    for const in ("ACCENT", "ACCENT2", "CARD", "MUTED", "TRACK"):
        setattr(scenes, const, g[const])


def rank_colors(rank: int) -> tuple[tuple, tuple]:
    if rank == 1:
        return GOLD, (245, 158, 11)
    if rank == 2:
        return SILVER, (148, 163, 184)
    if rank == 3:
        return BRONZE, (194, 65, 12)
    return ACCENT, ACCENT2


# --------------------------------------------------------------------------- Schriften

FONT_CANDIDATES = {
    "black": ["InterDisplay-Black.otf", "Inter-Black.otf", "seguibl.ttf", "ariblk.ttf", "DejaVuSans-Bold.ttf"],
    "bold": ["InterDisplay-Bold.otf", "Inter-Bold.otf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "semibold": ["Inter-SemiBold.otf", "seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "regular": ["Inter-Regular.otf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"],
}


def _font_dirs() -> list[Path]:
    dirs = [config.ASSETS_DIR / "fonts", Path.home() / ".fonts", Path.home() / ".local/share/fonts"]
    if sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        dirs += [windir / "Fonts", Path.home() / "AppData/Local/Microsoft/Windows/Fonts"]
    elif sys.platform == "darwin":
        dirs += [Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path.home() / "Library/Fonts"]
    else:
        dirs += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts")]
    return [d for d in dirs if d.exists()]


@functools.lru_cache(maxsize=1)
def _font_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for d in _font_dirs():
        for path in d.rglob("*"):
            if path.suffix.lower() in (".ttf", ".otf"):
                index.setdefault(path.name.lower(), path)
    return index


# Eigene Schriften je Format (OFL, Dateien in video_assets/fonts/). Fehlt eine Datei, gilt still die Standardschrift.
# Gewichte: "black" = Titel/Zahlen, "bold" = Zwischenüberschriften, "sub" = Untertitel (fett, gut lesbar),
# "hand" = Handschrift (nur Polaroid).
FORMAT_FONTS = {
    "vollbild": {"black": ["Anton-Regular.ttf"], "bold": ["Anton-Regular.ttf"], "sub": ["Anton-Regular.ttf"]},
    "kreis": {"black": ["Poppins-ExtraBold.ttf"], "bold": ["Poppins-Bold.ttf"], "sub": ["Poppins-ExtraBold.ttf"]},
    "magazin": {"black": ["PlayfairDisplay-Black.ttf"]},
    "polaroid": {"black": ["ArchivoBlack-Regular.ttf"], "sub": ["ArchivoBlack-Regular.ttf"], "hand": ["Caveat-Bold.ttf"]},
    "zahl": {"black": ["Anton-Regular.ttf"], "sub": ["Anton-Regular.ttf"]},
    # Buchlook: Serife (EB Garamond) für Titel/Sätze, Inter für kleine Pillen; weitere Schnitte in render/manuskript.py
    "manuskript": {"black": ["EBGaramond-Medium.ttf"], "bold": ["EBGaramond-Medium.ttf"], "sub": ["EBGaramond-Regular.ttf"],
                   "semibold": ["Inter-SemiBold.ttf"], "regular": ["EBGaramond-Regular.ttf"]},
}
_BASE_WEIGHT = {"sub": "black", "hand": "black"}


def format_font_names(weight: str, fmt: str | None = None) -> list[str]:
    """Dateinamen, die das Format für dieses Gewicht bevorzugt (leer = Standardschrift)."""
    return FORMAT_FONTS.get(fmt or STYLE.get("format") or "", {}).get(weight, [])


@functools.lru_cache(maxsize=128)
def _font(weight: str, size: int, family: tuple[str, ...]) -> ImageFont.FreeTypeFont:
    index = _font_index()
    for name in (*family, *FONT_CANDIDATES[_BASE_WEIGHT.get(weight, weight)]):
        if name.lower() in index:
            return ImageFont.truetype(str(index[name.lower()]), size)
    return ImageFont.load_default(size)


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Schrift für das aktive Format (STYLE["format"]); der Cache-Schlüssel enthält die Familie."""
    return _font(weight, size, tuple(format_font_names(weight)))


# --------------------------------------------------------------------------- Animation

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def progress(t: float, start: float, duration: float) -> float:
    return clamp((t - start) / duration) if duration > 0 else float(t >= start)


def ease_out_cubic(p: float) -> float:
    return 1 - (1 - p) ** 3


def ease_out_back(p: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_in_out(p: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * p)


# --------------------------------------------------------------------------- Zeichnen

def wrap(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if fnt.getlength(trial) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_font(text: str, weight: str, size: int, max_width: int, max_lines: int, min_size: int = 30):
    """Größte Schrift, bei der der Text in `max_lines` Zeilen passt."""
    while size > min_size:
        fnt = font(weight, size)
        lines = wrap(text, fnt, max_width)
        if len(lines) <= max_lines and all(fnt.getlength(l) <= max_width for l in lines):
            return fnt, lines
        size -= 4
    fnt = font(weight, min_size)
    return fnt, wrap(text, fnt, max_width)[:max_lines]


def text_layer(lines: list[str] | str, fnt, fill=WHITE, align="left", spacing=1.08, width: int | None = None) -> Image.Image:
    if isinstance(lines, str):
        lines = [lines]
    ascent, descent = fnt.getmetrics()
    line_h = int((ascent + descent) * spacing)
    w = width or int(max(fnt.getlength(l) for l in lines)) + 4
    img = Image.new("RGBA", (w, line_h * len(lines) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        lw = fnt.getlength(line)
        x = {"left": 0, "center": (w - lw) / 2, "right": w - lw}[align]
        d.text((x, i * line_h), line, font=fnt, fill=fill)
    return img


def gradient_fill(mask_layer: Image.Image, c1, c2, vertical=False) -> Image.Image:
    """Färbt die Deckkraft eines Text-Layers mit einem Farbverlauf ein."""
    w, h = mask_layer.size
    grad = linear_gradient((w, h), c1, c2, vertical=vertical)
    out = grad.convert("RGBA")
    out.putalpha(mask_layer.getchannel("A"))
    return out


@functools.lru_cache(maxsize=32)
def linear_gradient(size: tuple[int, int], c1, c2, vertical=True) -> Image.Image:
    w, h = size
    steps = h if vertical else w
    strip = Image.new("RGB", (1, steps) if vertical else (steps, 1))
    px = strip.load()
    for i in range(steps):
        p = i / max(1, steps - 1)
        c = tuple(int(c1[k] + (c2[k] - c1[k]) * p) for k in range(3))
        px[(0, i) if vertical else (i, 0)] = c
    return strip.resize((w, h))


@functools.lru_cache(maxsize=32)
def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    scale = 3  # Kantenglättung
    big = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius * scale, fill=255)
    return big.resize(size, Image.LANCZOS)


def rounded_rect(size, radius, fill) -> Image.Image:
    img = Image.new("RGBA", size, fill if len(fill) == 4 else (*fill, 255))
    img.putalpha(ImageChops.multiply(img.getchannel("A"), rounded_mask(tuple(size), radius)))
    return img


def shadow(layer: Image.Image, blur: int = 24, opacity: int = 150, grow: int = 0) -> Image.Image:
    pad = blur * 2 + grow
    sh = Image.new("RGBA", (layer.width + pad * 2, layer.height + pad * 2), (0, 0, 0, 0))
    alpha = layer.getchannel("A").point(lambda a: a * opacity // 255)
    sh.paste((0, 0, 0, 255), (pad, pad), alpha)
    return sh.filter(ImageFilter.GaussianBlur(blur))


def with_opacity(layer: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return layer
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda a: int(a * opacity)))
    return out


def paste(dst: Image.Image, layer: Image.Image, xy, opacity: float = 1.0) -> None:
    """Alpha-Blending mit Zuschnitt an den Bildrändern."""
    if opacity <= 0.003:
        return
    x, y = int(round(xy[0])), int(round(xy[1]))
    left, top = max(0, -x), max(0, -y)
    right = min(layer.width, dst.width - x)
    bottom = min(layer.height, dst.height - y)
    if right <= left or bottom <= top:
        return
    part = layer if (left, top, right, bottom) == (0, 0, layer.width, layer.height) else layer.crop((left, top, right, bottom))
    dst.alpha_composite(with_opacity(part, opacity), (x + left, y + top))


@functools.lru_cache(maxsize=8)
def glow_blob(radius: int, color: tuple, strength: int = 110) -> Image.Image:
    """Weicher Lichtfleck. Die Fläche ist um radius/2 je Seite größer als früher, damit die Unschärfe am Rand
    sicher auf 0 abklingt (sonst schimmern auf dunklen Designs Rechteck-Kanten durch)."""
    pad = radius // 2
    size = radius * 2 + 2 * pad
    blob = Image.new("RGBA", (size, size), (*color, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((pad + radius // 2, pad + radius // 2, size - pad - radius // 2, size - pad - radius // 2),
                                 fill=strength)
    blob.putalpha(mask.filter(ImageFilter.GaussianBlur(radius // 3)))
    return blob


@functools.lru_cache(maxsize=2)
def background_base() -> Image.Image:
    return linear_gradient((W, H), BG_TOP, BG_BOTTOM, vertical=True).convert("RGBA")


def background(t: float, tint=None, tint2=None, backdrop: Image.Image | None = None) -> Image.Image:
    """Hintergrund im aktuellen Design: Lichtflecken (glow), schlicht (flat) oder unscharfes Foto (blur), dazu der
    Effekt des Designs (Partikel, Lichtstrahlen, Filmkorn)."""
    mode = STYLE.get("bg", "glow")
    if mode == "manuskript":
        from . import manuskript
        return manuskript.background(t)
    tint, tint2 = tint or ACCENT, tint2 or ACCENT2
    img = backdrop.copy() if backdrop is not None and mode == "blur" else background_base().copy()
    if mode == "glow" or (mode == "blur" and backdrop is None):
        paste(img, glow_blob(420, tint), (-390 + 120 * math.sin(t * 0.35), -70 + 90 * math.cos(t * 0.27)))
        paste(img, glow_blob(460, tint2), (290 + 110 * math.cos(t * 0.31), 920 + 120 * math.sin(t * 0.23)))
    effect = STYLE.get("effect")
    if effect == "particles":
        d = ImageDraw.Draw(img)
        for i in range(34):
            x = (i * 137.5 + 40 * math.sin(t * 0.5 + i)) % W
            y = (H - ((i * 211 + t * (30 + i % 5 * 12)) % (H + 40))) - 20
            r = 2 + i % 4
            d.ellipse((x - r, y - r, x + r, y + r), fill=(*tint, 90 + (i % 3) * 40))
    elif effect == "rays":
        paste(img, _rays(tint2), (0, 0), opacity=0.55 + 0.25 * math.sin(t * 0.8))
    elif effect == "grain":
        paste(img, _grain(int(t * 12) % 4), (0, 0))
    return img


@functools.lru_cache(maxsize=2)
def full_shade() -> Image.Image:
    """Vollbild-Layout: oben und unten abgedunkelt, damit Kopfzeile, Name und Untertitel auf jedem Clip lesbar sind."""
    alpha = Image.new("L", (1, H))
    for y in range(H):
        top = max(0.0, 1 - y / 300) * 170
        bottom = clamp((y - 620) / 640) ** 1.3 * 235
        alpha.putpixel((0, y), int(max(top, bottom)))
    layer = Image.new("RGBA", (W, H), (*BG_TOP, 255))
    layer.putalpha(alpha.resize((W, H)))
    return layer


def backdrop_from(img: Image.Image) -> Image.Image:
    """Unscharfes, abgedunkeltes Vollbild aus dem Foto/Clip eines Platzes (Design-Hintergrund „blur“)."""
    small = cover_crop(img.convert("RGB"), (W // 6, H // 6)).filter(ImageFilter.GaussianBlur(5))
    big = small.resize((W, H), Image.BILINEAR).convert("RGBA")
    shade = linear_gradient((W, H), BG_TOP, BG_BOTTOM, vertical=True).convert("RGBA")
    return Image.blend(big, shade, 0.62)


@functools.lru_cache(maxsize=8)
def _rays(color: tuple) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, x in enumerate(range(-400, W + 400, 260)):
        d.polygon([(x, 0), (x + 90, 0), (x + 90 + 500, H), (x + 500, H)], fill=(*color, 26 if i % 2 else 14))
    return layer.filter(ImageFilter.GaussianBlur(30))


@functools.lru_cache(maxsize=4)
def _grain(seed: int) -> Image.Image:
    import random as _r

    rnd = _r.Random(seed)
    tile = Image.new("L", (240, 240))
    tile.putdata([rnd.randint(0, 255) for _ in range(240 * 240)])
    noise = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    alpha = Image.new("L", (W, H))
    for x in range(0, W, 240):
        for y in range(0, H, 240):
            alpha.paste(tile, (x, y))
    noise.putalpha(alpha.point(lambda a: a // 14))
    return noise


def cover_crop(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Bild formatfüllend zuschneiden (wie CSS object-fit: cover)."""
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((max(tw, int(img.width * scale + 0.5)), max(th, int(img.height * scale + 0.5))), Image.LANCZOS)
    left = (resized.width - tw) // 2
    top = (resized.height - th) // 3   # eher oberes Drittel behalten (Gebäudespitzen, Gipfel)
    return resized.crop((left, top, left + tw, top + th))
