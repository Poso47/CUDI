"""Schaubild rendern: EIN Renderer, der Look und Bewegung aus dem Stil-Katalog (`data/bildstile.json`) liest.

Je Szene: Hintergrund (zwei Farben im Wechsel + Effekt des Stils), ein Bild im Rahmen (KI-Illustration oder – Stil-Modus
„code“ – vom Renderer gezeichnet), Etiketten mit Führungslinie, Riesenzahl oder Titel, Untertitel (1–3 Wörter, wortgenau,
Schlüsselwort farbig), Fortschritt „3/7“, Kennzeichnung „KI-Illustration“. Zwei Seitenformate: 9:16 und 16:9 – das Layout
kommt aus `geo()`. Bewegung ist Zoom/Schwenk/Parallaxe/Ruckeln; animierte Figuren gibt es nicht. Kein Eingriff in `render/*`.
"""

from __future__ import annotations

import functools
import hashlib
import math
import subprocess
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .. import config, tts
from ..render import audio, theme as T, video
from ..render.manuskript import align_tokens
from . import sfx

LEAD, TAIL = 0.45, 0.55
FONTS = {"anton": "Anton-Regular.ttf", "archivo": "ArchivoBlack-Regular.ttf", "serif": "PlayfairDisplay-Black.ttf",
         "pop": "Poppins-ExtraBold.ttf", "popb": "Poppins-Bold.ttf", "sans": "Inter-SemiBold.ttf", "hand": "Caveat-Bold.ttf",
         "garamond": "EBGaramond-Medium.ttf"}
KI_LABEL = {"de": "KI-Illustration", "en": "AI illustration"}
CODE_LABEL = {"de": "Grafik", "en": "Graphic"}


@functools.lru_cache(maxsize=128)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    path = T._font_index().get(FONTS.get(kind, FONTS["sans"]).lower())
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def ease(x: float) -> float:
    return 1 - (1 - clamp(x)) ** 3


def pop(x: float) -> float:
    x = clamp(x)
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2 if x < 1 else 1.0


def _h(key: str, n: int = 1000) -> int:
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) % n


def geo(fmt: str) -> dict:
    """Layout aus dem Seitenformat. Alle Inhalte liegen in der Safe-Zone (9:16: y 170–1500 wegen der Plattform-Leisten)."""
    if fmt == "16:9":
        w, h = 1920, 1080
        return {"W": w, "H": h, "cap": (int(.25 * w), int(.17 * h), int(.42 * w), 64), "row": (int(.25 * w), int(.47 * h), int(.42 * w)),
                "img": (int(.70 * w), int(.50 * h), int(.36 * h)), "prog": (int(.25 * w), int(.86 * h)), "ki": (44, h - 62),
                "xlim": (int(.49 * w), w - 24), "safe": (40, 24, w - 24, h - 24)}
    w, h = 1080, 1920
    return {"W": w, "H": h, "cap": (w // 2, 214, int(.88 * w), 88), "row": (w // 2, 452, int(.84 * w)),
            "img": (w // 2, 1000, 420), "prog": (w // 2, 1458), "ki": (44, 1446), "xlim": (28, w - 28),
            "safe": (28, 170, w - 28, 1500)}


def paste(f: Image.Image, layer: Image.Image, xy, opacity: float = 1.0) -> None:
    if opacity <= 0.003:
        return
    mask = layer.getchannel("A")
    if opacity < 0.997:
        mask = mask.point(lambda v: int(v * opacity))
    f.paste(layer, (int(xy[0]), int(xy[1])), mask)


def fit_text(text: str, kind: str, size: int, max_w: int, min_size: int = 26) -> ImageFont.FreeTypeFont:
    fnt = font(kind, size)
    while fnt.getlength(text) > max_w and size > min_size:
        size -= 4
        fnt = font(kind, size)
    return fnt


def text_layer(text: str, fnt, color, stroke: int = 0, stroke_color=(0, 0, 0)) -> Image.Image:
    box = fnt.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (box[2] - box[0] + 8, box[3] - box[1] + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - box[0], 4 - box[1]), text, font=fnt, fill=tuple(color), stroke_width=stroke, stroke_fill=stroke_color)
    return im


# --------------------------------------------------------------------------- Etiketten

def label_slots(g: dict, sizes: list[tuple[int, int]]) -> list[dict]:
    """Platz je Etikett rund um das Bild: (x, y) der Pille und Zielpunkt der Führungslinie. Liegt in der Safe-Zone,
    die Pillen überlappen sich nicht (verschiedene Höhen). Die Linie endet am RAND des Bildes: Sie ordnet den Begriff dem
    Bild zu, behauptet aber nicht, eine bestimmte Stelle einer KI-Illustration sei genau dieses Teil."""
    cx, cy, h = g["img"]
    lo, hi = g["xlim"]
    plan = [("l", cy - h - 6, (cx - .70 * h, cy - .70 * h)), ("r", cy + h - 96, (cx + .70 * h, cy + .70 * h)),
            ("l", cy + .30 * h, (cx - .93 * h, cy + .36 * h))]
    out = []
    for (side, y, target), (w, hgt) in zip(plan, sizes):
        x = max(lo, cx - h - 34) if side == "l" else min(hi - w, cx + h + 34 - w)
        x = max(lo, min(hi - w, x))
        y = max(g["safe"][1], min(g["safe"][3] - hgt, y))
        out.append({"x": int(x), "y": int(y), "w": w, "h": hgt, "ziel": (int(target[0]), int(target[1])), "seite": side})
    return out


def label_image(text: str, stil: dict, dark_bg: bool) -> Image.Image:
    form, ak = stil["etikett"], tuple(stil["akzent"])
    fnt = font(stil["schrift"][1] if stil["schrift"][1] != "anton" else "popb", 34)
    tw = int(fnt.getlength(text))
    w, h = tw + 74, 62
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if form == "kasten":
        d.rectangle((6, 6, w + 6, h + 6), fill=(0, 0, 0, 255))
        d.rectangle((0, 0, w, h), fill=(255, 255, 255, 255), outline=(20, 20, 24, 255), width=4)
        fg = (20, 20, 24)
    elif form == "sprechblase":
        d.rounded_rectangle((0, 0, w, h), radius=26, fill=(255, 255, 255, 255), outline=(20, 20, 24, 255), width=5)
        fg = (20, 20, 24)
    elif form == "neon":
        d.rounded_rectangle((0, 0, w, h), radius=10, fill=(8, 8, 20, 235), outline=ak + (255,), width=3)
        fg = ak
    else:                                                     # Pille: hell auf dunklem Grund, dunkel auf hellem
        fill, fg = ((250, 248, 240, 255), (20, 36, 44)) if dark_bg else ((16, 44, 56, 255), (250, 248, 240))
        d.rounded_rectangle((0, 0, w, h), radius=h // 2, fill=fill)
    d.ellipse((22, h // 2 - 7, 36, h // 2 + 7), fill=ak + (255,))
    d.text((50, h // 2), text, font=fnt, fill=fg, anchor="lm")
    return im


# --------------------------------------------------------------------------- Hintergrund und Rahmen

def background(stil: dict, g: dict, idx: int) -> Image.Image:
    w, h = g["W"], g["H"]
    col = tuple(stil["bg"][idx % 2])
    ak = tuple(stil["akzent"])
    im = Image.new("RGB", (w, h), col)
    eff = stil["effekt"]
    d = ImageDraw.Draw(im, "RGBA")
    dark = sum(col) < 380
    if eff in ("partikel", "nebel", "neon", "verlauf", "liquid") or dark:                 # weiche Vignette gibt Tiefe
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot((xx - g["img"][0]) / w, (yy - g["img"][1]) / h)
        k = np.clip(1.08 - r * (0.9 if dark else 0.35), 0.55, 1.12)[..., None]
        im = Image.fromarray(np.clip(np.asarray(im, dtype=np.float32) * k, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im, "RGBA")
    if eff == "halftone":
        for y in range(0, h, 30):
            for x in range((y // 30 % 2) * 15, w, 30):
                d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(0, 0, 0, 30))
    elif eff == "raster":
        for i in range(-h, w + h, 80):
            d.line((i, 0, i + h // 2, h), fill=(128, 128, 128, 34), width=2)
            d.line((i, h, i + h // 2, 0), fill=(128, 128, 128, 34), width=2)
    elif eff == "neon":
        for y in range(0, h, 6):
            d.line((0, y, w, y), fill=(255, 255, 255, 9))
        d.line((0, int(g["img"][1] + g["img"][2] * 1.25), w, int(g["img"][1] + g["img"][2] * 1.25)), fill=ak + (120,), width=3)
    if eff in ("korn", "papier"):
        rng = np.random.default_rng(7)
        noise = rng.normal(0, 9 if eff == "korn" else 5, (h, w, 1))
        im = Image.fromarray(np.clip(np.asarray(im, dtype=np.float32) + noise, 0, 255).astype(np.uint8))
    return im


def frame_mask(form: str, size: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    if form == "kreis":
        d.ellipse((0, 0, size - 1, size - 1), fill=255)
    elif form in ("panel", "polaroid"):
        d.rectangle((0, 0, size - 1, size - 1), fill=255)
    elif form == "frei":
        d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 9, fill=255)
        m = m.filter(ImageFilter.GaussianBlur(size // 40))
        d = ImageDraw.Draw(m)
        d.rounded_rectangle((size // 28, size // 28, size - size // 28, size - size // 28), radius=size // 10, fill=255)
    else:
        d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 14, fill=255)
    return m


def frame_overlay(stil: dict, size: int, dark_bg: bool) -> Image.Image:
    """Rand über dem Bild (Ring, Karte, Panel, Polaroid, Neon)."""
    form, ak = stil["rahmen"], tuple(stil["akzent"])
    pad = 40
    im = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box = (pad, pad, pad + size - 1, pad + size - 1)
    if form == "kreis":
        d.ellipse(box, outline=ak + (255,), width=6)
        d.ellipse((pad - 16, pad - 16, pad + size + 15, pad + size + 15), outline=ak + (90,), width=2)
    elif form == "karte":
        d.rounded_rectangle(box, radius=size // 14, outline=((250, 248, 240, 255) if dark_bg else (20, 24, 30, 255)), width=7)
    elif form == "panel":
        d.rectangle(box, outline=(16, 16, 20, 255), width=12)
    elif form == "polaroid":
        d.rectangle((pad - 22, pad - 22, pad + size + 21, pad + size + 34), outline=(250, 248, 242, 255), width=24)
    if stil["effekt"] == "neon":
        glow = im.filter(ImageFilter.GaussianBlur(12))
        glow.alpha_composite(im)
        im = glow
    return im


def shadow(size: int) -> Image.Image:
    im = Image.new("RGBA", (size + 160, size + 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((80, 96, 80 + size, 96 + size), radius=size // 8, fill=(0, 0, 0, 120))
    return im.filter(ImageFilter.GaussianBlur(34))


# --------------------------------------------------------------------------- vom Renderer gezeichnete Bilder (Modus „code“)

def code_visual(art: str, size: int, p: float, t: float, ink, ak, seed: int, word: str, schrift: str) -> Image.Image:
    """Bild ohne KI: Formen (motiongraphics), Linien (linien) oder das Schlüsselwort selbst (typografie)."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, ink, ak = size / 2, tuple(ink), tuple(ak)
    if art == "typografie":
        fnt = fit_text(word.upper(), schrift, int(size * .34), int(size * .96), 40)
        n = max(1, len(word))
        x = (size - fnt.getlength(word.upper())) / 2
        for i, ch in enumerate(word.upper()):
            a = ease((p * 3.2 - i / n) * 2.0)
            if a > 0:
                d.text((x, c - (1 - a) * 60), ch, font=fnt, fill=(ak if i == 0 else ink) + (int(255 * a),), anchor="lm")
            x += fnt.getlength(ch)
        d.rectangle((size * .08, c + size * .24, size * .08 + size * .84 * ease(p * 2), c + size * .24 + 10), fill=ak + (255,))
        return im
    if art == "linien":
        pts = []
        turns, steps = 2.6 + seed % 3 * .4, 220
        for i in range(steps):
            a = i / steps * turns * 2 * math.pi
            r = size * (.08 + .34 * i / steps)
            pts.append((c + r * math.cos(a + seed), c + r * math.sin(a + seed) * .82))
        k = max(2, int(len(pts) * ease(p * 1.6)))
        d.line(pts[:k], fill=ink + (255,), width=5, joint="curve")
        x, y = pts[k - 1]
        d.ellipse((x - 12, y - 12, x + 12, y + 12), fill=ak + (255,))
        for j in range(3):
            q = ease(p * 1.6 - .25 - j * .18)
            if q > 0:
                yy = size * (.80 + j * .055)
                d.line((size * .22, yy, size * .22 + size * .56 * q * (1 - j * .22), yy), fill=ink + (150,), width=4)
        return im
    # motiongraphics: Ring, Balken, drehendes Quadrat
    r = size * .36
    d.arc((c - r, c - r, c + r, c + r), -90, -90 + 360 * ease(p * 1.4), fill=ak + (255,), width=22)
    d.arc((c - r - 34, c - r - 34, c + r + 34, c + r + 34), 40 + t * 30, 150 + t * 30, fill=ink + (120,), width=5)
    for j in range(4):
        q = ease(p * 2 - j * .16)
        hgt = size * (.10 + .07 * ((seed + j * 3) % 4)) * q
        x = c - size * .17 + j * size * .095
        d.rounded_rectangle((x, c + size * .14 - hgt, x + size * .06, c + size * .14), radius=8, fill=(ink if j % 2 else ak) + (255,))
    a = t * .7 + seed
    sq = [(c + size * .43 * math.cos(a + k * math.pi / 2), c + size * .43 * math.sin(a + k * math.pi / 2)) for k in range(4)]
    d.line(sq + [sq[0]], fill=ink + (70,), width=4)
    return im


# --------------------------------------------------------------------------- Untertitel

class Captions:
    """1–3 Wörter gleichzeitig, wortgenau zur Stimme; das Schlüsselwort (Zahl oder längstes Wort) in Akzentfarbe."""

    def __init__(self, text: str, words: list[dict], lead: float, stil: dict, g: dict, ink):
        self.lead, self.ink, self.ak = lead, tuple(ink), tuple(stil["akzent"])
        self.cx, self.y, self.max_w, self.size = g["cap"]
        self.kind = stil["schrift"][0]
        tokens, starts = text.split(), align_tokens(text, words)
        self.chunks, cur = [], []
        for tok, st in zip(tokens, starts):
            if cur and (len(cur) >= 3 or sum(len(c[0]) for c in cur) + len(tok) > 19 or cur[-1][0][-1:] in ".!?:"):
                self.chunks.append(cur)
                cur = []
            cur.append((tok, st))
        if cur:
            self.chunks.append(cur)
        self._cache: dict[int, list] = {}

    def _layers(self, i: int) -> list:
        if i not in self._cache:
            chunk = self.chunks[i]
            line = " ".join(c[0] for c in chunk)
            fnt = fit_text(line, self.kind, self.size, self.max_w, 34)
            key = max(range(len(chunk)), key=lambda k: (any(ch.isdigit() for ch in chunk[k][0]), len(chunk[k][0])))
            if not any(ch.isdigit() for ch in chunk[key][0]) and len(chunk[key][0].strip(".,!?:;")) < 6:
                key = -1
            x, space, out = self.cx - fnt.getlength(line) / 2, fnt.getlength(" "), []
            asc = fnt.getbbox("Ag")[1]
            for k, (tok, st) in enumerate(chunk):
                box = fnt.getbbox(tok)
                im = Image.new("RGBA", (box[2] - box[0] + 12, int(fnt.size * 1.5)), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((6 - box[0], 4 - asc), tok, font=fnt, fill=self.ak if k == key else self.ink)
                out.append((im, x + box[0] - 6, st))
                x += fnt.getlength(tok) + space
            self._cache = {i: out}
        return self._cache[i]

    def draw(self, f: Image.Image, t: float, fade: float) -> None:
        ts = t - self.lead
        idx = -1
        for i, chunk in enumerate(self.chunks):
            if chunk[0][1] <= ts + 0.06:
                idx = i
        if idx < 0:
            return
        for im, x, st in self._layers(idx):
            a = ease((ts - st + 0.06) / 0.16)
            if a > 0:
                paste(f, im, (x, self.y + (1 - a) * 10), a * fade)


# --------------------------------------------------------------------------- Szene

class Scene:
    def __init__(self, job: dict):
        self.job, self.stil, self.g = job, job["stil"], geo(job["format"])
        g, stil = self.g, self.stil
        self.dur, self.idx = job["duration"], job["index"]
        col = stil["bg"][self.idx % 2]
        self.dark = sum(col) < 380
        self.ink, self.ak = tuple(stil["ink"][self.idx % 2]), tuple(stil["akzent"])
        self.bg = background(stil, g, self.idx)
        self.cx, self.cy, self.h = g["img"]
        self.size = 2 * self.h
        self.mask = frame_mask(stil["rahmen"], self.size)
        self.over = frame_overlay(stil, self.size, self.dark)
        self.shadow = shadow(self.size)
        self.seed = _h(f"{job['id']}-{self.idx}")
        self.pic = None
        if job.get("bild"):
            try:
                with Image.open(job["bild"]) as src:
                    src = src.convert("RGB")
                    w, h = src.size
                    cut = int(h * 0.94) if job.get("ki") else h                 # Logo-Streifen des Bilddienstes abschneiden
                    side = min(w, cut)
                    src = src.crop(((w - side) // 2, (cut - side) // 2, (w - side) // 2 + side, (cut - side) // 2 + side))
                    self.pic = src.resize((int(self.size * 1.16),) * 2, Image.LANCZOS)
            except OSError:
                self.pic = None
        if stil["effekt"] == "aufdecken":
            yy, xx = np.mgrid[0:self.size, 0:self.size]
            self.ramp = ((xx * .7 + yy * .3) / self.size).astype(np.float32)
        self.caps = Captions(job["text"], job["words"], job["lead"], stil, g, self.ink)
        starts = align_tokens(job["text"], job["words"])
        tokens = [t.lower().strip(".,!?:;„“\"") for t in job["text"].split()]

        def when(word: str, default: float) -> float:
            w = word.lower().split()[0] if word.strip() else ""
            for tok, st in zip(tokens, starts):
                if w and (tok.startswith(w[:5]) or w.startswith(tok) and len(tok) > 3):
                    return job["lead"] + st
            return default

        labels = [label_image(t, stil, self.dark) for t in (job.get("etiketten") or [])[:3]]
        slots = label_slots(g, [(im.width, im.height) for im in labels])
        self.labels = [(im, sl, when(txt, job["lead"] + .7 + .8 * i))
                       for i, (im, sl, txt) in enumerate(zip(labels, slots, job.get("etiketten") or []))]
        rx, ry, rw = g["row"]
        self.row = None
        if job.get("zahl"):
            fnt = fit_text(job["zahl"], "archivo" if stil["schrift"][0] in ("sans", "garamond") else stil["schrift"][0], 150, int(rw * .62), 70)
            num = text_layer(job["zahl"], fnt, self.ak)
            unit = text_layer(job.get("einheit") or "", fit_text(job.get("einheit") or " ", stil["schrift"][1], 54, int(rw * .36), 28), self.ink)
            total = num.width + 18 + unit.width
            x0 = rx - total / 2
            digit = "".join(ch for ch in job["zahl"] if ch.isdigit())[:2]
            self.row = [(num, x0, ry - num.height / 2), (unit, x0 + num.width + 18, ry + num.height / 2 - unit.height - 6)]
            self.row_t = when(digit, job["lead"] + .3) if digit else job["lead"] + .3
        elif job.get("kopf"):
            words, lines, cur = job["kopf"].split(), [], ""
            fnt = font(stil["schrift"][0], 74 if len(job["kopf"]) < 34 else 58)
            for wd in words:
                if cur and fnt.getlength(cur + " " + wd) > rw:
                    lines.append(cur)
                    cur = wd
                else:
                    cur = (cur + " " + wd).strip()
            lines.append(cur)
            lines = lines[:3]
            lh = int(fnt.size * 1.16)
            self.row = [(text_layer(ln, fit_text(ln, stil["schrift"][0], fnt.size, rw), self.ink), None, ry - lh * len(lines) / 2 + i * lh)
                        for i, ln in enumerate(lines)]
            self.row = [(im, rx - im.width / 2, y) for im, _, y in self.row]
            self.row_t = 0.15
        px, py = g["prog"]
        self.prog = None
        if job.get("station"):
            self.prog = text_layer(f"{job['station']}/{job['n']}", font("sans", 34), self.ink)
        self.ki = text_layer((KI_LABEL if job.get("ki") else CODE_LABEL)[job["lang"]], font("sans", 26), self.ink)
        rng = np.random.default_rng(self.seed)
        self.dots = rng.random((26, 4))

    def _picture(self, t: float) -> Image.Image:
        stil, size, p = self.stil, self.size, clamp(t / max(self.dur, .1))
        step = stil.get("schritt") or 0
        tq = math.floor(t * step) / step if step else t
        pq = clamp(tq / max(self.dur, .1))
        if self.pic is None:
            art = stil["id"] if stil["modus"] == "code" else "motiongraphics"
            return code_visual(art, size, clamp(t / min(self.dur, 3.2)), t, self.ink, self.ak, self.seed % 7,
                               self.job.get("wort") or "", stil["schrift"][0])
        bew = stil["bewegung"]
        z, dx, dy = 1.0, 0.0, 0.0
        if bew == "zoom":
            z = 1.0 + .13 * p
        elif bew == "schwenk":
            z, dx = 1.12, (p - .5) * .10 * (1 if self.idx % 2 else -1)
        elif bew == "parallax":
            z, dx, dy = 1.05 + .08 * p, (p - .5) * .07, (.5 - p) * .04
        elif bew == "ruckeln":
            z = 1.03 + .09 * pq
            dx, dy = (_h(f"x{self.seed}{tq:.2f}", 9) - 4) / 900, (_h(f"y{self.seed}{tq:.2f}", 9) - 4) / 900
        elif bew == "puls":
            z = 1.06 + .03 * math.sin(t * 2.2)
        s = max(size, int(size * z))
        im = self.pic.resize((s, s), Image.BILINEAR)
        m = (s - size) / 2
        ox, oy = int(clamp(m + dx * s, 0, 2 * m)), int(clamp(m + dy * s, 0, 2 * m))
        im = im.crop((ox, oy, ox + size, oy + size)).convert("RGBA")
        mask = self.mask
        if stil["effekt"] == "aufdecken":                    # Whiteboard: Zeichnung deckt sich diagonal auf
            reveal = np.clip((clamp(t / 1.9) * 1.12 - self.ramp) / .06, 0, 1)
            mask = Image.fromarray((np.asarray(mask, dtype=np.float32) * reveal).astype(np.uint8))
        im.putalpha(mask)
        return im

    def frame(self, t: float) -> Image.Image:
        g, stil, job = self.g, self.stil, self.job
        f = self.bg.copy()
        fade = clamp(min(t / .16, (self.dur - t) / .16))
        d = ImageDraw.Draw(f, "RGBA")
        if stil["effekt"] in ("partikel", "liquid", "verlauf") or (self.dark and stil["effekt"] in ("none", "nebel")):
            big = stil["effekt"] in ("liquid", "verlauf")
            for x0, y0, r0, sp in self.dots[:8 if big else 26]:
                x = (x0 + .02 * math.sin(t * .5 + r0 * 9)) * g["W"]
                y = ((y0 - t * (.012 + sp * .02)) % 1.0) * g["H"]
                r = (60 + r0 * 150) if big else (2 + r0 * 4)
                d.ellipse((x - r, y - r, x + r, y + r), fill=self.ak + ((16 if big else int(40 + r0 * 70)),))
        ap = pop(t / .42)
        jit = 0
        if stil.get("schritt"):
            jit = _h(f"j{self.seed}{math.floor(t * stil['schritt'])}", 5) - 2
        x0, y0 = self.cx - self.h + jit, self.cy - self.h + int((1 - ease(t / .4)) * 26)
        if stil["rahmen"] != "frei" or self.pic is not None:
            paste(f, self.shadow, (x0 - 80, y0 - 80), .55 * fade if self.pic is not None else 0)
        pic = self._picture(t)
        if ap < 1 and self.pic is not None:
            s = max(8, int(self.size * (.9 + .1 * ap)))
            pic = pic.resize((s, s), Image.BILINEAR)
            paste(f, pic, (self.cx - s / 2 + jit, self.cy - s / 2), fade * clamp(t / .2))
        else:
            paste(f, pic, (x0, y0), fade)
        if self.pic is not None:
            paste(f, self.over, (x0 - 40, y0 - 40), fade * clamp(t / .3))
        d = ImageDraw.Draw(f, "RGBA")
        for im, sl, tt in self.labels:                         # Etikett + Führungslinie zum Bildteil
            a = ease((t - tt) / .28)
            if a <= 0:
                continue
            sx = sl["x"] + (sl["w"] - 12 if sl["seite"] == "l" else 12)
            sy = sl["y"] + sl["h"] // 2
            tx, ty = sl["ziel"]
            ex, ey = sx + (tx - sx) * a, sy + (ty - sy) * a
            d.line((sx, sy, ex, ey), fill=self.ak + (int(230 * fade),), width=3)
            d.ellipse((ex - 7, ey - 7, ex + 7, ey + 7), fill=self.ak + (int(255 * fade),))
            paste(f, im, (sl["x"], sl["y"] + (1 - a) * 12), a * fade)
        if self.row:
            a = ease((t - self.row_t) / .3)
            for im, x, y in self.row:
                paste(f, im, (x, y + (1 - a) * 18), a * fade)
        self.caps.draw(f, t, fade)
        px, py = g["prog"]
        if self.prog is not None:
            n, cur = job["n"], job["station"]
            gap = 26
            x = px - (n - 1) * gap / 2
            for i in range(n):
                r = 7 if i + 1 == cur else 4
                d.ellipse((x + i * gap - r, py - r, x + i * gap + r, py + r),
                          fill=(self.ak if i + 1 <= cur else self.ink) + ((255 if i + 1 <= cur else 90),))
            paste(f, self.prog, (px - self.prog.width / 2, py + 14), .8 * fade)
        paste(f, self.ki, g["ki"], .62)                        # Kennzeichnung in JEDEM Bild
        return f


def make_scene(job: dict) -> Scene:
    return Scene(job)


def render_frame(job: dict, t: float, path: Path) -> None:
    make_scene(job).frame(t).convert("RGB").save(path, quality=92)


def render_part(job: dict) -> str:
    scene = make_scene(job)
    g = scene.g
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{g['W']}x{g['H']}", "-r", str(job["fps"]),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-g", str(job["fps"] * 2), job["out"]]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for n in range(job["frames"]):
            proc.stdin.write(scene.frame(n / job["fps"]).convert("RGB").tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg-Fehler bei Szene {job['index']}")
    return job["out"]


# --------------------------------------------------------------------------- Ton

def events(jobs: list[dict]) -> list[tuple[float, str]]:
    """Soundeffekte mit Zeitpunkt: Wusch je Szenenwechsel, Pop je Etikett, Tick je Zahl, Stift beim Whiteboard."""
    out, t = [], 0.0
    for job in jobs:
        scene_labels = len((job.get("etiketten") or [])[:3])
        if job["index"]:
            out.append((max(0.0, t - .08), "wusch"))
        if job["stil"]["effekt"] == "aufdecken" and job.get("bild"):
            out.append((t + .1, "stift"))
        if job.get("zahl"):
            out.append((t + job["lead"] + .3, "tick"))
        for i in range(scene_labels):
            out.append((t + job["lead"] + .7 + .8 * i, "pop"))
        t += job["duration"]
    return out


def build_audio(jobs: list[dict], path: Path, music_style: str | None, seed_key: str) -> list[tuple[float, str]]:
    rate = video.SAMPLE_RATE
    total = int(sum(j["duration"] for j in jobs) * rate) + rate
    track = np.zeros(total, dtype=np.float32)
    t = 0.0
    for job in jobs:
        clip = video._decode(job["voice_path"])
        s = int((t + job["lead"]) * rate)
        track[s:s + len(clip)] += clip[: max(0, total - s)]
        t += job["duration"]
    voice_level = audio.rms(track[np.abs(track) > 0.01]) if np.any(np.abs(track) > 0.01) else 0.1
    used = []
    if sfx.enabled():
        used = events(jobs)
        sfx.place(track, used, voice_level, rate)
    if music_style is not None and audio.enabled():
        music = video._music_track(total)
        if music is None:
            music = audio.generate_music(music_style, total / rate, path.parent, seed_key, video._decode)
        track += audio.mix_music(track, music)
    track = track / (np.abs(track).max() or 1.0) * 0.89
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(track, -1, 1) * 32767).astype(np.int16).tobytes())
    return used


# --------------------------------------------------------------------------- Video

def build_jobs(script: dict, voiced: list, work: Path) -> list[dict]:
    jobs, n = [], sum(1 for s in script["szenen"] if s["typ"] == "station")
    for i, (sz, (wav, words, dur)) in enumerate(zip(script["szenen"], voiced)):
        frames = int(round((LEAD + dur + TAIL) * config.FPS))
        jobs.append({"index": i, "id": script["id"], "typ": sz["typ"], "lang": script["sprache"], "format": script["seitenformat"],
                     "stil": script["stil"], "text": sz["text"], "words": words, "lead": LEAD, "voice_dur": dur, "frames": frames,
                     "duration": frames / config.FPS, "fps": config.FPS, "voice_path": str(wav), "bild": sz.get("bild_datei"),
                     "ki": bool(sz.get("ki")), "zahl": sz.get("zahl") or "", "einheit": sz.get("einheit") or "",
                     "kopf": sz.get("kopf") or "", "wort": sz.get("name") or script["titel"].split()[0],
                     "etiketten": sz.get("etiketten") or [], "station": sz.get("station") or 0, "n": n,
                     "out": str(work / f"part_{i:02d}.mp4")})
    return jobs


def render_schaubild(script: dict, out_dir: Path, progress=None, musik: bool = True) -> dict:
    """Skript (aus `schaubild.baue_skript`) -> fertiges Video + Cover + Produktionsablauf (`ablauf.json`)."""
    import json

    from ..erklaer.render import voice_name
    from ..render import cover as cover_mod

    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    lang = script["sprache"]
    voiced = tts.voice_texts([s["text"] for s in script["szenen"]], work / "audio", voice_name(lang), "+0%", "+0Hz")
    jobs = build_jobs(script, voiced, work)
    done = 0
    with ProcessPoolExecutor(max_workers=config.RENDER_WORKERS) as pool:
        for _ in pool.map(render_part, jobs):
            done += 1
            if progress:
                progress(done / len(jobs))
    concat = work / "parts.txt"
    concat.write_text("".join(f"file '{Path(j['out']).name}'\n" for j in jobs), "utf-8")
    silent = work / "video_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(silent)], check=True)
    cover = out_dir / f"{script['id']}_cover.jpg"
    first = jobs[0]
    render_frame(first, first["duration"] - .4, cover)
    if script["seitenformat"] != "16:9":                      # Cover als erstes Frame – VOR dem Ton (der Stempel gibt nur Bild aus)
        stamped = work / "mit_cover.mp4"
        if cover_mod.stamp_first_frame(silent, cover, stamped):
            silent = stamped
    audio_file = work / "audio.wav"
    used = build_audio(jobs, audio_file, script["stil"]["musik"] if musik else None, script["id"])
    final = out_dir / f"{script['id']}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio_file), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", str(video.SAMPLE_RATE), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    str(final)], check=True)
    from .. import qa

    g = geo(script["seitenformat"])
    old = (config.WIDTH, config.HEIGHT)
    config.WIDTH, config.HEIGHT = g["W"], g["H"]              # Endkontrolle misst gegen das gewählte Seitenformat
    try:
        befund = qa.safe_check(final, "erklaer", config.STORY_MAX_SECONDS)
    finally:
        config.WIDTH, config.HEIGHT = old
    t, ablauf = 0.0, []
    for job, sz in zip(jobs, script["szenen"]):
        ablauf.append({"szene": job["index"], "typ": job["typ"], "start": round(t, 2), "dauer": round(job["duration"], 2),
                       "sprechtext": job["text"], "beleg": sz.get("beleg") or "", "quelle": sz.get("quelle_url") or "",
                       "bild": sz.get("bild_quelle") or "vom Renderer gezeichnet", "bild_prompt": sz.get("bild_prompt") or "",
                       "zahl": (job["zahl"] + " " + job["einheit"]).strip(), "etiketten": job["etiketten"],
                       "bewegung": script["stil"]["bewegung"], "soundeffekte": [name for when, name in used if t <= when < t + job["duration"]]})
        t += job["duration"]
    (out_dir / "ablauf.json").write_text(json.dumps({"titel": script["titel"], "stil": script["stil"]["id"], "seitenformat": script["seitenformat"],
                                                      "aufloesung": f"{g['W']}x{g['H']}", "musik": script["stil"]["musik"] if musik else None,
                                                      "szenen": ablauf}, ensure_ascii=False, indent=1), "utf-8")
    return {"video": final.name, "cover": cover.name, "duration": round(sum(j["duration"] for j in jobs), 1), "qa": befund}
