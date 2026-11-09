"""Szene „Reportage“ (Nachrichten-/Doku-Look) im Buchlook: oben echtes Bild oder Clip mit ruhiger Ken-Burns-Bewegung,
Bauchbinde (Ort · Datum), Quellen-Badge, optional Karten-Einschub und Zeitstrahl; darunter der Satz Wort für Wort
(mind. 54 px). Gibt es kein Bild, zeigt die Szene eine neutrale Grafik (Karte, großes Datum oder Zitat-Karte) –
der Bildbereich ist nie leer. Keine reißerischen Effekte: nur Einblenden und langsames Gleiten.

Szenen-Daten (`szene["visual"]`, geschrieben von `reportage/bilder.py`):
  bild: Pfad | None, bild_art: "image"|"video", credit: Kurzvermerk, karte: Pfad | None, ort, datum, jahr (int),
  jahre: alle Jahre des Videos (Zeitstrahl), quelle: „NASA · Wikipedia“, zitat: Beleg-Zitat (Zitat-Karte).
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import manuskript as M
from .clipreel import ClipReel
from .scenes import Scene
from .theme import H, W, clamp, cover_crop, ease_in_out, ease_out_cubic, paste, progress

MEDIA_H = 1000                  # Höhe des Bildbereichs (oben, volle Breite)
TEXT_Y = 1110                   # Oberkante des Satzes
TEXT_SIZE, TEXT_MIN = 58, 54    # Haupttext: nie kleiner als 54 px
TEXT_MAX_H = 540                # bis ca. 1650 – darunter liegt die Bedienleiste der Plattformen
BG_END = (20, 19, 17)           # Farbe, in die der Bildbereich unten ausblendet
ZOOM = 0.10                     # Ken Burns: 10 % Zoom über die ganze Szene
BAND_Y = 800                    # Oberkante der Bauchbinde


def _gradient(size: tuple[int, int]) -> Image.Image:
    """Abdunkelung unten (Lesbarkeit der Bauchbinde) und weiches Ausblenden in den Grund."""
    w, h = size
    g = Image.new("RGBA", size, (0, 0, 0, 0))
    px = g.load()
    for y in range(h):
        dark = clamp((y - h * 0.45) / (h * 0.5)) ** 1.4 * 150
        fade = clamp((y - (h - 150)) / 150)
        a = dark + (255 - dark) * fade
        color = tuple(int(c * fade) for c in BG_END)
        for x in range(0, w, 1):
            px[x, y] = (*color, int(a))
    return g


_GRAD: dict = {}


def gradient() -> Image.Image:
    if "g" not in _GRAD:                                     # eine Spalte rechnen, dann auf die Breite dehnen
        col = _gradient((1, MEDIA_H))
        _GRAD["g"] = col.resize((W, MEDIA_H), Image.NEAREST)
    return _GRAD["g"]


def band_layer(text: str) -> Image.Image:
    """Bauchbinde: dunkle Platte mit hellem Streifen links, „Ort · Datum“ in der Serifenschrift."""
    fnt = M.mfont("serif_m", 46)
    width = min(W - 80, int(fnt.getlength(text)) + 110)
    while fnt.getlength(text) > width - 110 and fnt.size > 34:
        fnt = M.mfont("serif_m", fnt.size - 2)
    img = Image.new("RGBA", (width, 92), (14, 14, 13, 224))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 7, 92), fill=(*M.INK, 255))
    d.text((38, 62), text, font=fnt, fill=(*M.INK, 255), anchor="ls")
    return img


def timeline_layer(years: list[int], now: int) -> Image.Image:
    """Zeitstrahl über die Jahre des Videos; das Jahr des Satzes ist hervorgehoben."""
    img = Image.new("RGBA", (900, 74), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lo, hi = min(years), max(years)
    span = max(1, hi - lo)
    xs = {y: 30 + (900 - 60) * (y - lo) / span for y in years}
    d.line((30, 26, 870, 26), fill=(*M.INK_FAINT, 255), width=3)
    d.line((30, 26, xs[now], 26), fill=(*M.INK, 255), width=3)
    small, big = M.mfont("sans", 22), M.mfont("sans", 28)
    last_right = -999.0
    for y in sorted(xs):
        on = y == now
        x = xs[y]
        d.ellipse((x - (9 if on else 5), 26 - (9 if on else 5), x + (9 if on else 5), 26 + (9 if on else 5)),
                  fill=(*M.INK, 255) if on else (*M.INK_DIM, 255))
        label, fnt = str(y), big if on else small
        half = fnt.getlength(label) / 2
        if on or x - half > last_right + 12:
            d.text((x, 68), label, font=fnt, fill=(*M.INK, 255) if on else (*M.INK_DIM, 255), anchor="ms")
            last_right = x + half
    return img


def map_layer(path: str, size: int) -> Image.Image | None:
    try:
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    except Exception:                                      # noqa: BLE001
        return None
    img = cover_crop(img, (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), 22, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    ImageDraw.Draw(out).rounded_rectangle((1, 1, size - 2, size - 2), 22, outline=(*M.INK, 130), width=2)
    return out


def quote_layer(text: str) -> Image.Image:
    """Zitat-Karte (kein Bild, keine Karte, kein Datum): der belegte Wortlaut der Quelle, ruhig gesetzt."""
    body = M.small_text("„" + text.strip().rstrip(".") + "“", "italic", 54, M.INK, 255, 860)
    mark = M.mfont("serif", 220)
    img = Image.new("RGBA", (900, body.height + 190), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((450, 190), "“", font=mark, fill=(*M.INK_FAINT, 255), anchor="ms")
    img.alpha_composite(body, ((900 - body.width) // 2, 150))
    return img


class ReportageScene(Scene):
    """Eine Szene der Reportage (Job-Art „reportage“, gebaut in `erklaer/render.py`)."""

    def __init__(self, job):
        self.job = job
        sz = job["szene"]
        v = self.visual = sz.get("visual") or {}
        self.pill = M.chapter_pill(sz["kapitel"]) if sz.get("kapitel") else None
        self.badge = M.source_pill(v["quelle"]) if v.get("quelle") and not sz.get("kapitel") else None
        self.sentence = M.Sentence(sz["text"], job["words"], job["lead"], bold=sz.get("betont") or [], size=TEXT_SIZE,
                                   max_h=TEXT_MAX_H, min_size=TEXT_MIN)
        self.photo, self.reel = None, None
        path = v.get("bild")
        if path and v.get("bild_art") == "video":
            try:
                self.reel = ClipReel([{"path": path, "kind": "video", "duration": v.get("dauer") or 0}],
                                     (W, MEDIA_H), job["duration"], job["fps"])
            except Exception:                              # noqa: BLE001
                self.reel = None
        elif path:
            try:
                img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
                self.photo = cover_crop(img, (int(W * (1 + ZOOM + 0.03)), int(MEDIA_H * (1 + ZOOM + 0.03))))
            except Exception:                              # noqa: BLE001
                self.photo = None
        has_media = self.photo is not None or self.reel is not None
        self.has_media = has_media
        place = " · ".join(x for x in (v.get("ort"), v.get("datum")) if x)
        self.band = band_layer(place) if place and has_media else None
        self.credit = M.small_text(v["credit"], "sans", 20, M.INK, 190, 520) if v.get("credit") and has_media else None
        self.map = map_layer(v["karte"], 250 if has_media else 700) if v.get("karte") else None
        years = sorted(set(v.get("jahre") or []))
        self.timeline = timeline_layer(years, v["jahr"]) if len(years) >= 2 and v.get("jahr") in years else None
        self.big_date = None
        self.quote = None
        if not has_media and self.map is None:
            if v.get("datum"):
                self.big_date = self._big_date(v["datum"])
            elif v.get("zitat"):
                self.quote = quote_layer(v["zitat"])
            else:                                          # nie leer: der Ort/Titel als ruhige Karte
                self.quote = quote_layer(sz["text"])
        self.grad = gradient()
        self.panel = Image.new("RGBA", (W - 96, MEDIA_H - 190), (0, 0, 0, 0))     # ruhige helle Fläche statt leerem Schwarz
        ImageDraw.Draw(self.panel).rounded_rectangle((0, 0, W - 97, MEDIA_H - 191), 28, fill=(54, 52, 47, 255),
                                                     outline=(*M.INK_FAINT, 255), width=2)

    @staticmethod
    def _big_date(text: str) -> Image.Image:
        size = 190
        fnt = M.mfont("italic", size)
        while fnt.getlength(text) > 900 and size > 70:
            size -= 8
            fnt = M.mfont("italic", size)
        w = int(fnt.getlength(text)) + 40
        img = Image.new("RGBA", (w, size + 70), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((w / 2, size), text, font=fnt, fill=(*M.INK, 255), anchor="ms")
        d.line((w / 2 - 60, size + 34, w / 2 + 60, size + 34), fill=(*M.INK_FAINT, 255), width=3)
        return img

    # ------------------------------------------------------------------ Bild

    def media(self, t: float) -> Image.Image | None:
        dur = max(1.0, self.job["duration"])
        if self.reel is not None:
            img = self.reel.frame_at(t)
            return img.convert("RGBA") if img is not None else None
        if self.photo is None:
            return None
        p = clamp(t / dur)                                    # gleichmäßig: nie ein Standbild ohne Bewegung
        zoom = 1.0 + ZOOM * p
        bw, bh = self.photo.size
        w, h = bw / zoom, bh / zoom
        x = (bw - w) * (0.5 + 0.35 * (p - 0.5) * (1 if self.job["index"] % 2 == 0 else -1))
        y = (bh - h) * 0.4
        return self.photo.resize((W, MEDIA_H), Image.BILINEAR, box=(x, y, x + w, y + h)).convert("RGBA")

    def frame(self, t):
        f = M.background(t)
        dur = self.job["duration"]
        fade = M.fade_in_out(t, dur, 0.4, 0.45)
        v = self.visual
        pic = self.media(t)
        if pic is not None:
            pic.alpha_composite(self.grad)
            paste(f, pic, (0, 0), opacity=fade)
            if self.band is not None:
                pb = ease_out_cubic(progress(t, 0.45, 0.6))
                paste(f, self.band, (-(1 - pb) * self.band.width * 0.4, BAND_Y), opacity=fade * pb)
            if self.credit is not None:
                paste(f, self.credit, (W - self.credit.width - 40, MEDIA_H - self.credit.height - 8), opacity=fade * 0.8)
            if self.map is not None:
                pm = ease_out_cubic(progress(t, 0.7, 0.6))
                paste(f, self.map, (W - self.map.width - 48, 170 + (1 - pm) * -16), opacity=fade * pm)
        else:
            self._neutral(f, t, fade)
        if self.pill is not None:
            paste(f, self.pill, (48, 160), opacity=fade)
        elif self.badge is not None:
            paste(f, self.badge, (48, 160), opacity=fade * progress(t, 0.15, 0.5))
        if self.timeline is not None:
            paste(f, self.timeline, ((W - 900) / 2, MEDIA_H + 6), opacity=fade * progress(t, 0.5, 0.6))
        self.sentence.draw(f, t, TEXT_Y + (28 if self.timeline is not None else 0), fade)
        return f

    def _neutral(self, f: Image.Image, t: float, fade: float) -> None:
        """Kein Foto/Clip: Karte, großes Datum oder Zitat – ruhig eingeblendet, nie ein leerer Bildbereich."""
        v = self.visual
        p = ease_out_cubic(progress(t, 0.2, 0.8))
        paste(f, self.panel, (48, 150), opacity=fade)
        if self.map is not None:
            paste(f, self.map, ((W - self.map.width) / 2, 230 + (1 - p) * 14), opacity=fade * p)
            label = " · ".join(x for x in (v.get("ort"), v.get("datum")) if x)
            if label:
                lay = M.small_text(label, "serif_m", 46, M.INK, 255, 900)
                paste(f, lay, ((W - lay.width) / 2, 230 + self.map.height + 24), opacity=fade * progress(t, 0.6, 0.6))
        elif self.big_date is not None:
            paste(f, self.big_date, ((W - self.big_date.width) / 2, 380 + (1 - p) * 14), opacity=fade * p)
            if v.get("ort"):
                lay = M.small_text(v["ort"], "sans", 28, M.INK_DIM, 255, 800)
                paste(f, lay, ((W - lay.width) / 2, 380 + self.big_date.height + 24), opacity=fade * progress(t, 0.6, 0.6))
        elif self.quote is not None:
            paste(f, M.blur_in(self.quote, p), ((W - self.quote.width) / 2, 250), opacity=fade)
