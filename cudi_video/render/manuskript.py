"""Baukasten für den Stil „manuskript“ (ruhige Erklärvideos im dunklen Buchlook).

Fast schwarzer Grund mit weicher Vignette, feinem Raster und schwebenden Lichtpunkten; Serifenschrift in warmem
Off-White; der Satz oben erscheint Wort für Wort zur Stimme (Schlüsselwörter fett-kursiv); kleine Pillen (Kapitel,
Quelle); in der Mitte Linien-Grafiken (`linien.py`). Alles gezeichnet mit PIL – keine Netzabhängigkeit.
"""

from __future__ import annotations

import functools
import math
import random
import re

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from . import theme as T
from .theme import H, W, clamp, ease_in_out, ease_out_cubic, paste, progress

INK = (233, 227, 211)             # warmes Off-White
INK_DIM = (150, 145, 132)
INK_FAINT = (104, 100, 91)
BG_CENTER = (21, 20, 18)
BG_EDGE = (2, 2, 2)
CX, CY = W // 2, 940              # Mitte der Grafik
TEXT_Y = 262                      # Oberkante des Satzes ohne Kapitel-Pille
TEXT_Y_PILL = 392                 # … mit Kapitel-Pille
PILL_Y = 330                      # Mitte der Kapitel-Pille

FILES = {
    "serif": "EBGaramond-Regular.ttf", "serif_m": "EBGaramond-Medium.ttf", "italic": "EBGaramond-Italic.ttf",
    "bolditalic": "EBGaramond-SemiBoldItalic.ttf", "sans": "Inter-SemiBold.ttf", "arabic": "Amiri-Regular.ttf",
}


@functools.lru_cache(maxsize=64)
def mfont(kind: str, size: int) -> ImageFont.FreeTypeFont:
    """Schrift des Stils; fehlt die Datei, gilt still die Standardschrift (Tests ohne Schriftdateien laufen weiter)."""
    path = T._font_index().get(FILES[kind].lower())
    if path is not None:
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


# --------------------------------------------------------------------------- Hintergrund

@functools.lru_cache(maxsize=1)
def base_background() -> Image.Image:
    """Vignette (Mitte minimal heller), sehr feines Linienraster zur Mitte hin sichtbar."""
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.hypot((xs - CX) / (W * 0.66), (ys - CY) / (H * 0.52))
    v = np.clip(1.0 - d, 0.0, 1.0) ** 1.5
    edge, center = np.array(BG_EDGE, np.float32), np.array(BG_CENTER, np.float32)
    img = edge[None, None, :] + (center - edge)[None, None, :] * v[:, :, None]
    grid = (((xs + 36) % 108 < 1.6) | ((ys + 12) % 108 < 1.6)).astype(np.float32)
    img += grid[:, :, None] * (3.0 + 5.0 * v[:, :, None])
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


@functools.lru_cache(maxsize=4)
def _dust_sprite(r: int) -> Image.Image:
    size = r * 8
    img = Image.new("L", (size, size), 0)
    ImageDraw.Draw(img).ellipse((size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r), fill=255)
    img = img.filter(ImageFilter.GaussianBlur(max(1.0, r * 0.9)))
    out = Image.new("RGBA", (size, size), (*INK, 0))
    out.putalpha(img)
    return out


@functools.lru_cache(maxsize=1)
def _dust() -> list[tuple]:
    rnd = random.Random(11)
    return [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(-5, 5), rnd.uniform(-9, -2), rnd.choice((1, 1, 1, 2, 2, 3)),
             rnd.uniform(0, 6.28), rnd.uniform(0.15, 0.7)) for _ in range(46)]


def background(t: float) -> Image.Image:
    """Hintergrund des Stils „manuskript“ mit langsam schwebenden Lichtpunkten (Effekt „staub“)."""
    img = base_background().copy()
    for x, y, vx, vy, r, ph, strength in _dust():
        px, py = (x + vx * t) % W, (y + vy * t) % H
        glint = 0.55 + 0.45 * math.sin(t * 0.8 + ph)
        sp = _dust_sprite(r)
        paste(img, sp, (px - sp.width / 2, py - sp.height / 2), opacity=strength * glint)
    return img


# --------------------------------------------------------------------------- Linien-Zeichner

class Art:
    """Leinwand für Linien-Grafiken: Zeichnen in doppelter Auflösung (glatte Kanten), weiches Leuchten am Ende.

    `m` = Linien mit Leuchten, `f` = flache Flächen ohne Leuchten (Karten, Raster). Koordinaten in Bildpunkten."""

    def __init__(self, w: int, h: int, ss: int = 2):
        self.w, self.h, self.ss = w, h, ss
        self.m = Image.new("L", (w * ss, h * ss), 0)
        self.f = Image.new("L", (w * ss, h * ss), 0)
        self.d = ImageDraw.Draw(self.m)
        self.fd = ImageDraw.Draw(self.f)

    def _p(self, pts):
        return [(x * self.ss, y * self.ss) for x, y in pts]

    def line(self, pts, width: float = 3.0, a: float = 1.0, caps: bool = True, flat: bool = False) -> None:
        if len(pts) < 2 or a <= 0:
            return
        d, val, wd = (self.fd if flat else self.d), int(255 * clamp(a)), max(1, int(width * self.ss))
        P = self._p(pts)
        d.line(P, fill=val, width=wd, joint="curve")
        if caps and width >= 2:
            r = wd / 2
            for x, y in (P[0], P[-1]):
                d.ellipse((x - r, y - r, x + r, y + r), fill=val)

    def dot(self, x: float, y: float, r: float, a: float = 1.0, flat: bool = False) -> None:
        if a <= 0:
            return
        d, s = (self.fd if flat else self.d), self.ss
        d.ellipse(((x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s), fill=int(255 * clamp(a)))

    def ring(self, x: float, y: float, r: float, width: float = 2.0, a: float = 1.0, flat: bool = False) -> None:
        d, s = (self.fd if flat else self.d), self.ss
        d.ellipse(((x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s), outline=int(255 * clamp(a)), width=max(1, int(width * s)))

    def rect(self, box, a_fill: float = 0.0, a_line: float = 0.0, width: float = 2.0, radius: float = 0, flat: bool = True) -> None:
        d, s = (self.fd if flat else self.d), self.ss
        b = tuple(v * s for v in box)
        fill = int(255 * a_fill) if a_fill > 0 else None
        out = int(255 * a_line) if a_line > 0 else None
        d.rounded_rectangle(b, radius * s, fill=fill, outline=out, width=max(1, int(width * s)))

    def polygon(self, pts, a: float = 1.0, flat: bool = True) -> None:
        (self.fd if flat else self.d).polygon(self._p(pts), fill=int(255 * clamp(a)))

    def text(self, xy, txt: str, font: ImageFont.FreeTypeFont, a: float = 1.0, anchor: str = "ls") -> None:
        """Text mit der Schrift in Bildpunkt-Größe (wird intern auf die Auflösung hochgesetzt)."""
        big = font.font_variant(size=int(font.size * self.ss))
        self.d.text((xy[0] * self.ss, xy[1] * self.ss), txt, font=big, fill=int(255 * clamp(a)), anchor=anchor)

    def image(self, glow: float = 0.45, blur: float = 7.0, alpha: float = 1.0, color=INK) -> Image.Image:
        small = self.m.resize((self.w, self.h), Image.LANCZOS)
        flat = self.f.resize((self.w, self.h), Image.LANCZOS)
        a = small
        if glow > 0:
            halo = small.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, int(v * glow * 1.6)))
            a = ImageChops.add(small, halo)
        a = ImageChops.lighter(a, flat)
        if alpha < 0.999:
            a = a.point(lambda v: int(v * alpha))
        out = Image.new("RGBA", (self.w, self.h), (*color, 0))
        out.putalpha(a)
        return out


def partial(pts: list[tuple[float, float]], p: float) -> list[tuple[float, float]]:
    """Der Anfang einer Linie bis zum Anteil p (0–1) ihrer Länge – für „Linie zeichnet sich“."""
    if p >= 1:
        return list(pts)
    if p <= 0 or len(pts) < 2:
        return []
    lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    goal, out = sum(lens) * p, [pts[0]]
    for i, seg in enumerate(lens):
        if goal >= seg:
            out.append(pts[i + 1])
            goal -= seg
            continue
        f = goal / seg if seg else 0
        out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f))
        break
    return out


# --------------------------------------------------------------------------- Satz Wort für Wort

def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def align_tokens(text: str, words: list[dict]) -> list[float]:
    """Startzeit je Wort des Anzeigetextes (an Leerzeichen getrennt) aus den Wortzeiten der Stimme."""
    tokens = text.split()
    if not tokens:
        return []
    if not words:
        return [0.0] * len(tokens)
    if len(tokens) == len(words):
        return [float(w["start"]) for w in words]
    starts, pos = [], 0
    for w in words:                               # Zeichenposition jedes gesprochenen Worts im Text
        idx = text.find(w["text"], pos)
        if idx < 0:
            starts.append(None)
        else:
            starts.append(idx)
            pos = idx + len(w["text"])
    out, pos, last = [], 0, 0
    for tok in tokens:
        cpos = text.find(tok, pos)
        pos = (cpos + len(tok)) if cpos >= 0 else pos
        best = None
        for w, s in zip(words, starts):
            if s is not None and cpos >= 0 and s <= cpos + max(0, len(tok) - 1):
                best = w
        if best is None:
            best = words[min(last, len(words) - 1)]
        last = words.index(best)
        out.append(float(best["start"]))
    for i in range(1, len(out)):                  # nie rückwärts
        out[i] = max(out[i], out[i - 1])
    return out


class Sentence:
    """Satz oben, zentriert; der Zeilenumbruch steht für den ganzen Satz fest, die Wörter blenden zur Stimme ein."""

    SIZE, LINE, MAX_W = 61, 76, 920

    def __init__(self, text: str, words: list[dict], offset: float, bold: list[str] | None = None, size: int | None = None,
                 max_h: int | None = None):
        size = size or self.SIZE
        self.offset, self.text, self.words, self.bold = offset, text, words, bold
        self._build(size)
        while max_h and self.height > max_h and size > 36:      # langer Text: Schrift kleiner statt zu viele Zeilen
            size -= 4
            self._build(size)

    def _build(self, size: int) -> None:
        text, bold = self.text, self.bold
        words = self.words
        self.regular, self.strong = mfont("serif_m", size), mfont("bolditalic", size)
        keys = {_norm(w) for phrase in (bold or []) for w in str(phrase).split()}
        self.tokens = text.split()
        self.starts = align_tokens(text, words)
        space = self.regular.getlength(" ")
        fonts = [self.strong if _norm(tok) in keys else self.regular for tok in self.tokens]
        widths = [f.getlength(tok) for f, tok in zip(fonts, self.tokens)]
        lines, cur, cur_w = [], [], 0.0
        for i, w in enumerate(widths):
            if cur and cur_w + space + w > self.MAX_W:
                lines.append(cur)
                cur, cur_w = [], 0.0
            cur_w += (space if cur else 0) + w
            cur.append(i)
        if cur:
            lines.append(cur)
        self.line_h = int(size * 1.25)
        self.layers: list[tuple[Image.Image, float, float]] = []
        for li, idxs in enumerate(lines):
            total = sum(widths[i] for i in idxs) + space * (len(idxs) - 1)
            x = (W - total) / 2
            for i in idxs:
                self.layers.append((self._render(self.tokens[i], fonts[i]), x - 10, li * self.line_h - 8))
                x += widths[i] + space
        self.height = len(lines) * self.line_h

    @staticmethod
    def _render(tok: str, fnt: ImageFont.FreeTypeFont) -> Image.Image:
        w, (asc, desc) = int(fnt.getlength(tok)) + 20, fnt.getmetrics()
        mask = Image.new("L", (w, asc + desc + 16), 0)
        ImageDraw.Draw(mask).text((10, 8), tok, font=fnt, fill=255)
        halo = mask.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.28))
        out = Image.new("RGBA", mask.size, (*INK, 0))
        out.putalpha(ImageChops.add(mask, halo))
        return out

    def draw(self, f: Image.Image, t: float, y: float, fade: float = 1.0) -> None:
        ts = t - self.offset
        for (layer, x, dy), start in zip(self.layers, self.starts):
            a = ease_in_out(clamp((ts - start + 0.06) / 0.32))
            if a > 0:
                paste(f, layer, (x, y + dy + (1 - a) * 7), opacity=a * fade)


# --------------------------------------------------------------------------- Pillen und Beschriftungen

def spaced(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, tracking: float) -> float:
    """Text mit Buchstabenabstand zeichnen (linke Kante x, Grundlinie y); gibt die Breite zurück."""
    x = xy[0]
    for ch in text:
        draw.text((x, xy[1]), ch, font=font, fill=fill, anchor="ls")
        x += font.getlength(ch) + tracking
    return x - xy[0] - tracking


def spaced_width(text: str, font, tracking: float) -> float:
    return sum(font.getlength(c) + tracking for c in text) - tracking


@functools.lru_cache(maxsize=32)
def caps_layer(text: str, size: int = 21, tracking: float = 5.0, underline: bool = False, alpha: int = 170) -> Image.Image:
    """Kleine Beschriftung in gesperrten Großbuchstaben (optional mit feiner Linie darunter)."""
    fnt = mfont("sans", size)
    txt = text.upper()
    w = int(spaced_width(txt, fnt, tracking)) + 12
    img = Image.new("RGBA", (w, size + 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    spaced(d, (6, size + 2), txt, fnt, (*INK_DIM, alpha), tracking)
    if underline:
        d.line((w / 2 - 34, size + 22, w / 2 + 34, size + 22), fill=(*INK_FAINT, 200), width=2)
    return img


@functools.lru_cache(maxsize=32)
def chapter_pill(text: str) -> Image.Image:
    """Kapitel-Pille: kleiner Sans-Text in dunkler, abgerundeter Box."""
    fnt = mfont("sans", 21)
    w = int(fnt.getlength(text)) + 40
    scale = 3
    box = Image.new("RGBA", (w * scale, 44 * scale), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((0, 0, w * scale - 1, 44 * scale - 1), 22 * scale, fill=(38, 37, 36, 255),
                                          outline=(64, 62, 58, 255), width=scale)
    img = box.resize((w, 44), Image.LANCZOS)
    ImageDraw.Draw(img).text((20, 30), text, font=fnt, fill=(*INK, 215), anchor="ls")
    return img


@functools.lru_cache(maxsize=16)
def source_pill(text: str) -> Image.Image:
    """Quellen-Pille mit Punkt: „• SAHIH AL-BUCHARI · 1162“."""
    fnt, tracking = mfont("sans", 20), 3.2
    txt = text.upper()
    w = int(spaced_width(txt, fnt, tracking)) + 76
    scale = 3
    box = Image.new("RGBA", (w * scale, 52 * scale), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((0, 0, w * scale - 1, 52 * scale - 1), 26 * scale, fill=(34, 33, 31, 255),
                                          outline=(60, 58, 54, 255), width=scale)
    img = box.resize((w, 52), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    d.ellipse((24, 22, 31, 29), fill=(*INK, 230))
    spaced(d, (44, 33), txt, fnt, (*INK, 225), tracking)
    return img


def small_text(text: str, kind: str, size: int, color=INK_DIM, alpha: int = 255, max_w: int = 900) -> Image.Image:
    fnt = mfont(kind, size)
    from .theme import wrap
    lines = wrap(text, fnt, max_w)
    w = int(max(fnt.getlength(l) for l in lines)) + 16
    line_h = int(size * 1.3)
    img = Image.new("RGBA", (w, line_h * len(lines) + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((w / 2, 8 + size + i * line_h - 4), line, font=fnt, fill=(*color, alpha), anchor="ms")
    return img


# --------------------------------------------------------------------------- Zusammensetzen

def fade_in_out(t: float, duration: float, fade_in: float = 0.5, fade_out: float = 0.6) -> float:
    """Deckkraft für weiche Überblendungen am Szenenanfang und -ende."""
    return clamp(t / fade_in) * clamp((duration - t) / fade_out)


def blur_in(layer: Image.Image, p: float, radius: float = 9.0) -> Image.Image:
    """Einblenden aus der Unschärfe (Zitat-Karte): p 0→1."""
    if p >= 0.999:
        return layer
    out = layer.filter(ImageFilter.GaussianBlur(radius * (1 - p)))
    out.putalpha(out.getchannel("A").point(lambda a: int(a * p)))
    return out
