"""Szenen des Videos. Jede Szene liefert für einen Zeitpunkt t (Sekunden) ein Bild."""

from __future__ import annotations

import math
import random
import re

from PIL import Image, ImageDraw, ImageOps

from ..units import quantity
from .theme import (
    ACCENT, ACCENT2, CARD, CONTENT_W, GOLD, H, MUTED, SUB_Y, TRACK, W, WHITE, X0,
    background, clamp, cover_crop, ease_in_out, ease_out_back, ease_out_cubic, fit_font, font,
    gradient_fill, paste, progress, rank_colors, rounded_mask, rounded_rect, shadow, text_layer, wrap,
)

LABELS = {
    "de": {"rank": "PLATZ", "top": "TOP", "photo": "Foto", "as_of": "Stand", "sources": "Quellen", "src_n": "{n} Quellen",
           "mystery": "Platz 1", "cta": "Folgen für mehr Rankings!"},
    "en": {"rank": "RANK", "top": "TOP", "photo": "Photo", "as_of": "As of", "sources": "Sources", "src_n": "{n} sources",
           "mystery": "Number 1", "cta": "Follow for more rankings!"},
}


# --------------------------------------------------------------------------- Untertitel

class Subtitles:
    """Karaoke-Untertitel: kurze Wortgruppen, aktives Wort farbig hinterlegt."""

    MAX_CHARS = 20
    MAX_WORDS = 4

    def __init__(self, words: list[dict], text: str, offset: float, highlight=ACCENT):
        self.highlight = highlight
        self.font = font("black", 66)
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
                if idx == wi:
                    d.rounded_rectangle((x - 12, y - 4, x + wl + 12, y + ascent + descent + 4), 16, fill=(*self.highlight, 255))
                    d.text((x, y), word, font=fnt, fill=(10, 12, 28))
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
                y = SUB_Y - img.height / 2 + (1 - pop) * 18
                paste(frame, img, (X0, y), opacity=clamp(pop * 1.4))
                return


# --------------------------------------------------------------------------- Bausteine

def header(frame, job, t, current_index: int | None):
    """Videotitel klein + Countdown-Fortschritt."""
    title = job["_header_title"]
    paste(frame, title, (X0, 112))
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


def placeholder_card(size, name: str, c1, c2) -> Image.Image:
    """Grafische Karte, wenn kein frei lizenziertes Bild verfügbar ist."""
    card = rounded_rect(size, 36, (*CARD, 255))
    grad = gradient_fill(rounded_rect(size, 36, (255, 255, 255, 60)), c1, c2)
    paste(card, grad, (0, 0), 0.55)
    d = ImageDraw.Draw(card)
    for i in range(-size[1], size[0], 46):  # diagonale Streifen
        d.line((i, size[1], i + size[1], 0), fill=(255, 255, 255, 14), width=14)
    initials = "".join(w[0] for w in re.findall(r"[\wÄÖÜäöü]+", name)[:2]).upper() or "?"
    fnt = font("black", 300)
    layer = text_layer(initials, fnt, fill=(255, 255, 255, 70))
    paste(card, layer, ((size[0] - layer.width) / 2, (size[1] - layer.height) / 2 - 20))
    return card


# --------------------------------------------------------------------------- Szenen

class Scene:
    def __init__(self, job: dict):
        self.job = job
        self.lang = job["lang"]
        self.L = LABELS[self.lang]
        self.lead = job["lead"]
        c1, c2 = rank_colors(job.get("item", {}).get("rank", 99))
        job["_color1"], job["_color2"] = c1, c2
        self.c1, self.c2 = c1, c2
        fnt, lines = fit_font(job["title"], "semibold", 34, CONTENT_W, 1, min_size=24)
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
        self.top_q = quantity(top["si_value"], top["unit"], top["wanted"])

    def frame(self, t):
        f = background(t)
        p = ease_out_back(progress(t, 0.05, 0.45))
        badge = self.badge.resize((max(1, int(self.badge.width * p)), max(1, int(self.badge.height * p))))
        paste(f, badge, (X0 + (self.badge.width - badge.width) / 2, 250 + (self.badge.height - badge.height) / 2))
        y = 390
        for i, layer in enumerate(self.title_lines):
            pi = ease_out_cubic(progress(t, 0.2 + i * 0.12, 0.45))
            paste(f, layer, (X0 + (1 - pi) * -80, y), opacity=pi)
            y += self.line_h
        cy = max(y + 50, 860)
        pc = ease_out_cubic(progress(t, 0.7, 0.5))
        paste(f, self.card_shadow, (X0 - 60, cy - 60 + (1 - pc) * 60), opacity=pc)
        paste(f, self.card, (X0, cy + (1 - pc) * 60), opacity=pc)
        wobble = math.sin(t * 3) * 6
        paste(f, self.q, (X0 + 60, cy + 40 + wobble), opacity=pc)
        paste(f, self.mystery, (X0 + 300, cy + 90), opacity=pc)
        count = ease_out_cubic(progress(t, 0.9, 1.4))
        value = text_layer(self.top_q.display(self.lang, self.top_q.value * count), font("black", 92), fill=(*GOLD, 255))
        paste(f, value, (X0 + 300, cy + 170), opacity=pc)
        self.subs.draw(f, t)
        return f


class ItemScene(Scene):
    CARD_Y = 230
    CARD_SIZE = (CONTENT_W, 560)

    def __init__(self, job):
        super().__init__(job)
        it = job["item"]
        self.item = it
        self.q = quantity(it["si_value"], it["unit"], it["wanted"])
        self.max_display = job["max_display"]
        # Bild bzw. Platzhalter vorbereiten (Ken-Burns braucht Reserve um den Ausschnitt).
        self.photo = None
        if it.get("image_path"):
            try:
                img = ImageOps.exif_transpose(Image.open(it["image_path"])).convert("RGB")
                cw, ch = self.CARD_SIZE
                self.photo = cover_crop(img, (int(cw * 1.18), int(ch * 1.18)))
            except Exception:
                self.photo = None
        self.placeholder = None if self.photo else placeholder_card(self.CARD_SIZE, it["name"], self.c1, self.c2)
        self.card_mask = rounded_mask(self.CARD_SIZE, 36)
        self.card_shadow = shadow(rounded_rect(self.CARD_SIZE, 36, (0, 0, 0, 255)), 30, 180)
        self.credit = None
        if it.get("credit_short"):
            fnt = font("regular", 22)
            full = f"{self.L['photo']}: {it['credit_short']}"
            text = full
            while fnt.getlength(text + "…") > CONTENT_W - 80 and len(text) > 10:
                text = text[:-1]
            self.credit = chip(text if text == full else text.rstrip() + "…", fnt,
                               fg=(230, 230, 240), bg=(0, 0, 0, 150))
        # Rang-Badge
        badge = rounded_rect((230, 230), 54, (*self.c1, 255))
        grad = gradient_fill(rounded_rect((230, 230), 54, (255, 255, 255, 255)), self.c1, self.c2, vertical=True)
        paste(badge, grad, (0, 0))
        lab = text_layer(self.L["rank"], font("bold", 30), fill=(10, 12, 28, 200))
        paste(badge, lab, ((230 - lab.width) / 2, 26))
        num = text_layer(f"#{it['rank']}", fit_font(f"#{it['rank']}", "black", 132, 200, 1)[0], fill=(10, 12, 28, 255))
        paste(badge, num, ((230 - num.width) / 2, 62))
        self.badge = badge
        self.badge_shadow = shadow(badge, 22, 160)
        # Texte
        fnt, lines = fit_font(it["name"], "black", 88, CONTENT_W, 2, min_size=52)
        self.name = text_layer(lines, fnt)
        self.value_font = font("black", 96)
        self.value_label = text_layer(it["value_label"].upper(), font("bold", 30), fill=MUTED) if it["value_label"] else None
        chip_font = font("semibold", 30)
        chips = [f"{label}: {value}" for label, value in it["extras"]]
        if it.get("as_of"):
            chips.append(f"{self.L['as_of']} {it['as_of']}")
        self.chips = [chip(c, chip_font) for c in chips]
        if it.get("n_sources", 0) >= 2:   # Quellen-Abgleich sichtbar machen
            self.chips.insert(0, chip("✓ " + self.L["src_n"].format(n=it["n_sources"]), font("bold", 30),
                                      fg=(6, 30, 16), bg=(74, 222, 128, 255)))
        self.confetti = self._confetti() if it["rank"] == 1 else []

    def _confetti(self):
        rnd = random.Random(7)
        colors = [GOLD, ACCENT, ACCENT2, WHITE, (244, 114, 182)]
        return [(rnd.uniform(0, W), rnd.uniform(-H, 0), rnd.uniform(220, 420), rnd.uniform(0, 6.28),
                 rnd.choice(colors), rnd.uniform(10, 20)) for _ in range(90)]

    def _card(self, t):
        if self.photo is None:
            return self.placeholder
        cw, ch = self.CARD_SIZE
        p = ease_in_out(clamp(t / max(1.0, self.job["duration"])))
        zoom = 1.0 + 0.14 * p
        bw, bh = self.photo.size
        w, h = bw / zoom, bh / zoom
        x = (bw - w) * (0.5 + 0.25 * math.sin(p * math.pi * 0.8 - 0.4))
        y = (bh - h) * 0.4
        crop = self.photo.resize((cw, ch), Image.BILINEAR, box=(x, y, x + w, y + h)).convert("RGBA")
        crop.putalpha(self.card_mask)
        return crop

    def frame(self, t):
        f = background(t, self.c1, self.c2)
        header(f, self.job, t, self.job["n_items"] - self.item["rank"])
        # Bildkarte
        pc = ease_out_cubic(progress(t, 0.05, 0.5))
        cy = self.CARD_Y + (1 - pc) * 50
        paste(f, self.card_shadow, (X0 - 60, cy - 50), opacity=pc)
        paste(f, self._card(t), (X0, cy), opacity=pc)
        if self.credit:
            paste(f, self.credit, (X0 + 18, cy + self.CARD_SIZE[1] - self.credit.height - 16), opacity=pc)
        # Rang-Badge springt auf die Ecke
        pb = ease_out_back(progress(t, 0.15, 0.45))
        if pb > 0:
            size = max(1, int(230 * pb))
            b = self.badge.resize((size, size))
            bx, by = X0 - 30 + (230 - size) / 2, self.CARD_Y - 40 + (230 - size) / 2
            paste(f, self.badge_shadow, (bx - 44, by - 34), opacity=clamp(pb))
            paste(f, b, (bx, by))
        # Name
        y = self.CARD_Y + self.CARD_SIZE[1] + 34
        pn = ease_out_cubic(progress(t, 0.3, 0.45))
        paste(f, self.name, (X0, y + (1 - pn) * 40), opacity=pn)
        y += self.name.height + 6
        # Wert zählt hoch, Balken wächst
        pv = ease_out_cubic(progress(t, 0.5, 1.3))
        if self.value_label:
            paste(f, self.value_label, (X0, y), opacity=clamp(pv * 3))
            y += self.value_label.height
        val = text_layer(self.q.display(self.lang, self.q.value * pv), self.value_font, fill=(*self.c1, 255))
        paste(f, val, (X0, y - 6), opacity=clamp(pv * 3))
        y += val.height + 4
        d = ImageDraw.Draw(f)
        d.rounded_rectangle((X0, y, X0 + CONTENT_W, y + 18), 9, fill=TRACK)
        ratio = clamp(abs(self.q.value) / self.max_display if self.max_display else 1.0)
        fill_w = CONTENT_W * ratio * pv
        if fill_w > 18:
            bar = gradient_fill(rounded_rect((int(fill_w), 18), 9, (255, 255, 255, 255)), self.c2, self.c1)
            paste(f, bar, (X0, y))
        y += 44
        # Info-Chips
        x = X0
        for i, c in enumerate(self.chips):
            pch = ease_out_cubic(progress(t, 0.9 + i * 0.12, 0.35))
            if x + c.width > X0 + CONTENT_W:
                x = X0
                y += c.height + 12
            if y + c.height > SUB_Y - 70:
                break
            paste(f, c, (x, y + (1 - pch) * 20), opacity=pch)
            x += c.width + 12
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
        self.row_h = min(80, int(740 / max(1, len(rows))))
        name_font = font("semibold", min(40, self.row_h - 30))
        value_font = font("bold", min(40, self.row_h - 30))
        self.rows = []
        for rank, name, value in rows:
            c1, _ = rank_colors(rank)
            row = rounded_rect((CONTENT_W, self.row_h - 10), 22, (255, 255, 255, 18))
            d = ImageDraw.Draw(row)
            d.rounded_rectangle((10, 8, 10 + self.row_h - 26, self.row_h - 18), 14, fill=c1)
            num = str(rank)
            nf = font("black", int((self.row_h - 26) * 0.6))
            d.text((10 + (self.row_h - 26 - nf.getlength(num)) / 2, 8 + (self.row_h - 26) * 0.17), num, font=nf, fill=(10, 12, 28))
            vw = value_font.getlength(value)
            max_name = CONTENT_W - self.row_h - vw - 60
            label = name
            while name_font.getlength(label) > max_name and len(label) > 4:
                label = label[:-2]
            if label != name:
                label = label.rstrip() + "…"
            ty = (self.row_h - 10 - sum(name_font.getmetrics())) / 2
            d.text((self.row_h + 6, ty), label, font=name_font, fill=WHITE)
            d.text((CONTENT_W - vw - 24, ty), value, font=value_font, fill=c1)
            self.rows.append(row)
        src_font = font("regular", 28)
        self.sources = text_layer(wrap(out["sources_line"], src_font, CONTENT_W), src_font, fill=MUTED)
        self.cta = chip(self.L["cta"], font("black", 48), fg=(10, 12, 28), bg=(*ACCENT, 255))

    def frame(self, t):
        f = background(t)
        pt = ease_out_cubic(progress(t, 0.0, 0.4))
        paste(f, self.title, (X0, 140 + (1 - pt) * 30), opacity=pt)
        y = 160 + self.title.height + 30
        for i, row in enumerate(self.rows):
            pr = ease_out_cubic(progress(t, 0.2 + i * 0.08, 0.35))
            paste(f, row, (X0 + (1 - pr) * 120, y), opacity=pr)
            y += self.row_h
        y += 16
        ps = progress(t, 1.0, 0.5)
        paste(f, self.sources, (X0, y), opacity=ps)
        y += self.sources.height + 24
        pc = ease_out_back(progress(t, 1.3, 0.5))
        pulse = 1 + 0.03 * math.sin(t * 5)
        s = max(0.01, pc * pulse)
        cta = self.cta.resize((max(1, int(self.cta.width * s)), max(1, int(self.cta.height * s))))
        paste(f, cta, (X0 + (CONTENT_W - cta.width) / 2, min(y, SUB_Y - 160) + (self.cta.height - cta.height) / 2))
        self.subs.draw(f, t)
        return f


def make_scene(job: dict) -> Scene:
    return {"intro": IntroScene, "item": ItemScene, "outro": OutroScene}[job["kind"]](job)
