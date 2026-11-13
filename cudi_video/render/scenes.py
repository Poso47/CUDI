"""Szenen des Videos. Jede Szene liefert für einen Zeitpunkt t (Sekunden) ein Bild."""

from __future__ import annotations

import math
import random
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from ..units import quantity
from .icons import draw_icon
from .theme import (
    ACCENT, ACCENT2, CARD, CONTENT_W, GOLD, H, MUTED, STYLE, SUB_Y, TRACK, W, WHITE, X0,
    apply_style, backdrop_from, background, clamp, full_shade, cover_crop, ease_in_out, ease_out_back, ease_out_cubic, fit_font, font,
    gradient_fill, paste, progress, rank_colors, rounded_mask, rounded_rect, shadow, text_layer, wrap,
)

LABELS = {
    "de": {"rank": "PLATZ", "top": "TOP", "photo": "Foto", "image": "Bild", "clip": "Video", "as_of": "Stand", "sources": "Quellen", "src_n": "{n} Quellen",
           "mystery": "Platz 1", "cta": "Folgen für mehr Rankings!"},
    "en": {"rank": "RANK", "top": "TOP", "photo": "Photo", "image": "Image", "clip": "Video", "as_of": "As of", "sources": "Sources", "src_n": "{n} sources",
           "mystery": "Number 1", "cta": "Follow for more rankings!"},
}


# --------------------------------------------------------------------------- Untertitel

class Subtitles:
    """Karaoke-Untertitel: kurze Wortgruppen, aktives Wort farbig hinterlegt."""

    MAX_CHARS = 20
    MAX_WORDS = 4

    def __init__(self, words: list[dict], text: str, offset: float, highlight=None):
        self.highlight = highlight or ACCENT
        self.mode = STYLE.get("subs", "box")
        self.font = font("sub", 66)
        self.line_height = sum(self.font.getmetrics()) + 14
        self.chunks = self._chunk(words, text)
        self.offset = offset
        self._cache: dict[tuple[int, int], Image.Image] = {}

    def _chunk(self, words, text):
        # Satzzeichen hinter den Wörtern im Originaltext finden -> dort Gruppen trennen.
        pos, enriched = 0, []
        for w in words:
            idx = text.find(w["text"], pos)
            end = idx + len(w["text"]) if idx >= 0 else pos
            following = text[end:end + 2]
            pos = end if idx >= 0 else pos
            ends = bool(re.search(r"[.,!?:;–]$", w["text"])) or bool(re.match(r"\s?[.,!?:;–]", following))
            enriched.append({**w, "break": ends})
        chunks, cur = [], []
        for w in enriched:
            cur.append(w)
            chars = sum(len(x["text"]) + 1 for x in cur)
            if w["break"] or len(cur) >= self.MAX_WORDS or chars >= self.MAX_CHARS:
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        return chunks

    def _render(self, ci: int, wi: int) -> Image.Image:
        key = (ci, wi)
        if key in self._cache:
            return self._cache[key]
        words = [w["text"] for w in self.chunks[ci]]
        fnt = self.font
        space = fnt.getlength(" ") + 14   # Platz für die Markierung des aktiven Worts
        lines = wrap(" ".join(words), fnt, CONTENT_W - 120)
        ascent, descent = fnt.getmetrics()
        line_h = ascent + descent + 14
        img = Image.new("RGBA", (CONTENT_W, line_h * len(lines) + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        idx = 0
        for li, line in enumerate(lines):
            line_words = line.split(" ")
            total = sum(fnt.getlength(x) for x in line_words) + space * (len(line_words) - 1)
            x = (CONTENT_W - total) / 2
            y = 10 + li * line_h
            for word in line_words:
                wl = fnt.getlength(word)
                if idx == wi and self.mode == "box":          # Design: aktives Wort farbig hinterlegt
                    d.rounded_rectangle((x - 12, y - 4, x + wl + 12, y + ascent + descent + 4), 16, fill=(*self.highlight, 255))
                    d.text((x, y), word, font=fnt, fill=(10, 12, 28))
                elif idx == wi:                                  # „outline“/„color“: aktives Wort in Akzentfarbe
                    d.text((x, y - 3), word, font=fnt, fill=(*self.highlight, 255),
                           stroke_width=6 if self.mode == "outline" else 2, stroke_fill=(5, 6, 16))
                elif self.mode == "color":
                    d.text((x, y), word, font=fnt, fill=(235, 235, 240), stroke_width=2, stroke_fill=(5, 6, 16))
                else:
                    d.text((x, y), word, font=fnt, fill=WHITE, stroke_width=6, stroke_fill=(5, 6, 16))
                x += wl + space
                idx += 1
        self._cache[key] = img
        return img

    def draw(self, frame: Image.Image, t: float) -> None:
        ts = t - self.offset
        for ci, chunk in enumerate(self.chunks):
            nxt = self.chunks[ci + 1][0]["start"] if ci + 1 < len(self.chunks) else chunk[-1]["end"] + 0.5
            if chunk[0]["start"] - 0.05 <= ts < nxt:
                wi = 0
                for i, w in enumerate(chunk):
                    if ts >= w["start"] - 0.03:
                        wi = i
                img = self._render(ci, wi)
                pop = ease_out_back(progress(ts, chunk[0]["start"] - 0.05, 0.18))
                # oben verankert: zweizeilige Untertitel wachsen nach unten statt in die Info-Chips
                y = SUB_Y - self.line_height / 2 - 10 + (1 - pop) * 18
                paste(frame, img, (X0, y), opacity=clamp(pop * 1.4))
                return


# --------------------------------------------------------------------------- Bausteine

def header(frame, job, t, current_index: int | None):
    """Videotitel klein + Countdown-Fortschritt."""
    title = job["_header_title"]
    paste(frame, title, (X0, 112))
    if job.get("_channel_layer") is not None:
        layer = job["_channel_layer"]
        paste(frame, layer, (X0 + CONTENT_W - layer.width, 112))
    n = job["n_items"]
    gap = 8
    seg_w = (CONTENT_W - gap * (n - 1)) / n
    d = ImageDraw.Draw(frame)
    for i in range(n):
        x = X0 + i * (seg_w + gap)
        color = TRACK
        if current_index is not None and i < current_index:
            color = (70, 120, 160)
        if current_index is not None and i == current_index:
            pulse = 0.75 + 0.25 * math.sin(t * 6)
            color = tuple(int(c * pulse) for c in job["_color1"])
        d.rounded_rectangle((x, 168, x + seg_w, 178), 5, fill=color)


def chip(text: str, fnt, fg=WHITE, bg=(255, 255, 255, 28)) -> Image.Image:
    tw = int(fnt.getlength(text))
    ascent, descent = fnt.getmetrics()
    img = rounded_rect((tw + 44, ascent + descent + 22), 28, bg)
    ImageDraw.Draw(img).text((22, 10), text, font=fnt, fill=fg)
    return img


class GraphicCard:
    """Karte ohne Foto: Farbverlauf, wandernde Streifen und Themen-Icon – oder eine Flagge."""

    def __init__(self, size, icon: str, c1, c2, flag: Image.Image | None = None, keep_out=(0, 0)):
        """keep_out: Breite/Höhe der Ecke oben links, die das Rang-Badge verdeckt."""
        self.size = size
        w, h = size
        base = rounded_rect(size, 36, (*CARD, 255))
        grad = gradient_fill(rounded_rect(size, 36, (255, 255, 255, 255)), c1, c2)
        paste(base, grad, (0, 0), 0.30 if flag else 0.55)
        self.base = base
        stripes = Image.new("RGBA", (w + 92, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(stripes)
        for i in range(-h, w + 92, 46):
            d.line((i, h, i + h, 0), fill=(255, 255, 255, 14), width=14)
        self.stripes = stripes
        self.mask = rounded_mask(size, 36)
        self.flag = None
        if flag is not None:
            # Flaggen tragen Wappen oft oben links (Malta, Union Jack) – dort sitzt das Badge.
            # Daher rechts neben dem Badge platzieren statt mittig.
            left = keep_out[0] + 30 if keep_out[0] > 0 else 70
            box_w, box_h = w - left - 50, h - 100
            fw, fh = flag.size
            scale = min(box_w / fw, box_h / fh)
            self.flag_center = (left + box_w / 2, h / 2)
            flag = flag.resize((max(1, int(fw * scale)), max(1, int(fh * scale))), Image.LANCZOS).convert("RGBA")
            framed = Image.new("RGBA", (flag.width + 12, flag.height + 12), (255, 255, 255, 235))
            framed.alpha_composite(flag, (6, 6))
            self.flag = framed
            self.flag_shadow = shadow(framed, 18, 170)
            self.icon = None
        else:
            self.icon = draw_icon(icon, int(min(w, h) * 0.62))
            glow = Image.new("RGBA", self.icon.size, (255, 255, 255, 0))
            glow.putalpha(self.icon.getchannel("A").point(lambda a: a // 3))
            self.icon_glow = glow.filter(ImageFilter.GaussianBlur(18))

    def render(self, t: float, duration: float) -> Image.Image:
        w, h = self.size
        card = self.base.copy()
        offset = int((t * 18) % 46)                       # Streifen wandern langsam
        card.alpha_composite(self.stripes.crop((offset, 0, offset + w, h)))
        p = ease_in_out(clamp(t / max(1.0, duration)))
        if self.flag is not None:
            scale = 1.0 + 0.04 * p
            flag = self.flag.resize((int(self.flag.width * scale), int(self.flag.height * scale)), Image.BILINEAR)
            x, y = self.flag_center[0] - flag.width / 2, self.flag_center[1] - flag.height / 2
            paste(card, self.flag_shadow, (x - 36, y - 26))
            paste(card, flag, (x, y))
        else:
            bob = math.sin(t * 1.6) * 8                      # Icon "schwebt" leicht
            x, y = (w - self.icon.width) / 2, (h - self.icon.height) / 2 + bob
            paste(card, self.icon_glow, (x, y))
            paste(card, self.icon, (x, y))
        card.putalpha(ImageChops.multiply(card.getchannel("A"), self.mask))
        return card


# --------------------------------------------------------------------------- Szenen

def card_motion(p: float) -> tuple[float, float, float]:
    """(dx, dy, Maßstab) einer hereinkommenden Karte je Bewegungsprofil des Designs."""
    mode = STYLE.get("card", "slide")
    if mode == "rise":
        return 0.0, (1 - p) * 240, 1.0
    if mode == "zoom":
        return 0.0, 0.0, 0.82 + 0.18 * p
    if mode == "swing":
        return (1 - p) * -360, 0.0, 1.0
    return 0.0, (1 - p) * 50, 1.0


def paste_scaled(f, layer, xy, scale: float, opacity: float = 1.0) -> None:
    """Ebene um ihre Mitte skaliert einfügen (kleiner oder größer; nur während der Animation, sonst unverändert)."""
    if abs(scale - 1) < 0.001:
        paste(f, layer, xy, opacity=opacity)
        return
    w, h = max(1, int(layer.width * scale)), max(1, int(layer.height * scale))
    paste(f, layer.resize((w, h), Image.BILINEAR), (xy[0] + (layer.width - w) / 2, xy[1] + (layer.height - h) / 2),
          opacity=opacity)


class Scene:
    def __init__(self, job: dict):
        self.job = job
        self.lang = job["lang"]
        self.L = LABELS[self.lang]
        self.lead = job["lead"]
        c1, c2 = rank_colors(job.get("item", {}).get("rank", 99))
        job["_color1"], job["_color2"] = c1, c2
        self.c1, self.c2 = c1, c2
        channel = job.get("channel") or ""
        job["_channel_layer"] = text_layer(channel, font("bold", 30), fill=(*WHITE, 200)) if channel else None
        title_width = CONTENT_W - (job["_channel_layer"].width + 24 if channel else 0)
        fnt, lines = fit_font(job["title"], "semibold", 34, title_width, 1, min_size=22)
        job["_header_title"] = text_layer(lines, fnt, fill=MUTED)
        self.subs = Subtitles(job["words"], job["text"], offset=self.lead,
                              highlight=GOLD if job.get("item", {}).get("rank") == 1 else ACCENT)

    def frame(self, t: float) -> Image.Image:
        raise NotImplementedError


class IntroScene(Scene):
    def __init__(self, job):
        super().__init__(job)
        n = job["n_items"]
        self.badge = chip(f"{self.L['top']} {n}", font("black", 64), fg=(10, 12, 28), bg=(*ACCENT, 255))
        fnt, lines = fit_font(job["title"], "black", 112, CONTENT_W, 4, min_size=64)
        self.title_lines = [gradient_fill(text_layer(l, fnt), WHITE, (200, 220, 255), vertical=True) for l in lines]
        self.line_h = fnt.getmetrics()[0] + fnt.getmetrics()[1]
        self.card = rounded_rect((CONTENT_W, 400), 40, (*CARD, 235))
        self.card_shadow = shadow(self.card, 30, 170)
        self.q = text_layer("?", font("black", 260), fill=(*GOLD, 255))
        self.mystery = text_layer(self.L["mystery"], font("bold", 46), fill=MUTED)
        top = job["intro"]
        self.top_q = None if top.get("fact") else quantity(top["si_value"], top["unit"], top["wanted"])

    def frame(self, t):
        f = background(t)
        p = ease_out_back(progress(t, 0.05, 0.45))
        badge = self.badge.resize((max(1, int(self.badge.width * p)), max(1, int(self.badge.height * p))))
        paste(f, badge, (X0 + (self.badge.width - badge.width) / 2, 250 + (self.badge.height - badge.height) / 2))
        y = 390
        for i, layer in enumerate(self.title_lines):
            pi = ease_out_cubic(progress(t, 0.2 + i * 0.12, 0.45))
            mode = STYLE.get("title", "left")
            if mode == "scale":
                paste_scaled(f, layer, (X0, y), 0.7 + 0.3 * pi, opacity=pi)
            else:
                dx = {"left": -80, "right": 80}.get(mode, 0) * (1 - pi)
                paste(f, layer, (X0 + dx, y + (60 * (1 - pi) if mode == "rise" else 0)), opacity=pi)
            y += self.line_h
        cy = max(y + 50, 860)
        pc = ease_out_cubic(progress(t, 0.7, 0.5))
        dx, dy, sc = card_motion(pc)
        paste_scaled(f, self.card_shadow, (X0 - 60 + dx, cy - 60 + dy), sc, opacity=pc)
        paste_scaled(f, self.card, (X0 + dx, cy + dy), sc, opacity=pc)
        wobble = math.sin(t * 3) * 6
        paste(f, self.q, (X0 + 60, cy + 40 + wobble), opacity=pc)
        paste(f, self.mystery, (X0 + 300, cy + 90), opacity=pc)
        if self.top_q is not None:
            count = ease_out_cubic(progress(t, 0.9, 1.4))
            value = text_layer(self.top_q.display(self.lang, self.top_q.value * count), font("black", 92), fill=(*GOLD, 255))
            paste(f, value, (X0 + 300, cy + 170), opacity=pc)
        self.subs.draw(f, t)
        return f


def name_layout(name: str):
    """Name möglichst einzeilig (dann bleibt Platz für die Info-Chips), sonst zweizeilig."""
    fnt, lines = fit_font(name, "black", 88, CONTENT_W, 1, min_size=60)
    if lines == [name] and fnt.getlength(name) <= CONTENT_W:
        return fnt, lines
    return fit_font(name, "black", 72, CONTENT_W, 2, min_size=48)


class ItemScene(Scene):
    CARD_Y = 230
    CARD_SIZE = (CONTENT_W, 560)
    CARD_SIZE_LONG_NAME = (CONTENT_W, 490)   # zweizeiliger Name: Karte kürzer, damit die Info-Chips Platz haben
    BADGE = 230
    BADGE_POS = (-30, -40)          # relativ zur Bildkarte: ragt oben links über den Rand
    FULL = False                    # Format „vollbild“ (Unterklasse in formats.py)

    # --- Haken für Formate (formats.py): Form und Größe der Bildfläche, Maske, Schatten, Clip-Auflösung
    def media_size(self) -> tuple[int, int]:
        if self.full:
            return (W, H)
        return self.CARD_SIZE if len(self.name_lines) == 1 else self.CARD_SIZE_LONG_NAME

    def media_mask(self) -> Image.Image:
        return Image.new("L", self.card_size, 255) if self.full else rounded_mask(self.card_size, 36)

    def media_shadow(self):
        return None if self.full else shadow(rounded_rect(self.card_size, 36, (0, 0, 0, 255)), 30, 180)

    def reel_size(self) -> tuple[int, int]:
        return (W // 2, H // 2) if self.full else self.card_size      # Vollbild: halbe Auflösung, hochskaliert

    def ratio(self) -> float:
        """Anteil für Balken/Ringe: Wert im Verhältnis zum Spitzenwert (Fakten: nach Rang)."""
        if self.item.get("fact"):
            n = max(1, self.job["n_items"])
            return clamp((n + 1 - self.item["rank"]) / n)
        return clamp(abs(self.q.value) / self.max_display if self.max_display else 1.0)

    def __init__(self, job):
        super().__init__(job)
        it = job["item"]
        self.item = it
        self.q = quantity(it["si_value"], it["unit"], it["wanted"])
        self.max_display = job["max_display"]
        name_font, name_lines = name_layout(it["name"])
        self.name = text_layer(name_lines, name_font)
        self.name_font = name_font
        self.name_lines = name_lines
        # Vollbild-Format: Clip/Foto füllt den ganzen Bildschirm, Text unten auf Schatten (nur mit echtem Bild/Clip)
        self.full = self.FULL and bool(it.get("clips") or (it.get("image_path") and it.get("image_kind") != "flag"))
        self.card_size = self.media_size()
        # Bild vorbereiten: Fotos füllen die Karte (Ken-Burns braucht Reserve um den Ausschnitt),
        # Flaggen werden vollständig gezeigt, ohne Bild gibt es eine Grafik-Karte mit Themen-Icon.
        self.photo = None
        flag = None
        if it.get("image_path"):
            try:
                img = ImageOps.exif_transpose(Image.open(it["image_path"]))
                if it.get("image_kind") == "flag":
                    flag = img.convert("RGBA")
                else:
                    cw, ch = self.card_size
                    self.photo = cover_crop(img.convert("RGB"), (int(cw * 1.18), int(ch * 1.18)))
            except Exception:
                self.photo, flag = None, None
        if self.full and self.photo is None and not it.get("clips"):      # Foto nicht lesbar: zurück zur Karte
            self.full = False
            self.card_size = self.media_size()
        keep_out = (self.BADGE_POS[0] + self.BADGE, self.BADGE_POS[1] + self.BADGE)
        self.anim = None
        if it.get("szene"):                                   # eigene Animation statt Foto/Clip (Fakten-Videos)
            from ..animation import Bild

            self.anim = Bild(it["szene"], job["text"], job["words"], job["lead"], (250, 246, 236), self.c1, it["rank"])
            self.photo, it = None, {**it, "clips": [], "credit_short": None, "image_path": None}
            self.full = False
            self.card_size = self.media_size()
        self.graphic = None if self.photo else GraphicCard(self.card_size, it.get("icon", "globe"),
                                                           self.c1, self.c2, flag, keep_out)
        self.card_mask = self.media_mask()
        self.card_shadow = self.media_shadow()
        self.credit = None
        if it.get("credit_short"):
            kind = self.L["image"] if it.get("image_kind") == "flag" else self.L["photo"]
            self.credit = self._credit_chip(f"{kind}: {it['credit_short']}")
        # Echte Videoclips: mehrere kurze Ausschnitte hintereinander statt Foto-Zoom
        self.reel, self.clip_credits = None, {}
        if it.get("clips"):
            from .clipreel import ClipReel

            self.reel = ClipReel(it["clips"], self.reel_size(), job["duration"], job["fps"])
            self.clip_credits = {
                c.get("credit", ""): self._credit_chip(
                    f"{self.L['photo'] if c.get('kind') == 'image' else self.L['clip']}: {c['credit_short']}")
                for c in it["clips"] if c.get("credit_short")}
        # Rang-Badge
        B = self.BADGE
        badge = rounded_rect((B, B), 54, (*self.c1, 255))
        grad = gradient_fill(rounded_rect((B, B), 54, (255, 255, 255, 255)), self.c1, self.c2, vertical=True)
        paste(badge, grad, (0, 0))
        lab = text_layer(self.L["rank"], font("bold", 30), fill=(10, 12, 28, 200))
        paste(badge, lab, ((B - lab.width) / 2, 26))
        num = text_layer(f"#{it['rank']}", fit_font(f"#{it['rank']}", "black", 132, B - 30, 1)[0], fill=(10, 12, 28, 255))
        paste(badge, num, ((B - num.width) / 2, 62))
        self.badge = badge
        self.badge_shadow = shadow(badge, 22, 160)
        # Texte
        self.value_font = font("black", 96)
        self.value_label = text_layer(it["value_label"].upper(), font("bold", 30), fill=MUTED) if it["value_label"] else None
        # Fakten-Ranking: statt Zahl und Balken die Kernaussage (zweizeilig, Akzentfarbe)
        self.kicker = None
        if it.get("fact") and it.get("kicker"):
            kfont, klines = fit_font(it["kicker"], "bold", 52, CONTENT_W, 3, min_size=34)
            self.kicker = text_layer(klines, kfont, fill=(*self.c1, 255))
        chip_font = font("semibold", 30)
        chips = [f"{label}: {value}" for label, value in it["extras"]]
        if it.get("as_of"):
            chips.append(f"{self.L['as_of']} {it['as_of']}")
        self.chips = [chip(c, chip_font) for c in chips]
        if it.get("compare_chip"):   # belegter Vergleich, z. B. "48× Deutschland"
            self.chips.insert(0, chip(it["compare_chip"], font("bold", 30), fg=(10, 12, 28), bg=(*self.c1, 255)))
        self.confetti = self._confetti() if it["rank"] == 1 else []
        self._backdrop = None

    def _confetti(self):
        rnd = random.Random(7)
        colors = [GOLD, ACCENT, ACCENT2, WHITE, (244, 114, 182)]
        return [(rnd.uniform(0, W), rnd.uniform(-H, 0), rnd.uniform(220, 420), rnd.uniform(0, 6.28),
                 rnd.choice(colors), rnd.uniform(10, 20)) for _ in range(90)]

    @staticmethod
    def _credit_chip(full: str):
        fnt = font("regular", 22)
        text = full
        while fnt.getlength(text + "…") > CONTENT_W - 80 and len(text) > 10:
            text = text[:-1]
        return chip(text if text == full else text.rstrip() + "…", fnt, fg=(230, 230, 240), bg=(0, 0, 0, 150))

    def _card(self, t):
        if self.anim is not None:
            cw, ch = self.card_size
            n = max(cw, ch)
            karte = Image.new("RGBA", (cw, ch), (16, 28, 40, 255))
            bild = self.anim.bild(t, n)
            karte.alpha_composite(bild, (int((cw - n) / 2), int((ch - n) / 2)))
            karte.putalpha(self.card_mask)
            return karte
        if self.reel is not None:
            img = self.reel.frame_at(t)
            if img is not None:
                if img.size != self.card_size:
                    img = img.resize(self.card_size, Image.BILINEAR)
                crop = img.convert("RGBA")
                crop.putalpha(self.card_mask)
                return crop
        if self.photo is None:
            return self.graphic.render(t, self.job["duration"])
        cw, ch = self.card_size
        p = ease_in_out(clamp(t / max(1.0, self.job["duration"])))
        zoom = 1.0 + 0.14 * p
        bw, bh = self.photo.size
        w, h = bw / zoom, bh / zoom
        x = (bw - w) * (0.5 + 0.25 * math.sin(p * math.pi * 0.8 + STYLE.get("pan", -0.4)))
        y = (bh - h) * 0.4
        crop = self.photo.resize((cw, ch), Image.BILINEAR, box=(x, y, x + w, y + h)).convert("RGBA")
        crop.putalpha(self.card_mask)
        return crop

    def frame(self, t):
        if STYLE.get("bg") == "blur" and self._backdrop is None and not self.full:    # Design „blur“: Foto/Clip als Vollbild-Hintergrund
            src = self.photo if self.photo is not None else (self.reel.last if self.reel is not None else None)
            if src is not None:
                self._backdrop = backdrop_from(src)
        f = background(t, self.c1, self.c2, backdrop=self._backdrop)
        if not self.full:                       # Vollbild: Kopfzeile erst über Clip und Schatten
            header(f, self.job, t, self.job["n_items"] - self.item["rank"])
        # Bildkarte (Hereinkommen je Bewegungsprofil)
        pc = ease_out_cubic(progress(t, 0.05, 0.5))
        dx, dy, sc = card_motion(pc)
        credit = self.clip_credits.get(self.reel.credit_at(t)) if self.reel is not None and self.reel.last else self.credit
        if self.full:
            paste_scaled(f, self._card(t), (0, 0), 1 + 0.22 * (1 - pc), opacity=clamp(pc * 1.6))   # Punch-in-Zoom
            paste(f, full_shade(), (0, 0))
            header(f, self.job, t, self.job["n_items"] - self.item["rank"])      # Kopfzeile über dem Schatten
            if credit:
                paste(f, credit, (X0 + self.BADGE + 10, self.CARD_Y - 20), opacity=pc)
        else:
            cy = self.CARD_Y + dy
            paste_scaled(f, self.card_shadow, (X0 - 60 + dx, cy - 50), sc, opacity=pc)
            paste_scaled(f, self._card(t), (X0 + dx, cy), sc, opacity=pc)
            if credit:
                paste(f, credit, (X0 + 18, cy + self.card_size[1] - credit.height - 16), opacity=pc)
        # Rang-Badge springt auf die Ecke
        pb = ease_out_back(progress(t, 0.15, 0.45))
        mode = STYLE.get("badge", "pop")
        if pb > 0:
            B = self.BADGE
            bx, by = X0 + self.BADGE_POS[0], self.CARD_Y + self.BADGE_POS[1]
            if mode == "pop":                                  # springt aus der Ecke auf
                size = max(1, int(B * pb))
                b = self.badge.resize((size, size))
                bx, by = bx + (B - size) / 2, by + (B - size) / 2
            else:                                              # fällt von oben herein / gleitet von links herein
                pm = ease_out_cubic(progress(t, 0.15, 0.45))
                b = self.badge
                bx, by = (bx - (1 - pm) * 320, by) if mode == "slide" else (bx, by - (1 - pb) * 300)
            paste(f, self.badge_shadow, (bx - 44, by - 34), opacity=clamp(pb))
            paste(f, b, (bx, by), opacity=clamp(pb * 1.5) if mode != "pop" else 1.0)
        y = 880 if self.full else self.CARD_Y + self.card_size[1] + 34
        self.texts(f, t, y)
        return self.finish(f, t)

    def texts(self, f, t, y: float, center: bool = False, slide: float = 40, x0: float = X0) -> float:
        """Name, Kernaussage bzw. Wert mit Balken und Info-Chips ab Höhe y (links oder mittig) – gibt das Ende zurück."""
        def at(layer) -> float:
            return x0 + (CONTENT_W - layer.width) / 2 if center else x0

        # Block nie in die Untertitel laufen lassen: erst Info-Chips weglassen (s. u.), dann den Namen kleiner setzen,
        # nur als letztes Mittel den Block nach oben schieben (sonst ragt er in Kreis/Foto/Bild)
        limit = SUB_Y - self.subs.line_height / 2 - 30
        name = self.name
        rest = 0
        if self.item.get("fact"):
            rest = (self.kicker.height + 24) if self.kicker is not None else 0
        else:
            rest = (self.value_label.height if self.value_label else 0) + self.value_font.size + 30 + 44
        if y + name.height + 6 + rest > limit:
            key = (int(y), len(self.item["name"]))
            cache = self.__dict__.setdefault("_small_names", {})
            if key not in cache:
                size = getattr(self.name_font, "size", 72) - 4
                cache[key] = name
                while size >= 36:
                    fnt, lines = fit_font(self.item["name"], "black", size, CONTENT_W, 3, min_size=size)
                    cand = text_layer(lines, fnt)
                    cache[key] = cand
                    if y + cand.height + 6 + rest <= limit:
                        break
                    size -= 4
            name = cache[key]
        y = min(y, limit - (name.height + 6 + rest))
        pn = ease_out_cubic(progress(t, 0.3, 0.45))
        paste(f, name, (at(name) + (slide * (1 - pn) if slide < 0 else 0), y + (1 - pn) * abs(slide)),
              opacity=pn)
        y += name.height + 6
        # Wert zählt hoch, Balken wächst
        pv = ease_out_cubic(progress(t, 0.5, 1.3))
        if self.item.get("fact"):
            if self.kicker is not None:
                paste(f, self.kicker, (at(self.kicker), y + (1 - pv) * 20), opacity=clamp(pv * 2))
                y += self.kicker.height + 24
        elif self.value_label:
            paste(f, self.value_label, (at(self.value_label), y), opacity=clamp(pv * 3))
            y += self.value_label.height
        if not self.item.get("fact"):
            val = text_layer(self.q.display(self.lang, self.q.value * pv), self.value_font, fill=(*self.c1, 255))
            paste(f, val, (at(val), y - 6), opacity=clamp(pv * 3))
            y += val.height + 4
            if pv > 0:                                   # Spur erst mit dem Wert einblenden
                paste(f, rounded_rect((CONTENT_W, 18), 9, (*TRACK, 255)), (x0, y), opacity=clamp(pv * 3))
            fill_w = CONTENT_W * self.ratio() * pv
            if fill_w > 18:
                bar = gradient_fill(rounded_rect((int(fill_w), 18), 9, (255, 255, 255, 255)), self.c2, self.c1)
                paste(f, bar, (x0, y))
            y += 44
        # Info-Chips (zeilenweise; mittig ausgerichtet, wenn das Format zentriert)
        rows, row, width = [], [], 0
        for c in self.chips:
            if row and width + c.width > CONTENT_W:
                rows.append(row)
                row, width = [], 0
            row.append(c)
            width += c.width + 12
        if row:
            rows.append(row)
        i = 0
        for row in rows:
            if y + row[0].height > SUB_Y - self.subs.line_height / 2 - 24:
                break   # Platz für die Untertitel freihalten
            total = sum(c.width for c in row) + 12 * (len(row) - 1)
            x = x0 + (CONTENT_W - total) / 2 if center else x0
            for c in row:
                pch = ease_out_cubic(progress(t, 0.9 + i * 0.12, 0.35))
                paste(f, c, (x, y + (1 - pch) * 20), opacity=pch)
                x += c.width + 12
                i += 1
            y += row[0].height + 12
        return y

    def finish(self, f, t):
        """Konfetti für Platz 1 und Untertitel – letzter Schritt jedes Formats."""
        # Konfetti für Platz 1
        if self.confetti:
            d = ImageDraw.Draw(f)
            for x0, y0, speed, phase, color, size in self.confetti:
                yy = y0 + speed * t
                if 0 <= yy <= H:
                    xx = x0 + 30 * math.sin(t * 2 + phase)
                    ang = t * 4 + phase
                    dx, dy = size * math.cos(ang), size * 0.5 * math.sin(ang)
                    d.polygon([(xx - dx, yy - dy), (xx + dy, yy - dx * 0.4), (xx + dx, yy + dy), (xx - dy, yy + dx * 0.4)], fill=color)
        self.subs.draw(f, t)
        return f


class OutroScene(Scene):
    def __init__(self, job):
        super().__init__(job)
        out = job["outro"]
        fnt, lines = fit_font(job["title"], "black", 64, CONTENT_W, 2, min_size=40)
        self.title = gradient_fill(text_layer(lines, fnt), WHITE, (200, 220, 255), vertical=True)
        rows = out["rows"]
        # Lange Rankings (bis 30 Plätze): zwei Spalten, sonst würden Zeilen und Schrift zu klein
        self.cols = 1 if len(rows) <= 12 else 2
        self.per_col = max(1, math.ceil(len(rows) / self.cols))
        self.gap = 24 if self.cols > 1 else 0
        self.col_w = (CONTENT_W - self.gap * (self.cols - 1)) // self.cols
        self.row_h = max(44, min(80, int((740 if self.cols == 1 else 800) / self.per_col)))
        size = max(18, min(40, self.row_h - 30))
        name_font = font("semibold", size)
        value_font = font("bold", size)
        self.rows = []
        for rank, name, value in rows:
            c1, _ = rank_colors(rank)
            row = rounded_rect((self.col_w, self.row_h - 10), 22 if self.row_h > 50 else 14, (255, 255, 255, 18))
            d = ImageDraw.Draw(row)
            badge = self.row_h - 26
            d.rounded_rectangle((10, 8, 10 + badge, self.row_h - 18), 14 if badge > 30 else 8, fill=c1)
            num = str(rank)
            nf = font("black", max(12, int(badge * 0.6)))
            d.text((10 + (badge - nf.getlength(num)) / 2, 8 + (badge - sum(nf.getmetrics())) / 2), num, font=nf,
                   fill=(10, 12, 28))
            vw = value_font.getlength(value)
            max_name = self.col_w - self.row_h - vw - 40
            label = name
            while name_font.getlength(label) > max_name and len(label) > 4:
                label = label[:-2]
            if label != name:
                label = label.rstrip() + "…"
            ty = (self.row_h - 10 - sum(name_font.getmetrics())) / 2
            d.text((self.row_h + 6, ty), label, font=name_font, fill=WHITE)
            d.text((self.col_w - vw - 18, ty), value, font=value_font, fill=c1)
            self.rows.append(row)
        src_font = font("regular", 28)
        self.sources = text_layer(wrap(out["sources_line"], src_font, CONTENT_W), src_font, fill=MUTED)
        self.cta = chip(self.L["cta"], font("black", 48), fg=(10, 12, 28), bg=(*ACCENT, 255))
        channel = job.get("channel") or ""
        self.channel = text_layer(channel, font("black", 54), fill=(*WHITE, 255)) if channel else None

    def frame(self, t):
        f = background(t)
        pt = ease_out_cubic(progress(t, 0.0, 0.4))
        paste(f, self.title, (X0, 140 + (1 - pt) * 30), opacity=pt)
        y0 = 160 + self.title.height + 30
        step = min(0.08, 1.6 / max(1, len(self.rows)))      # lange Listen bauen sich schneller auf
        for i, row in enumerate(self.rows):
            col, r = divmod(i, self.per_col)
            pr = ease_out_cubic(progress(t, 0.2 + i * step, 0.35))
            mode = STYLE.get("rows", "right")
            dx = {"right": 120, "left": -120}.get(mode, 0) * (1 - pr)
            dy = 60 * (1 - pr) if mode == "rise" else 0
            paste(f, row, (X0 + col * (self.col_w + self.gap) + dx, y0 + r * self.row_h + dy), opacity=pr)
        y = y0 + self.per_col * self.row_h + 16
        ps = progress(t, 1.0, 0.5)
        paste(f, self.sources, (X0, y), opacity=ps)
        y += self.sources.height + 24
        pc = ease_out_back(progress(t, 1.3, 0.5))
        pulse = 1 + 0.03 * math.sin(t * 5)
        s = max(0.01, pc * pulse)
        cta = self.cta.resize((max(1, int(self.cta.width * s)), max(1, int(self.cta.height * s))))
        cta_y = min(y, SUB_Y - 160)
        paste(f, cta, (X0 + (CONTENT_W - cta.width) / 2, cta_y + (self.cta.height - cta.height) / 2))
        if self.channel is not None and cta_y + self.cta.height + 8 + self.channel.height < SUB_Y - 60:
            paste(f, self.channel, (X0 + (CONTENT_W - self.channel.width) / 2, cta_y + self.cta.height + 8), opacity=pc)
        self.subs.draw(f, t)
        return f


def make_scene(job: dict) -> Scene:
    apply_style(job.get("style"))           # Design je Video (jeder Render-Prozess setzt es selbst)
    from .formats import scene_class        # Format: ganz anderer Bildaufbau je Video

    return scene_class(STYLE.get("format", "karte"), job["kind"])(job)
