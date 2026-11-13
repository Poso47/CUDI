"""Video-Formate: jedes Video kann wie ein ganz anderes Video wirken – nicht nur andere Farben.

Ein Format bestimmt den ganzen Bildaufbau aller Szenen (Intro, Plätze, Abschluss): Form der Bildfläche, Lage von
Rang und Text, Kamerabewegung (Zoom, Schwenk), Übergang am Szenenanfang und die Art des Abschlusses. Die Farben
(Design, `theme.STYLES`) kommen unabhängig davon passend zum Thema dazu.

* **karte**    – Bildkarte oben, Text darunter, Rang-Abzeichen an der Ecke (Bewegungsprofile aus `theme.MOTIONS`).
* **vollbild** – Clip/Foto füllt den Bildschirm, Punch-in-Zoom, Text unten auf Schatten.
* **kreis**    – Bild im großen Kreis mit Fortschrittsring (Wert), Rang-Blase; Iris-Blende, Abschluss als Podest.
* **magazin**  – Bild oben mit schräger Kante, riesige Umriss-Ziffer, Farbbalken; Wisch-Übergang wie ein Magazin.
* **polaroid** – Sofortbild fällt mit Drehung herein (Blitz), Stapel dahinter, Klebestreifen; Abschluss als Podest.
* **zahl**     – Der Clip läuft IN der riesigen Rang-Ziffer, die aus dem Bild heraus herangezoomt wird.
* **manuskript** – Buchlook (render/manuskript.py): fast schwarz, Satz oben Wort für Wort zur Stimme, Kapitel-Pille
  („Platz 3“), Bild dezent eingefärbt im Linienrahmen, Quellen-Pille; Grundlage der Erklärvideos (`erklaer/`).
"""

from __future__ import annotations

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import theme as T
from .scenes import IntroScene, ItemScene, OutroScene, header, paste_scaled
from .theme import (
    CONTENT_W, GOLD, H, SUB_Y, W, WHITE, X0, background, clamp, ease_in_out, ease_out_back, ease_out_cubic, fit_font,
    font, gradient_fill, paste, progress, rank_colors, rounded_rect, shadow, text_layer,
)

FORMATS = ["karte", "vollbild", "kreis", "magazin", "polaroid", "zahl", "manuskript"]
DARK = (10, 12, 28)


# --------------------------------------------------------------------------- Hilfen

def circle_mask(d: int) -> Image.Image:
    big = Image.new("L", (d * 3, d * 3), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * 3 - 1, d * 3 - 1), fill=255)
    return big.resize((d, d), Image.LANCZOS)


def polygon_mask(size: tuple[int, int], points: list[tuple[float, float]]) -> Image.Image:
    big = Image.new("L", (size[0] * 2, size[1] * 2), 0)
    ImageDraw.Draw(big).polygon([(x * 2, y * 2) for x, y in points], fill=255)
    return big.resize(size, Image.LANCZOS)


def iris(f: Image.Image, t: float, center: tuple[float, float], duration: float = 0.4) -> None:
    """Übergang: Kreisblende öffnet sich vom Bildmittelpunkt."""
    p = progress(t, 0.0, duration)
    if p >= 1:
        return
    r = ease_in_out(p) * math.hypot(W, H)
    cover = Image.new("RGBA", (W, H), (*T.BG_TOP, 255))
    cx, cy = center
    ImageDraw.Draw(cover).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 0))
    f.alpha_composite(cover)


def wipe(f: Image.Image, t: float, color, duration: float = 0.35) -> None:
    """Übergang: schräger Farbbalken wischt über das Bild (Magazin)."""
    p = ease_in_out(progress(t, 0.0, duration))
    if p >= 1:
        return
    x = -300 + p * (W + 900)
    d = ImageDraw.Draw(f)
    d.polygon([(x, 0), (W + 600, 0), (W + 600, H), (x - 600, H)], fill=(*T.BG_TOP, 255))
    d.polygon([(x - 90, 0), (x, 0), (x - 600, H), (x - 690, H)], fill=(*color, 255))


def flash(f: Image.Image, t: float, duration: float = 0.22) -> None:
    """Übergang: Kamerablitz (Polaroid)."""
    p = progress(t, 0.0, duration)
    if p < 1:
        f.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(230 * (1 - p) ** 2))))


def rank_bubble(rank: int, label: str, size: int, c1, c2) -> Image.Image:
    layer = gradient_fill(Image.new("RGBA", (size, size), (255, 255, 255, 255)), c1, c2, vertical=True)
    layer.putalpha(circle_mask(size))
    lab = text_layer(label, font("bold", max(16, size // 8)), fill=(*DARK, 200))
    paste(layer, lab, ((size - lab.width) / 2, size * 0.17))
    num = text_layer(f"#{rank}", fit_font(f"#{rank}", "black", int(size * 0.5), int(size * 0.78), 1)[0], fill=(*DARK, 255))
    paste(layer, num, ((size - num.width) / 2, size * 0.32))
    return layer


def outline_digits(text: str, size: int, color, stroke: int = 5) -> Image.Image:
    """Riesige Ziffern nur als Umriss (Magazin-Look)."""
    fnt = font("black", size)
    l, tp, r, b = fnt.getbbox(text, stroke_width=stroke)
    layer = Image.new("RGBA", (r - l + 4, b - tp + 4), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((-l + 2, -tp + 2), text, font=fnt, fill=(0, 0, 0, 0), stroke_width=stroke,
                               stroke_fill=(*color, 255))
    return layer


def glyph_mask(text: str, max_w: int, max_h: int) -> Image.Image:
    """Maske einer riesigen Ziffernfolge, eingepasst in max_w × max_h (für Clips IN der Zahl)."""
    size = 1100
    while size > 200:
        fnt = font("black", size)
        l, tp, r, b = fnt.getbbox(text)
        if r - l <= max_w and b - tp <= max_h:
            break
        size -= 40
    fnt = font("black", size)
    l, tp, r, b = fnt.getbbox(text)
    mask = Image.new("L", (r - l + 8, b - tp + 8), 0)
    ImageDraw.Draw(mask).text((-l + 4, -tp + 4), text, font=fnt, fill=255)
    return mask


# --------------------------------------------------------------------------- Plätze

class FullItem(ItemScene):
    FULL = True


class CircleItem(ItemScene):
    D = 640
    CX, CY = W // 2, 580

    def media_size(self):
        return (self.D, self.D)

    def media_mask(self):
        return circle_mask(self.D)

    def media_shadow(self):
        return shadow(rounded_rect((self.D, self.D), self.D // 2, (0, 0, 0, 255)), 30, 190)

    def reel_size(self):
        return (self.D, self.D)

    def __init__(self, job):
        super().__init__(job)
        self.bubble = rank_bubble(self.item["rank"], self.L["rank"], 200, self.c1, self.c2)

    def frame(self, t):
        f = background(t, self.c1, self.c2)
        p = ease_out_back(progress(t, 0.08, 0.6))
        x0, y0 = self.CX - self.D / 2, self.CY - self.D / 2
        paste_scaled(f, self.card_shadow, (x0 - 60, y0 - 50), max(0.02, p), opacity=clamp(p))
        paste_scaled(f, self._card(t), (x0, y0), max(0.02, p), opacity=clamp(p * 1.5))
        # Fortschrittsring = Wert im Verhältnis zum Spitzenreiter (Fakten: nach Rang)
        pv = ease_out_cubic(progress(t, 0.45, 1.2))
        R = self.D / 2 + 36
        box = (self.CX - R, self.CY - R, self.CX + R, self.CY + R)
        d = ImageDraw.Draw(f)
        d.arc(box, 0, 360, fill=(*T.TRACK, 255), width=16)
        sweep = 360 * self.ratio() * pv
        if sweep > 1:
            d.arc(box, -90, -90 + sweep, fill=(*self.c1, 255), width=16)
        # Rang-Blase auf dem Ring (oben rechts), dreht sich hinein
        pb = ease_out_back(progress(t, 0.35, 0.45))
        if pb > 0:
            ang = math.radians(-45 - 40 * (1 - pb))
            bx, by = self.CX + R * math.cos(ang) - 100, self.CY + R * math.sin(ang) - 100
            paste_scaled(f, self.bubble, (bx, by), max(0.02, pb))
        header(f, self.job, t, self.job["n_items"] - self.item["rank"])
        self.texts(f, t, self.CY + self.D / 2 + 70, center=True)
        iris(f, t, (self.CX, self.CY))
        return self.finish(f, t)


class MagazineItem(ItemScene):
    MH, SLANT = 900, 150

    def media_size(self):
        return (W, self.MH)

    def media_mask(self):
        return polygon_mask((W, self.MH), [(0, 0), (W, 0), (W, self.MH - self.SLANT), (0, self.MH)])

    def media_shadow(self):
        return None

    def reel_size(self):
        return (W // 2, self.MH // 2)

    def __init__(self, job):
        super().__init__(job)
        self.big = outline_digits(f"{self.item['rank']:02d}", 400, self.c1, stroke=6)
        self.label = text_layer(self.L["rank"].upper(), font("black", 34), fill=(*self.c1, 255))

    def frame(self, t):
        f = background(t, self.c1, self.c2)
        pm = ease_out_cubic(progress(t, 0.0, 0.55))
        paste(f, self._card(t), (-(1 - pm) * W * 0.6, 0), opacity=clamp(pm * 1.4))
        paste(f, T.full_shade().crop((0, 0, W, 320)), (0, 0))
        # Farbkante entlang der Schräge
        d = ImageDraw.Draw(f)
        off = (1 - pm) * W
        d.polygon([(-off, self.MH + 6), (W - off, self.MH - self.SLANT + 6), (W - off, self.MH - self.SLANT + 22),
                   (-off, self.MH + 22)], fill=(*self.c1, 255))
        header(f, self.job, t, self.job["n_items"] - self.item["rank"])
        credit = self.clip_credits.get(self.reel.credit_at(t)) if self.reel is not None and self.reel.last else self.credit
        if credit:
            paste(f, credit, (X0, self.MH - self.SLANT - 40 - credit.height), opacity=pm)
        # Riesige Umriss-Ziffer rechts, zoomt aus der Tiefe heran
        pn = ease_out_cubic(progress(t, 0.15, 0.6))
        paste_scaled(f, self.big, (W - self.big.width - 40, self.MH - 210), 1.7 - 0.7 * pn, opacity=0.85 * pn)
        paste(f, self.label, (W - self.big.width - 30, self.MH - 250), opacity=pn)
        # Farbbalken links neben dem Namen wächst
        y = self.MH + 60
        pb = ease_out_cubic(progress(t, 0.25, 0.5))
        d.rectangle((X0 - 40, y + 6, X0 - 26, y + 6 + 220 * pb), fill=(*self.c1, 255))
        self.texts(f, t, y, slide=-90)
        wipe(f, t, self.c1)
        return self.finish(f, t)


class PolaroidItem(ItemScene):
    PHOTO = (600, 520)
    BORDER, BOTTOM = 28, 100

    def media_size(self):
        return self.PHOTO

    def media_mask(self):
        return Image.new("L", self.PHOTO, 255)

    def media_shadow(self):
        return None

    def reel_size(self):
        return self.PHOTO

    def __init__(self, job):
        super().__init__(job)
        pw, ph = self.PHOTO
        self.size = (pw + 2 * self.BORDER, ph + self.BORDER + self.BOTTOM)
        self.angle = 4.0 if self.item["rank"] % 2 else -4.0
        hand = "caveat-bold.ttf" in T._font_index()     # Handschrift da? sonst Standardschrift in kleinerer Größe
        self.caption = text_layer(f"#{self.item['rank']}", font("hand", 96 if hand else 78), fill=(40, 40, 44, 255))
        tape = Image.new("RGBA", (190, 54), (255, 248, 210, 150))
        self.tape = tape.rotate(-3, resample=Image.BICUBIC, expand=True)
        self.drop_shadow = shadow(Image.new("RGBA", self.size, (0, 0, 0, 255)), 26, 170)
        # Stapel älterer Bilder dahinter (leer, leicht verdreht)
        stack = Image.new("RGBA", (W, 1000), (0, 0, 0, 0))
        for angle, dx, dy in ((-9, -40, 30), (7, 50, 10)):
            sheet = Image.new("RGBA", self.size, (236, 236, 230, 255))
            ImageDraw.Draw(sheet).rectangle((self.BORDER, self.BORDER, self.BORDER + pw, self.BORDER + ph),
                                            fill=(*T.CARD, 255))
            rot = sheet.rotate(angle, resample=Image.BICUBIC, expand=True)
            paste(stack, shadow(rot, 20, 120), ((W - rot.width) / 2 + dx - 40, dy - 40))
            paste(stack, rot, ((W - rot.width) / 2 + dx, dy))
        self.stack = stack

    def frame(self, t):
        f = background(t, self.c1, self.c2)
        paste(f, self.stack, (0, 200), opacity=clamp(progress(t, 0.1, 0.4)))
        pe = ease_out_back(progress(t, 0.0, 0.75))
        angle = self.angle + (1 - clamp(pe)) * (-24 if self.angle > 0 else 24) + 0.7 * math.sin(t * 1.3)
        pol = Image.new("RGBA", self.size, (250, 250, 246, 255))
        pol.alpha_composite(self._card(t), (self.BORDER, self.BORDER))
        paste(pol, self.caption, (self.BORDER + 8, self.PHOTO[1] + self.BORDER + 12))
        paste(pol, self.tape, ((self.size[0] - self.tape.width) / 2, -12))
        rot = pol.rotate(angle, resample=Image.BILINEAR, expand=True)
        y = 220 - (1 - pe) * 1200
        paste(f, self.drop_shadow, ((W - self.drop_shadow.width) / 2 + 14, y + 10 - 52), opacity=clamp(pe))
        paste(f, rot, ((W - rot.width) / 2, y - (rot.height - self.size[1]) / 2))
        header(f, self.job, t, self.job["n_items"] - self.item["rank"])
        credit = self.clip_credits.get(self.reel.credit_at(t)) if self.reel is not None and self.reel.last else self.credit
        if credit:
            paste(f, credit, (X0, 220 + self.size[1] + 22), opacity=clamp(pe))
        self.texts(f, t, 220 + self.size[1] + 104)
        flash(f, t)
        return self.finish(f, t)


class NumberItem(ItemScene):
    """Der Clip läuft in der riesigen Rang-Ziffer; sie zoomt aus dem Bild heraus heran."""
    TOP = 240

    def media_size(self):
        self.glyph = glyph_mask(str(self.item["rank"]), CONTENT_W, 620)
        return self.glyph.size

    def media_mask(self):
        return self.glyph

    def media_shadow(self):
        layer = Image.new("RGBA", self.card_size, (0, 0, 0, 255))
        layer.putalpha(self.glyph)
        return shadow(layer, 28, 200)

    def reel_size(self):
        return self.card_size

    def __init__(self, job):
        super().__init__(job)
        ring = ImageChops.subtract(self.glyph.filter(ImageFilter.MaxFilter(13)), self.glyph)
        self.outline = Image.new("RGBA", self.card_size, (*self.c1, 255))
        self.outline.putalpha(ring)
        self.label = text_layer(self.L["rank"].upper(), font("black", 40), fill=(*self.c1, 255))

    def frame(self, t):
        f = background(t, self.c1, self.c2)
        pz = ease_out_cubic(progress(t, 0.0, 0.65))
        scale = 2.6 - 1.6 * pz + 0.015 * math.sin(t * 2.2)
        gw, gh = self.card_size
        x, y = (W - gw) / 2, self.TOP
        paste_scaled(f, self.card_shadow, (x - 56, y - 56), scale, opacity=clamp(pz))
        paste_scaled(f, self._card(t), (x, y), scale, opacity=clamp(pz * 1.3))
        paste_scaled(f, self.outline, (x, y), scale, opacity=clamp(pz))
        paste(f, self.label, ((W - self.label.width) / 2, y - 56), opacity=clamp(progress(t, 0.4, 0.3)))
        header(f, self.job, t, self.job["n_items"] - self.item["rank"])
        credit = self.clip_credits.get(self.reel.credit_at(t)) if self.reel is not None and self.reel.last else self.credit
        if credit:
            paste(f, credit, ((W - credit.width) / 2, y + gh + 8), opacity=pz)
        self.texts(f, t, y + gh + 60, center=True)
        return self.finish(f, t)


# --------------------------------------------------------------------------- Intros

class CinemaIntro(IntroScene):
    """Vollbild-Format: Kino-Vorspann – Letterbox-Balken fahren herein, Titel groß in der Mitte."""

    def frame(self, t):
        f = background(t)
        pb = ease_out_cubic(progress(t, 0.0, 0.5))
        d = ImageDraw.Draw(f)
        bar = 210 * pb
        d.rectangle((0, 0, W, bar), fill=(0, 0, 0, 255))
        d.rectangle((0, H - bar, W, H), fill=(0, 0, 0, 255))
        paste(f, self.badge, ((W - self.badge.width) / 2, 300), opacity=clamp(progress(t, 0.3, 0.4)))
        y = 420
        for i, layer in enumerate(self.title_lines):
            pi = ease_out_cubic(progress(t, 0.35 + i * 0.15, 0.6))
            paste_scaled(f, layer, ((W - layer.width) / 2, y), 1.12 - 0.12 * pi, opacity=pi)
            y += self.line_h
        if self.top_q is not None:
            count = ease_out_cubic(progress(t, 0.9, 1.4))
            value = text_layer(self.top_q.display(self.lang, self.top_q.value * count), font("black", 110), fill=(*GOLD, 255))
            paste(f, self.mystery, ((W - self.mystery.width) / 2, y + 60), opacity=clamp(count * 3))
            paste(f, value, ((W - value.width) / 2, y + 60 + self.mystery.height), opacity=clamp(count * 3))
        self.subs.draw(f, t)
        return f


class CircleIntro(IntroScene):
    def frame(self, t):
        f = background(t)
        y = 260
        for i, layer in enumerate(self.title_lines):
            pi = ease_out_cubic(progress(t, 0.15 + i * 0.1, 0.45))
            paste(f, layer, (X0 + (CONTENT_W - layer.width) / 2, y + 40 * (1 - pi)), opacity=pi)
            y += self.line_h
        cx, r = W / 2, 230
        cy = min(max(y + 290, 820), 900)
        pc = ease_out_back(progress(t, 0.5, 0.6))
        d = ImageDraw.Draw(f)
        if pc > 0:
            rr = r * pc
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(*T.CARD, 255))
            for k in range(12):                              # gestrichelter Ring dreht sich
                a0 = k * 30 + t * 40
                d.arc((cx - rr - 30, cy - rr - 30, cx + rr + 30, cy + rr + 30), a0, a0 + 18, fill=(*T.ACCENT, 255), width=10)
            paste_scaled(f, self.q, (cx - self.q.width / 2, cy - self.q.height / 2 + math.sin(t * 3) * 6), max(0.02, pc))
        if self.top_q is not None:                          # Rekordwert unter dem Kreis, über den Untertiteln
            count = ease_out_cubic(progress(t, 0.9, 1.4))
            value = text_layer(self.top_q.display(self.lang, self.top_q.value * count), font("black", 92), fill=(*GOLD, 255))
            paste(f, self.mystery, ((W - self.mystery.width) / 2, cy + r + 46), opacity=clamp(pc))
            paste(f, value, ((W - value.width) / 2, cy + r + 46 + self.mystery.height), opacity=clamp(pc))
        iris(f, t, (W / 2, H / 2), 0.5)
        self.subs.draw(f, t)
        return f


class MagazineIntro(IntroScene):
    def __init__(self, job):
        super().__init__(job)
        self.big = outline_digits(f"{job['n_items']:02d}", 520, T.ACCENT, stroke=7)
        self.top = text_layer(self.L["top"], font("black", 70), fill=(*T.ACCENT, 255))

    def frame(self, t):
        f = background(t)
        pn = ease_out_cubic(progress(t, 0.0, 0.7))
        paste_scaled(f, self.big, (W - self.big.width - 30, 210), 1.6 - 0.6 * pn, opacity=0.9 * pn)
        paste(f, self.top, (X0, 260 + 30 * (1 - pn)), opacity=pn)
        block = self.line_h * len(self.title_lines) + (150 if self.top_q is not None else 0)
        y = min(800, SUB_Y - 190 - block)               # lange Titel rücken nach oben, nie in die Untertitel
        d = ImageDraw.Draw(f)
        pb = ease_out_cubic(progress(t, 0.3, 0.5))
        d.rectangle((X0 - 40, y + 10, X0 - 26, y + 10 + self.line_h * len(self.title_lines) * pb), fill=(*T.ACCENT, 255))
        for i, layer in enumerate(self.title_lines):
            pi = ease_out_cubic(progress(t, 0.25 + i * 0.1, 0.45))
            paste(f, layer, (X0 + 90 * (1 - pi), y), opacity=pi)
            y += self.line_h
        if self.top_q is not None:
            count = ease_out_cubic(progress(t, 0.9, 1.4))
            value = text_layer(self.top_q.display(self.lang, self.top_q.value * count), font("black", 92), fill=(*GOLD, 255))
            paste(f, self.mystery, (X0, y + 30), opacity=clamp(count * 3))
            paste(f, value, (X0, y + 30 + self.mystery.height), opacity=clamp(count * 3))
        wipe(f, t, T.ACCENT, 0.45)
        self.subs.draw(f, t)
        return f


class PolaroidIntro(IntroScene):
    def __init__(self, job):
        super().__init__(job)
        pw, ph, b = 520, 480, 26
        stack = Image.new("RGBA", (W, 900), (0, 0, 0, 0))
        for k, angle in enumerate((-10, 6, -2)):
            sheet = Image.new("RGBA", (pw + 2 * b, ph + b + 100), (244, 244, 238, 255))
            ImageDraw.Draw(sheet).rectangle((b, b, b + pw, b + ph), fill=(*T.CARD, 255))
            if k == 2:
                paste(sheet, self.q, (b + (pw - self.q.width) / 2, b + (ph - self.q.height) / 2))
            rot = sheet.rotate(angle, resample=Image.BICUBIC, expand=True)
            x = (W - rot.width) / 2 + (k - 1) * 40
            paste(stack, shadow(rot, 20, 130), (x - 40, 40 - 40))
            paste(stack, rot, (x, 40))
        self.stack = stack

    def frame(self, t):
        f = background(t)
        y = 220
        for i, layer in enumerate(self.title_lines):
            pi = ease_out_cubic(progress(t, 0.15 + i * 0.1, 0.45))
            paste(f, layer, (X0, y + 40 * (1 - pi)), opacity=pi)
            y += self.line_h
        pe = ease_out_back(progress(t, 0.35, 0.7))
        paste(f, self.stack, (0, max(y + 20, 600) - (1 - pe) * 1300))
        flash(f, t, 0.25)
        self.subs.draw(f, t)
        return f


class NumberIntro(IntroScene):
    def __init__(self, job):
        super().__init__(job)
        mask = glyph_mask(str(job["n_items"]), CONTENT_W, 600)
        layer = gradient_fill(Image.new("RGBA", mask.size, (255, 255, 255, 255)), T.ACCENT, T.ACCENT2, vertical=True)
        layer.putalpha(mask)
        self.big = layer
        self.top = text_layer(self.L["top"], font("black", 60), fill=(*WHITE, 255))

    def frame(self, t):
        f = background(t)
        pz = ease_out_cubic(progress(t, 0.0, 0.7))
        paste_scaled(f, self.big, ((W - self.big.width) / 2, 260), 2.4 - 1.4 * pz, opacity=clamp(pz * 1.3))
        paste(f, self.top, ((W - self.top.width) / 2, 200), opacity=pz)
        y = 260 + self.big.height + 40
        for i, layer in enumerate(self.title_lines):
            pi = ease_out_cubic(progress(t, 0.35 + i * 0.1, 0.45))
            paste(f, layer, ((W - layer.width) / 2, y + 30 * (1 - pi)), opacity=pi)
            y += self.line_h
        self.subs.draw(f, t)
        return f


# --------------------------------------------------------------------------- Abschluss

class PodiumOutro(OutroScene):
    """Abschluss als Siegerpodest (Plätze 1–3) mit kompakter Liste der übrigen Plätze darüber."""

    def __init__(self, job):
        super().__init__(job)
        rows = job["outro"]["rows"]
        self.top3 = {rank: (name, value) for rank, name, value in rows if rank <= 3}
        rest_rows = [r for r in rows if r[0] > 3]
        small = font("semibold", 30)
        self.rest_layers = []
        for rank, name, value in rest_rows[:9]:
            label = f"{rank}. {name}" + (f" – {value}" if value else "")
            while small.getlength(label) > CONTENT_W and len(label) > 8:
                label = label[:-2]
            self.rest_layers.append(text_layer(label, small, fill=(*T.MUTED, 255)))
        self.name_font = font("bold", 32)

    def frame(self, t):
        f = background(t)
        pt = ease_out_cubic(progress(t, 0.0, 0.4))
        paste(f, self.title, (X0, 140 + (1 - pt) * 30), opacity=pt)
        y = 160 + self.title.height + 24
        for i, layer in enumerate(self.rest_layers):
            pr = ease_out_cubic(progress(t, 0.2 + i * 0.06, 0.35))
            paste(f, layer, (X0, y + 20 * (1 - pr)), opacity=pr)
            y += layer.height + 6
        base = 1170
        col_w, gap = 270, 25
        heights = {1: 360, 2: 270, 3: 200}
        order = [2, 1, 3]
        d = ImageDraw.Draw(f)
        for k, rank in enumerate(order):
            if rank not in self.top3:
                continue
            name, value = self.top3[rank]
            pr = ease_out_back(progress(t, 0.5 + (2 - rank) * 0.2, 0.6))
            h = heights[rank] * clamp(pr)
            x = (W - (3 * col_w + 2 * gap)) / 2 + k * (col_w + gap)
            c1, c2 = rank_colors(rank)
            if h > 4:
                block = gradient_fill(rounded_rect((col_w, int(h)), 18, (255, 255, 255, 255)), c1, c2, vertical=True)
                paste(f, block, (x, base - h))
                num = text_layer(str(rank), font("black", 110), fill=(*DARK, 230))
                if h > num.height + 10:
                    paste(f, num, (x + (col_w - num.width) / 2, base - h + 14))
            fnt, lines = fit_font(name, "bold", 34, col_w, 2, min_size=22)
            label = text_layer(lines, fnt, fill=(*WHITE, 255), align="center", width=col_w)
            paste(f, label, (x, base - h - label.height - (44 if value else 10)), opacity=clamp(pr))
            if value:
                val = text_layer(value, font("bold", 30), fill=(*c1, 255))
                paste(f, val, (x + (col_w - val.width) / 2, base - h - 42), opacity=clamp(pr))
        d.rectangle((X0 - 20, base, X0 + CONTENT_W + 20, base + 6), fill=(*T.TRACK, 255))
        pc = ease_out_back(progress(t, 1.3, 0.5))
        s = max(0.01, pc * (1 + 0.03 * math.sin(t * 5)))
        paste_scaled(f, self.cta, (X0 + (CONTENT_W - self.cta.width) / 2, base + 24), s)
        self.subs.draw(f, t)
        return f


# --------------------------------------------------------------------------- Format „manuskript“ (Buchlook)

from PIL import ImageOps                                            # noqa: E402
from . import manuskript as M                                       # noqa: E402
from .icons import draw_icon                                        # noqa: E402
from .linien import DECOR, LABEL_Y, SIZE as ART, decor_layer, draw_visual, seg          # noqa: E402
from .scenes import Scene                                           # noqa: E402


def _toned(img: Image.Image, mask: Image.Image) -> Image.Image:
    """Foto/Clip dezent im Buchlook: fast entsättigt, warm eingefärbt, abgedunkelt, weiche Ränder."""
    rgb = img.convert("RGB")
    gray = ImageOps.autocontrast(rgb.convert("L"), cutoff=1)
    warm = ImageOps.colorize(gray, black=(4, 4, 4), white=(238, 224, 196))
    out = Image.blend(rgb, warm, 0.78).point(lambda v: int(v * 0.72)).convert("RGBA")
    out.putalpha(mask)
    return out


def wrap_lines(text: str, size: int, width: int) -> list[str]:
    from .theme import wrap
    return wrap(text, font("sub", size), width)


class ManuskriptItem(ItemScene):
    """Platz im Buchlook: Satz oben, Bild im Linien-Rahmen, darunter Name, Wert und Quellen-Pille."""
    MEDIA = (720, 470)

    def media_size(self):
        return self.MEDIA

    def media_mask(self):
        w, h = self.MEDIA
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle((12, 12, w - 13, h - 13), 26, fill=255)
        return m.filter(ImageFilter.GaussianBlur(7))

    def media_shadow(self):
        return None

    def reel_size(self):
        return self.MEDIA

    def __init__(self, job):
        super().__init__(job)
        it = self.item
        self.pill = M.chapter_pill(f"{self.L['rank'].title()} {it['rank']}")
        self.sentence = M.Sentence(job["text"], job["words"], job["lead"], bold=[it["name"]], max_h=330)
        w, h = self.MEDIA
        self.frame_img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
        ImageDraw.Draw(self.frame_img).rounded_rectangle((2, 2, w + 17, h + 17), 32, outline=(*M.INK, 70), width=2)
        self.icon = None
        if self.photo is None and self.reel is None:
            ic = draw_icon(it.get("icon", "globe"), 300)
            self.icon = Image.new("RGBA", ic.size, (*M.INK, 0))
            self.icon.putalpha(ic.getchannel("A").point(lambda a: int(a * 0.8)))
        nf, nl = fit_font(it["name"], "black", 72, 900, 2, min_size=44)
        self.name_layer = text_layer(nl, nf, fill=(*M.INK, 255), align="center", width=900)
        if it.get("fact"):
            self.value_layer = (text_layer(wrap_lines(it["kicker"], 38, 900), font("sub", 38), fill=(*M.INK_DIM, 255),
                                           align="center", width=900) if it.get("kicker") else None)
        else:
            self.value_layer = text_layer(self.q.display(self.lang, self.q.value), M.mfont("italic", 76),
                                          fill=(*M.INK, 255), align="center", width=900)
        bits = []
        if it.get("as_of"):
            bits.append(f"{self.L['as_of']} {it['as_of']}")
        if it.get("n_sources"):
            bits.append(self.L["src_n"].format(n=it["n_sources"]))
        self.src = M.source_pill(" · ".join(bits)) if bits else None
        self.label = M.caps_layer(it["value_label"]) if it.get("value_label") and not it.get("fact") else None

    def frame(self, t):
        f = M.background(t)
        fade = M.fade_in_out(t, self.job["duration"], 0.45, 0.5)
        top = M.TEXT_Y_PILL
        paste(f, self.pill, ((W - self.pill.width) / 2, M.PILL_Y - 22), opacity=fade)
        self.sentence.draw(f, t, top, fade)
        w, h = self.MEDIA
        fy = max(740, top + self.sentence.height + 50)
        fx = (W - w) / 2
        pc = ease_out_cubic(progress(t, 0.15, 0.7))
        if self.icon is not None:
            paste(f, self.icon, ((W - self.icon.width) / 2, fy + (h - self.icon.height) / 2 + math.sin(t * 1.4) * 6),
                  opacity=fade * pc)
        else:
            card = self._card(t)
            paste(f, _toned(card, card.getchannel("A")), (fx, fy + (1 - pc) * 18), opacity=fade * pc)
        paste(f, self.frame_img, (fx - 10, fy - 10 + (1 - pc) * 18), opacity=fade * pc)
        credit = self.clip_credits.get(self.reel.credit_at(t)) if self.reel is not None and self.reel.last else self.credit
        y = fy + h + 26
        if credit:
            paste(f, credit, ((W - credit.width) / 2, y), opacity=fade * 0.7)
            y += credit.height + 6
        pn = ease_out_cubic(progress(t, 0.5, 0.6))
        paste(f, self.name_layer, ((W - self.name_layer.width) / 2, y + (1 - pn) * 14), opacity=fade * pn)
        y += self.name_layer.height + 6
        if self.label is not None:
            paste(f, self.label, ((W - self.label.width) / 2, y), opacity=fade * pn)
            y += self.label.height - 4
        if self.value_layer is not None:
            pv = ease_out_cubic(progress(t, 0.8, 0.7))
            paste(f, self.value_layer, ((W - self.value_layer.width) / 2, y + (1 - pv) * 12), opacity=fade * pv)
            y += self.value_layer.height + 8
        if self.src is not None:
            paste(f, self.src, ((W - self.src.width) / 2, min(y + 6, 1500)), opacity=fade * progress(t, 1.2, 0.6))
        return f


class ManuskriptIntro(IntroScene):
    def __init__(self, job):
        super().__init__(job)
        self.pill = M.chapter_pill(f"{self.L['top']} {job['n_items']}")
        self.sentence = M.Sentence(job["text"], job["words"], job["lead"], bold=[], max_h=330)
        self.title_caps = M.caps_layer(job["title"][:48], 24, 6.0, underline=True)

    def frame(self, t):
        f = M.background(t)
        fade = M.fade_in_out(t, self.job["duration"], 0.5, 0.5)
        paste(f, self.pill, ((W - self.pill.width) / 2, M.PILL_Y - 22), opacity=fade)
        self.sentence.draw(f, t, M.TEXT_Y_PILL, fade)
        u = clamp((t - 0.3) / max(2.0, 0.62 * (self.job["lead"] + 3.0)))
        paste(f, decor_layer(), (0, 0), opacity=fade)
        layer = draw_visual("spirale_partikel", {}, u, t)
        paste(f, layer, (W / 2 - ART / 2, M.CY - ART / 2), opacity=fade)
        paste(f, self.title_caps, ((W - self.title_caps.width) / 2, 1360), opacity=fade * seg(u, 0.5, 0.9))
        return f


class ManuskriptOutro(OutroScene):
    def __init__(self, job):
        super().__init__(job)
        rows = job["outro"]["rows"]
        self.pill = M.chapter_pill(job["title"][:34])
        self.sentence = M.Sentence(job["text"], job["words"], job["lead"], bold=[], max_h=250)
        self.n = len(rows)
        self.cols = 1 if self.n <= 12 else 2
        self.per = math.ceil(self.n / self.cols)
        self.row_h = row_h = max(40, min(78, int(780 / self.per)))
        fnt, vf = M.mfont("serif_m", int(row_h * 0.55)), M.mfont("italic", int(row_h * 0.55))
        self.col_w = col_w = 900 // self.cols - (20 if self.cols > 1 else 0)
        self.rows_l = []
        for rank, name, value in rows:
            img = Image.new("RGBA", (col_w, row_h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            base = row_h * 0.68
            d.text((4, base), f"{rank}", font=vf, fill=(*M.INK_DIM, 255), anchor="ls")
            label = name
            vw = vf.getlength(value) if value else 0
            while fnt.getlength(label) > col_w - vw - 80 and len(label) > 4:
                label = label[:-2]
            d.text((row_h * 0.9, base), label if label == name else label.rstrip() + "…", font=fnt,
                   fill=(*M.INK, 255), anchor="ls")
            if value:
                d.text((col_w - 4, base), value, font=vf, fill=(*M.INK_DIM, 255), anchor="rs")
            d.line((0, row_h - 2, col_w, row_h - 2), fill=(*M.INK_FAINT, 90), width=1)
            self.rows_l.append(img)
        self.cta = M.caps_layer(self.L["cta"].rstrip("!"), 24, 6.0, underline=True)

    def frame(self, t):
        f = M.background(t)
        fade = M.fade_in_out(t, self.job["duration"], 0.5, 0.7)
        paste(f, self.pill, ((W - self.pill.width) / 2, M.PILL_Y - 22), opacity=fade)
        self.sentence.draw(f, t, M.TEXT_Y_PILL, fade)
        y0 = max(700, M.TEXT_Y_PILL + self.sentence.height + 40)
        x0 = (W - 900) / 2
        for i, img in enumerate(self.rows_l):
            col, r = divmod(i, self.per)
            pr = ease_out_cubic(progress(t, 0.3 + i * min(0.12, 1.8 / max(1, self.n)), 0.5))
            paste(f, img, (x0 + col * (self.col_w + 20), y0 + r * self.row_h + (1 - pr) * 10), opacity=fade * pr)
        paste(f, self.cta, ((W - self.cta.width) / 2, min(1500, y0 + self.per * self.row_h + 40)),
              opacity=fade * progress(t, 1.4, 0.6))
        return f


class ErklaerScene(Scene):
    """Eine Szene des Erklärvideos (`erklaer/`): Kapitel-Pille, Satz Wort für Wort, Linien-Grafik oder Zitat-Karte."""

    def __init__(self, job):
        self.job = job
        sz = job["szene"]
        self.visual = sz.get("visual") or {}
        self.kind = self.visual.get("typ", "beschriftung")
        self.pill = M.chapter_pill(sz["kapitel"]) if sz.get("kapitel") else None
        self.sentence = M.Sentence(sz["text"], job["words"], job["lead"], bold=sz.get("betont") or [], max_h=300)
        self.label = M.caps_layer(self.visual["label"], 22, 5.5, underline=True) if self.visual.get("label") else None
        self.quote = self._quote() if self.kind == "zitatkarte" else None
        self.build = max(2.0, 0.6 * (job["lead"] + job["voice_dur"]))
        self.anim = None
        if sz.get("animation"):                               # eigene Animation (animation.py) statt Linien-Grafik
            from ..animation import Bild

            self.anim = Bild(sz["animation"], sz["text"], job["words"], job["lead"], M.INK, (214, 162, 84),
                             job.get("index", 0))

    def _quote(self):
        v = self.visual
        z = str(v.get("zitat") or "")
        arabic = any("؀" <= c <= "ۿ" for c in z)
        main = M.small_text(z, "arabic" if arabic else "serif", 98 if arabic else 60, M.INK, 255, 900)
        sub = " · ".join(x for x in (v.get("umschrift"), v.get("uebersetzung")) if x)
        return {"main": main, "sub": M.small_text(sub, "italic", 31, M.INK_DIM, 235, 900) if sub else None,
                "pill": M.source_pill(v["quelle"]) if v.get("quelle") else None,
                "by": M.small_text(v["ueberliefert"], "sans", 19, M.INK_DIM, 150, 900) if v.get("ueberliefert") else None}

    def frame(self, t):
        f = M.background(t)
        fade = M.fade_in_out(t, self.job["duration"], 0.4, 0.4)
        top = M.TEXT_Y_PILL if self.pill is not None else M.TEXT_Y
        if self.pill is not None:
            paste(f, self.pill, ((W - self.pill.width) / 2, M.PILL_Y - 22), opacity=fade)
        self.sentence.draw(f, t, top, fade)
        u = clamp((t - 0.35) / self.build)
        if self.quote is not None:
            q = self.quote
            paste(f, M.blur_in(q["main"], ease_out_cubic(progress(t, 0.5, 1.0))),
                  ((W - q["main"].width) / 2, 844 - q["main"].height / 2), opacity=fade)
            if q["sub"] is not None:
                paste(f, M.blur_in(q["sub"], ease_out_cubic(progress(t, 0.9, 0.9))),
                      ((W - q["sub"].width) / 2, 956 - q["sub"].height / 2), opacity=fade)
            if q["pill"] is not None:
                paste(f, q["pill"], ((W - q["pill"].width) / 2, 1056), opacity=fade * progress(t, 1.3, 0.7))
            if q["by"] is not None:
                paste(f, q["by"], ((W - q["by"].width) / 2, 1118), opacity=fade * progress(t, 1.6, 0.7))
            return f
        if self.anim is not None:
            shift = max(0, min(170, top + self.sentence.height + 40 - (M.CY - 400)))
            paste(f, self.anim.bild(t, ART), (W / 2 - ART / 2, M.CY - ART / 2 + shift), opacity=fade)
            return f
        if self.kind in DECOR:
            paste(f, decor_layer(), (0, 0), opacity=fade * clamp(t / 0.8))
        layer = draw_visual(self.kind, self.visual, u, t)
        shift = max(0, min(170, top + self.sentence.height + 40 - (M.CY - 400)))     # langer Satz: Grafik rückt nach unten
        if layer is not None:
            paste(f, layer, (W / 2 - ART / 2, M.CY - ART / 2 + shift), opacity=fade)
        if self.label is not None:
            paste(f, self.label, ((W - self.label.width) / 2, LABEL_Y.get(self.kind, 1380) + shift),
                  opacity=fade * seg(u, 0.6, 1.0))
        return f


SCENES = {
    "karte": {},
    "vollbild": {"item": FullItem, "intro": CinemaIntro},
    "kreis": {"item": CircleItem, "intro": CircleIntro, "outro": PodiumOutro},
    "magazin": {"item": MagazineItem, "intro": MagazineIntro},
    "polaroid": {"item": PolaroidItem, "intro": PolaroidIntro, "outro": PodiumOutro},
    "zahl": {"item": NumberItem, "intro": NumberIntro, "outro": PodiumOutro},
    "manuskript": {"item": ManuskriptItem, "intro": ManuskriptIntro, "outro": ManuskriptOutro, "erklaer": ErklaerScene},
}
BASE = {"intro": IntroScene, "item": ItemScene, "outro": OutroScene}


def scene_class(fmt: str, kind: str):
    return SCENES.get(fmt, {}).get(kind) or BASE[kind]
