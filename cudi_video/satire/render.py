"""Satire rendern: eigener Zeitungs-/Cartoon-Look (nur Bausteine importiert, keine Änderung an `render/*`).

Look: der ECHTE Teil auf Zeitungspapier (nüchtern, Serifen, grünes „ECHT“-Abzeichen), der satirische Teil in Comic-Gelb
(Halbton-Punkte, Sprechblasen-Karte, rotes „ERFUNDEN“-Band), die Pointe auf rotem Strahlenhintergrund. In JEDEM Bild steht
oben links der Stempel „SATIRE“. Musik: selbst erzeugt, leicht/verspielt („pluck“); Stimme: nüchtern im Faktenteil,
verschmitzt-flott im satirischen Teil (Profil `tts.SPEECH_PROFILES["satire"]`).
"""

from __future__ import annotations

import functools
import math
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .. import config, tts
from ..render import audio, theme as T, video
from ..render.manuskript import align_tokens
from . import STRINGS

W, H = config.WIDTH, config.HEIGHT
PAPER, INK, RED, YELLOW, WHITE = (240, 232, 212), (26, 24, 22), (214, 40, 40), (255, 211, 31), (255, 255, 255)
GREEN, GREY = (36, 128, 66), (110, 104, 92)
LEAD, TAIL = 0.6, 0.8
MUSIC_STYLE = "pluck"
STAMP_POS = (44, 176)                 # oben links, unterhalb der Plattform-Leiste (Safe-Zone ab y 170)
COVER_SAFE = (170, 1500)

FONT_FILES = {"anton": "Anton-Regular.ttf", "serif": "PlayfairDisplay-Black.ttf", "pop": "Poppins-ExtraBold.ttf",
              "popb": "Poppins-Bold.ttf", "sans": "Inter-SemiBold.ttf", "hand": "Caveat-Bold.ttf"}


@functools.lru_cache(maxsize=64)
def sfont(kind: str, size: int) -> ImageFont.FreeTypeFont:
    path = T._font_index().get(FONT_FILES[kind].lower())
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def ease_out(x: float) -> float:
    return 1 - (1 - clamp(x)) ** 3


def pop(x: float) -> float:
    """Überschwinger (0 -> 1.12 -> 1) für Stempel und Karten."""
    x = clamp(x)
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2 if x < 1 else 1.0


def paste(f: Image.Image, layer: Image.Image, xy, opacity: float = 1.0) -> None:
    if opacity <= 0.003:
        return
    mask = layer.getchannel("A")
    if opacity < 0.997:
        mask = mask.point(lambda v: int(v * opacity))
    f.paste(layer.convert("RGB"), (int(round(xy[0])), int(round(xy[1]))), mask)


# --------------------------------------------------------------------------- Hintergründe

@functools.lru_cache(maxsize=1)
def bg_paper() -> Image.Image:
    rng = np.random.default_rng(7)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.clip(np.hypot((xs - W / 2) / (W * 0.8), (ys - H / 2) / (H * 0.7)), 0, 1) ** 2
    img = np.array(PAPER, np.float32)[None, None, :] * (1 - 0.14 * v[:, :, None])
    img += rng.normal(0, 2.6, (H, W, 1)).astype(np.float32)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(im)
    d.rectangle((34, 34, W - 35, H - 35), outline=INK, width=3)
    d.rectangle((44, 44, W - 45, H - 45), outline=INK, width=1)
    return im


@functools.lru_cache(maxsize=1)
def bg_comic() -> Image.Image:
    im = Image.new("RGB", (W, H), YELLOW)
    d = ImageDraw.Draw(im)
    step = 38
    for gy in range(-1, H // step + 2):
        for gx in range(-1, W // step + 2):
            x, y = gx * step + (step / 2 if gy % 2 else 0), gy * step
            near = min(math.hypot(x, H - y), math.hypot(W - x, y)) / (W * 0.95)
            r = 17 * clamp(1 - near) ** 1.1
            if r > 1.2:
                d.ellipse((x - r, y - r, x + r, y + r), fill=(245, 160, 0))
    return im


@functools.lru_cache(maxsize=1)
def bg_burst() -> Image.Image:
    im = Image.new("RGB", (W, H), RED)
    d = ImageDraw.Draw(im)
    cx, cy, n = W / 2, H * 0.47, 28
    for i in range(0, n, 2):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d.polygon([(cx, cy), (cx + 2600 * math.cos(a0), cy + 2600 * math.sin(a0)),
                   (cx + 2600 * math.cos(a1), cy + 2600 * math.sin(a1))], fill=(186, 26, 26))
    return im


# --------------------------------------------------------------------------- Bausteine

def stamp(text: str, size: int, angle: float, pad: int = 26) -> Image.Image:
    """Roter Stempel mit weißer Fläche und schwarzem Rand (auf jedem Hintergrund lesbar)."""
    fnt = sfont("anton", size)
    box = fnt.getbbox(text)
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    im = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((3, 3, w + 8, h + 8), radius=18, fill=(0, 0, 0, 255))
    d.rounded_rectangle((8, 8, w + 3, h + 3), radius=14, fill=(255, 255, 255, 240), outline=RED, width=max(6, size // 14))
    d.text((6 + w / 2 - (box[0] + box[2]) / 2 + 3, 6 + h / 2 - (box[1] + box[3]) / 2 + 3), text, font=fnt, fill=RED)
    return im.rotate(angle, resample=Image.BICUBIC, expand=True)


@functools.lru_cache(maxsize=4)
def corner_stamp() -> Image.Image:
    return stamp("SATIRE", 68, 6)


def star(r_out: float, r_in: float, n: int, fill, outline=INK, width: int = 8) -> Image.Image:
    size = int(r_out * 2 + 2 * width + 4)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size / 2
    pts = [(c + (r_out if i % 2 == 0 else r_in) * math.cos(math.pi * i / n - math.pi / 2),
            c + (r_out if i % 2 == 0 else r_in) * math.sin(math.pi * i / n - math.pi / 2)) for i in range(2 * n)]
    ImageDraw.Draw(im).polygon(pts, fill=fill, outline=outline, width=width)
    return im


def label_band(text: str, fill, fg=WHITE, size: int = 54, angle: float = -3.0) -> Image.Image:
    fnt = sfont("anton", size)
    box = fnt.getbbox(text)
    w, h = box[2] - box[0] + 90, box[3] - box[1] + 46
    im = Image.new("RGBA", (w + 14, h + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((12, 12, w + 11, h + 11), fill=(0, 0, 0, 255))
    d.rectangle((2, 2, w, h), fill=fill, outline=INK, width=5)
    d.text((1 + w / 2 - (box[0] + box[2]) / 2, 1 + h / 2 - (box[1] + box[3]) / 2), text, font=fnt, fill=fg)
    return im.rotate(angle, resample=Image.BICUBIC, expand=True)


def badge_real(text: str) -> Image.Image:
    """Grünes Abzeichen mit Haken (selbst gezeichnet) und „ECHT“."""
    fnt = sfont("popb", 40)
    tw = int(fnt.getlength(text))
    w, h = tw + 120, 76
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=38, fill=GREEN)
    d.line([(26, 40), (38, 52), (58, 26)], fill=WHITE, width=8, joint="curve")
    d.text((76, h / 2 + 1), text, font=fnt, fill=WHITE, anchor="lm")
    return im


def small(text: str, kind: str, size: int, color, max_w: int = 900, align: str = "center") -> Image.Image:
    fnt = sfont(kind, size)
    while fnt.getlength(text) > max_w and size > 22:
        size -= 2
        fnt = sfont(kind, size)
    im = Image.new("RGBA", (int(fnt.getlength(text)) + 8, int(size * 1.5)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4, 2), text, font=fnt, fill=color)
    return im


class Words:
    """Satz Wort für Wort zur Stimme einblenden (Zeilenumbruch steht fest, Schrift schrumpft bei langem Text)."""

    def __init__(self, text: str, words: list[dict], offset: float, kind: str, size: int, color, max_w: int = 900,
                 max_h: int = 700, stroke: int = 0, stroke_color=INK, line: float = 1.22, min_size: int = 34):
        self.offset, self.text, self.words = offset, text, words
        self.kind, self.color, self.max_w, self.stroke, self.stroke_color, self.line = kind, color, max_w, stroke, stroke_color, line
        self._build(size)
        while self.height > max_h and size > min_size:
            size -= 4
            self._build(size)

    def _build(self, size: int) -> None:
        fnt = sfont(self.kind, size)
        self.tokens = self.text.split()
        self.starts = align_tokens(self.text, self.words)
        space = fnt.getlength(" ") + self.stroke
        widths = [fnt.getlength(t) for t in self.tokens]
        lines, cur, cur_w = [], [], 0.0
        for i, w in enumerate(widths):
            if cur and cur_w + space + w > self.max_w:
                lines.append(cur)
                cur, cur_w = [], 0.0
            cur_w += (space if cur else 0) + w
            cur.append(i)
        if cur:
            lines.append(cur)
        self.line_h = int(size * self.line)
        self.layers = []
        pad = self.stroke + 6
        for li, idxs in enumerate(lines):
            total = sum(widths[i] for i in idxs) + space * (len(idxs) - 1)
            x = (W - total) / 2
            for i in idxs:
                tok = self.tokens[i]
                im = Image.new("RGBA", (int(widths[i]) + 2 * pad, int(size * 1.5) + 2 * pad), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((pad, pad), tok, font=fnt, fill=self.color, stroke_width=self.stroke,
                                        stroke_fill=self.stroke_color)
                self.layers.append((im, x - pad, li * self.line_h - pad))
                x += widths[i] + space
        self.height = len(lines) * self.line_h + int(size * 0.3)

    def draw(self, f: Image.Image, t: float, y: float, fade: float = 1.0) -> None:
        ts = t - self.offset
        for (layer, x, dy), start in zip(self.layers, self.starts):
            a = ease_out((ts - start + 0.05) / 0.22)
            if a > 0:
                paste(f, layer, (x, y + dy + (1 - a) * 9), opacity=a * fade)


def rounded_card(w: int, h: int, fill, outline=INK, width: int = 8, shadow: int = 14, radius: int = 34) -> Image.Image:
    im = Image.new("RGBA", (w + shadow + 4, h + shadow + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((shadow, shadow, w + shadow, h + shadow), radius=radius, fill=(0, 0, 0, 255))
    d.rounded_rectangle((0, 0, w, h), radius=radius, fill=fill, outline=outline, width=width)
    return im


# --------------------------------------------------------------------------- Szenen

class Scene:
    def __init__(self, job: dict):
        self.job = job
        self.dur = job["duration"]
        self.s = STRINGS[job["lang"]]

    def fade(self, t: float) -> float:
        return clamp(min(t / 0.18, (self.dur - t) / 0.18))

    def base(self, t: float) -> Image.Image:
        raise NotImplementedError

    def content(self, f: Image.Image, t: float, fade: float) -> None:
        raise NotImplementedError

    def anim_unter(self, f: Image.Image, t: float, y: float, fade: float) -> None:
        """Eigene Animation (Studio) unter dem Text – zeigt, was gerade gesagt wird."""
        if not self.job.get("animation"):
            return
        if not hasattr(self, "_anim"):
            from ..animation import Bild
            self._anim = Bild(self.job["animation"], self.job["text"], self.job["words"], self.job["lead"], INK, RED, self.job["index"])
        size = int(min(560, 1660 - y))
        if size >= 280:
            paste(f, self._anim.bild(t, size), ((W - size) / 2, y), opacity=fade)

    def frame(self, t: float) -> Image.Image:
        f = self.base(t).copy()
        self.content(f, t, 1.0 if t < self.dur - 0.18 else self.fade(t))
        paste(f, corner_stamp(), STAMP_POS)                    # Kennzeichnung in JEDEM Bild
        return f


class IntroScene(Scene):
    def __init__(self, job):
        super().__init__(job)
        self.big = stamp("SATIRE", 230, -8, 40)
        self.text = Words(job["text"], job["words"], job["lead"], "serif", 58, INK, max_h=420)

    def base(self, t):
        return bg_paper()

    def content(self, f, t, fade):
        k = pop(t / 0.4) if t < 0.4 else 1.0
        im = self.big if t > 0.45 else self.big.resize((max(8, int(self.big.width * (0.4 + 0.6 * k) * (2.2 - 1.2 * ease_out(t / 0.35)))),
                              max(8, int(self.big.height * (0.4 + 0.6 * k) * (2.2 - 1.2 * ease_out(t / 0.35))))))
        shake = math.sin(t * 90) * 6 * clamp(1 - (t - 0.3) / 0.25) if 0.3 < t < 0.55 else 0
        paste(f, im, ((W - im.width) / 2 + shake, 700 - im.height / 2), opacity=clamp(t / 0.12))
        self.text.draw(f, t, 1060, fade)


class FaktScene(Scene):
    def __init__(self, job):
        super().__init__(job)
        self.badge = badge_real(self.s["echt"])
        self.kicker = small(self.s["kern"], "serif", 38, INK, 700)
        self.text = Words(job["text"], job["words"], job["lead"], "serif", 62, INK, max_h=640)
        src = " · ".join(job.get("quellen") or [])
        self.src = small(f"{self.s['sources']}: {src}", "sans", 32, GREY, 900) if src else None

    def base(self, t):
        return bg_paper()

    def content(self, f, t, fade):
        a = clamp(t / 0.3)
        paste(f, self.badge, ((W - self.badge.width) / 2, 330 + (1 - ease_out(a)) * -20), opacity=a)
        paste(f, self.kicker, ((W - self.kicker.width) / 2, 430), opacity=a)
        d = ImageDraw.Draw(f)
        d.line([(120, 500), (W - 120, 500)], fill=INK, width=4)
        d.line([(120, 510), (W - 120, 510)], fill=INK, width=1)
        self.text.draw(f, t, 590, fade)
        if self.src is not None:
            paste(f, self.src, ((W - self.src.width) / 2, 590 + self.text.height + 70), opacity=clamp((t - 0.8) / 0.5) * fade)
        self.anim_unter(f, t, 590 + self.text.height + (140 if self.src is not None else 60), fade)


class SatireScene(Scene):
    def __init__(self, job):
        super().__init__(job)
        self.band = label_band(self.s["erfunden"], RED, WHITE, 54, -3)
        self.text = Words(job["text"], job["words"], job["lead"], "pop", 60, INK, max_w=800, max_h=620)
        self.card = rounded_card(880, self.text.height + 90, WHITE)
        self.star1, self.star2 = star(95, 50, 9, RED), star(70, 36, 8, WHITE)

    def base(self, t):
        return bg_comic()

    def content(self, f, t, fade):
        k = pop(t / 0.35)
        band = self.band.resize((max(8, int(self.band.width * k)), max(8, int(self.band.height * k))))
        paste(f, band, ((W - band.width) / 2, 420 - band.height / 2))
        ch = self.card.height
        card = self.card.resize((max(8, int(self.card.width * (0.7 + 0.3 * k))), max(8, int(ch * (0.7 + 0.3 * k)))))
        top = 640
        paste(f, card, ((W - card.width) / 2 - 7, top + (ch - card.height) / 2), opacity=clamp(t / 0.15) * fade)
        self.text.draw(f, t, top + 58, fade)
        self.anim_unter(f, t, top + ch + 40, fade)
        for img, pos, speed in ((self.star1, (W - 190, 1480), 25), (self.star2, (90, 1560), -35)):
            paste(f, img.rotate(t * speed, resample=Image.BICUBIC), pos, opacity=ease_out(t / 0.5) * fade)


class PointeScene(Scene):
    def __init__(self, job):
        super().__init__(job)
        self.label = label_band(self.s["pointe"], INK, YELLOW, 50, 3)
        self.text = Words(job["text"], job["words"], job["lead"], "anton", 92, WHITE, max_w=900, max_h=760, stroke=7,
                          stroke_color=INK, line=1.18, min_size=50)

    def base(self, t):
        return bg_burst()

    def content(self, f, t, fade):
        k = pop(t / 0.35)
        band = self.label.resize((max(8, int(self.label.width * k)), max(8, int(self.label.height * k))))
        paste(f, band, ((W - band.width) / 2, 520 - band.height / 2))
        self.text.draw(f, t, 680 + (1 - ease_out(t / 0.5)) * 25, fade)


class OutroScene(Scene):
    def __init__(self, job):
        super().__init__(job)
        word = "DAS WAR SATIRE" if job["lang"] == "de" else "THAT WAS SATIRE"
        self.big = stamp(word, 120, -5, 36)
        self.text = Words(job["text"], job["words"], job["lead"], "serif", 46, INK, max_h=520)

    def base(self, t):
        return bg_paper()

    def content(self, f, t, fade):
        k = pop(t / 0.4)
        im = self.big.resize((max(8, int(self.big.width * k)), max(8, int(self.big.height * k))))
        paste(f, im, ((W - im.width) / 2, 700 - im.height / 2), opacity=clamp(t / 0.12))
        self.text.draw(f, t, 960, fade)


SCENES = {"intro": IntroScene, "fakt": FaktScene, "satire": SatireScene, "pointe": PointeScene, "outro": OutroScene}


def make_scene(job: dict) -> Scene:
    return SCENES[job["typ"]](job)


def render_frame(job: dict, t: float, path: Path) -> None:
    make_scene(job).frame(t).convert("RGB").save(path, quality=92)


def render_part(job: dict) -> str:
    """Eigener Prozess: Szene Bild für Bild an ffmpeg übergeben."""
    scene = make_scene(job)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(job["fps"]),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-g", str(job["fps"] * 2),
           job["out"]]
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


# --------------------------------------------------------------------------- Cover

def make_cover(path: Path, titel: str, lang: str) -> dict:
    """Cover 1080×1920: Comic-Gelb, großer Stempel „SATIRE“, Titel, Hinweis „Echte Meldung – satirisch betrachtet“.
    Rückgabe: die auf dem Cover stehenden Texte (für die Endabnahme)."""
    im = bg_comic().copy()
    core = titel.split(":", 1)[1].strip() if ":" in titel else titel
    big = stamp("SATIRE", 300, -7, 44)
    paste(im, big, ((W - big.width) / 2, 330))
    words = Words(core, [], 0, "anton", 112, INK, max_w=900, max_h=520, stroke=0, line=1.12, min_size=56)
    card = rounded_card(920, words.height + 90, WHITE)
    top = 330 + big.height + 70
    paste(im, card, ((W - card.width) / 2 - 7, top))
    for layer, x, dy in words.layers:
        paste(im, layer, (x, top + 48 + dy))
    sub = small(STRINGS[lang]["cover"], "popb", 40, INK, 900)
    paste(im, sub, ((W - sub.width) / 2, min(COVER_SAFE[1] - 60, top + words.height + 150)))
    im.convert("RGB").save(path, quality=92)
    return {"headline": "SATIRE", "titel": core, "hinweis": STRINGS[lang]["cover"]}


# --------------------------------------------------------------------------- Video

def _rate_pitch(role: str) -> tuple[str, str]:
    rate, pitch, _ = tts.SPEECH_PROFILES["satire"]["rollen"][role]
    return f"{rate:+d}%", f"{pitch:+d}Hz"


def render_satire(script: dict, out_dir: Path | None = None, progress=None, musik: bool = True) -> dict:
    """Skript (aus `satire.baue_skript`) -> Video + Cover. Gibt {"video", "cover", "duration", "folder", "qa"} zurück."""
    from ..erklaer.render import build_audio, voice_name
    from ..render import cover as cover_mod

    out_dir = out_dir or config.new_output_folder(script["id"])
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    lang, scenes = script["sprache"], script["szenen"]
    voiced: list = [None] * len(scenes)
    for role in ("fakt", "satire", "pointe"):                  # je Ton eine Stimm-Einstellung (nüchtern / verschmitzt / Pointe)
        idx = [i for i, sz in enumerate(scenes) if sz["ton"] == role]
        if not idx:
            continue
        rate, pitch = _rate_pitch(role)
        res = tts.voice_texts([scenes[i]["text"] for i in idx], work / f"audio_{role}", voice_name(lang), rate, pitch)
        for i, r in zip(idx, res):
            voiced[i] = r
    jobs = []
    for i, (sz, (wav, words, dur)) in enumerate(zip(scenes, voiced)):
        frames = int(round((LEAD + dur + TAIL) * config.FPS))
        jobs.append({"index": i, "typ": sz["typ"], "lang": lang, "text": sz["text"], "words": words, "lead": LEAD,
                     "voice_dur": dur, "frames": frames, "duration": frames / config.FPS, "fps": config.FPS,
                     "voice_path": str(wav), "quellen": sz.get("quellen") or [], "animation": sz.get("animation"), "out": str(work / f"part_{i:02d}.mp4")})
    done = 0
    with ProcessPoolExecutor(max_workers=config.RENDER_WORKERS) as pool:
        for _ in pool.map(render_part, jobs):
            done += 1
            if progress:
                progress(done / len(jobs))
    concat = work / "parts.txt"
    concat.write_text("".join(f"file '{Path(j['out']).name}'\n" for j in jobs), "utf-8")
    silent = work / "video_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy",
                    str(silent)], check=True)
    cover = out_dir / f"{script['id']}_cover.jpg"
    cover_texts = make_cover(cover, script["titel"], lang)
    stamped = work / "mit_cover.mp4"
    if cover_mod.stamp_first_frame(silent, cover, stamped):    # Cover als erstes Frame – VOR dem Ton (der Stempel gibt nur Bild aus)
        silent = stamped
    audio_file = work / "audio.wav"
    build_audio(jobs, audio_file, music_style=MUSIC_STYLE if (musik and audio.enabled()) else None, seed_key=script["id"])
    final = out_dir / f"{script['id']}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio_file), "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(video.SAMPLE_RATE), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
    from .. import qa

    return {"video": final.name, "cover": cover.name, "duration": round(sum(j["duration"] for j in jobs), 1),
            "folder": str(out_dir), "qa": qa.safe_check(final, "erklaer", config.STORY_MAX_SECONDS), "cover_texte": cover_texts}
