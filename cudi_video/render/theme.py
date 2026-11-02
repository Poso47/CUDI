"""Farben, Schriften und Zeichen-Hilfen für den Infografik-Stil."""

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


@functools.lru_cache(maxsize=64)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    index = _font_index()
    for name in FONT_CANDIDATES[weight]:
        if name.lower() in index:
            return ImageFont.truetype(str(index[name.lower()]), size)
    return ImageFont.load_default(size)


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
    size = radius * 2
    blob = Image.new("RGBA", (size, size), (*color, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((radius // 2, radius // 2, size - radius // 2, size - radius // 2), fill=strength)
    blob.putalpha(mask.filter(ImageFilter.GaussianBlur(radius // 3)))
    return blob


@functools.lru_cache(maxsize=2)
def background_base() -> Image.Image:
    return linear_gradient((W, H), BG_TOP, BG_BOTTOM, vertical=True).convert("RGBA")


def background(t: float, tint=ACCENT, tint2=ACCENT2) -> Image.Image:
    """Dunkler Verlauf mit zwei langsam wandernden Lichtflecken."""
    img = background_base().copy()
    paste(img, glow_blob(420, tint), (-180 + 120 * math.sin(t * 0.35), 140 + 90 * math.cos(t * 0.27)))
    paste(img, glow_blob(460, tint2), (520 + 110 * math.cos(t * 0.31), 1150 + 120 * math.sin(t * 0.23)))
    return img


def cover_crop(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Bild formatfüllend zuschneiden (wie CSS object-fit: cover)."""
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((max(tw, int(img.width * scale + 0.5)), max(th, int(img.height * scale + 0.5))), Image.LANCZOS)
    left = (resized.width - tw) // 2
    top = (resized.height - th) // 3   # eher oberes Drittel behalten (Gebäudespitzen, Gipfel)
    return resized.crop((left, top, left + tw, top + th))
