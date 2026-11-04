"""Maskottchen-Erzähler „CUDI“: ein freundlicher kleiner Roboter, der beim Sprechen den Mund bewegt und blinzelt.

Kostenlos und offline mit Pillow gezeichnet (eigenes Design). Die Mundöffnung folgt der Lautstärke der Stimme
(nur Sprachspur, nicht die Musik), Blinzeln kommt in unregelmäßigen Abständen, dazu ein leichtes Wippen.
Ergebnis ist eine Video-Ebene mit Transparenz (QuickTime Animation), die beim Rendern unten mittig über das
Video gelegt wird. Abschaltbar über den Auftrag (`maskottchen: false`) bzw. CUDI_MASCOT=0.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 280                     # Breite der Figur im 1080×1920-Video
CANVAS = (SIZE, int(SIZE * 1.18))
MOUTH_LEVELS = 8
BOTTOM_MARGIN = 190            # Abstand zum unteren Rand (Platz für Bedienelemente von TikTok/Shorts)

BODY = (34, 211, 238)          # Türkis wie die Akzentfarbe der Videos
BODY_DARK = (99, 102, 241)
SCREEN = (15, 18, 40)
EYE = (240, 253, 255)
GLOW = (103, 232, 249)
MOUTH = (244, 114, 182)


def enabled(flag: bool | None = None) -> bool:
    """Maskottchen an? Auftragsfeld hat Vorrang, sonst Umgebungsvariable (Standard: an)."""
    if flag is not None:
        return bool(flag)
    return os.environ.get("CUDI_MASCOT", "1") != "0"


# --------------------------------------------------------------------------- Zeichnen

def _gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    w, h = size
    t = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, w, axis=1), "RGB")


def draw(mouth: float, blink: bool, scale: int = 3) -> Image.Image:
    """Eine Figur (RGBA, CANVAS groß). mouth 0..1 = Mundöffnung, blink = Augen zu."""
    w, h = CANVAS[0] * scale, CANVAS[1] * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    s = w / 100                                   # Einheit: 1 % der Breite

    # weicher Schatten unter der Figur
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((22 * s, h - 14 * s, 78 * s, h - 4 * s), fill=(0, 0, 0, 110))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3 * s)))

    d = ImageDraw.Draw(img)
    # Antenne mit leuchtender Kugel (leuchtet beim Sprechen heller)
    d.line((50 * s, 14 * s, 50 * s, 4 * s), fill=BODY_DARK, width=int(2.4 * s))
    glow = int(150 + 105 * min(1.0, mouth * 1.5))
    d.ellipse((45 * s, 0, 55 * s, 10 * s), fill=(*GLOW, 255), outline=(*BODY_DARK, 255), width=int(1.2 * s))
    halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((41 * s, -4 * s, 59 * s, 14 * s), fill=(*GLOW, glow // 3))
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(2.5 * s)))
    d = ImageDraw.Draw(img)

    # Kopf: abgerundetes Quadrat mit Farbverlauf
    head = (6 * s, 13 * s, 94 * s, 101 * s)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(head, radius=30 * s, fill=255)
    img.paste(_gradient((w, h), BODY, BODY_DARK), (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(head, radius=30 * s, outline=(255, 255, 255, 90), width=int(1.4 * s))
    # Ohren / Lautsprecher
    for x0 in (1 * s, 93 * s):
        d.rounded_rectangle((x0, 46 * s, x0 + 6 * s, 66 * s), radius=3 * s, fill=(*BODY_DARK, 255))

    # Gesicht (dunkler Bildschirm)
    face = (16 * s, 25 * s, 84 * s, 89 * s)
    d.rounded_rectangle(face, radius=20 * s, fill=(*SCREEN, 255))

    # Augen
    for cx in (36 * s, 64 * s):
        cy = 49 * s
        if blink:
            d.rounded_rectangle((cx - 8 * s, cy - 1.2 * s, cx + 8 * s, cy + 1.2 * s), radius=1.2 * s, fill=(*EYE, 255))
        else:
            d.ellipse((cx - 8 * s, cy - 10 * s, cx + 8 * s, cy + 10 * s), fill=(*EYE, 255))
            d.ellipse((cx - 4.2 * s, cy - 4 * s, cx + 4.2 * s, cy + 5.5 * s), fill=(*GLOW, 255))
            d.ellipse((cx - 2.2 * s, cy - 1.5 * s, cx + 2.2 * s, cy + 3 * s), fill=(*SCREEN, 255))
            d.ellipse((cx + 1 * s, cy - 6.5 * s, cx + 4 * s, cy - 3.5 * s), fill=(255, 255, 255, 255))

    # Wangen
    for cx in (25 * s, 75 * s):
        d.ellipse((cx - 5 * s, 64 * s, cx + 5 * s, 69 * s), fill=(*MOUTH, 90))

    # Mund: geschlossen ein Lächeln, offen ein rundes „o“ mit Zunge
    cx, top = 50 * s, 69 * s
    if mouth < 0.08:
        d.arc((40 * s, 62 * s, 60 * s, 76 * s), start=20, end=160, fill=(*EYE, 255), width=int(2.2 * s))
    else:
        open_h = (3 + 13 * mouth) * s
        half_w = (7 + 3 * mouth) * s
        d.rounded_rectangle((cx - half_w, top, cx + half_w, top + open_h), radius=min(open_h, 2 * half_w) / 2,
                            fill=(60, 10, 40, 255), outline=(*EYE, 255), width=int(1.4 * s))
        if open_h > 7 * s:
            d.ellipse((cx - half_w * 0.6, top + open_h * 0.55, cx + half_w * 0.6, top + open_h - 1.4 * s),
                      fill=(*MOUTH, 255))
    return img.resize(CANVAS, Image.LANCZOS)


# --------------------------------------------------------------------------- Bewegung

def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as f:
        rate, n, width, channels = f.getframerate(), f.getnframes(), f.getsampwidth(), f.getnchannels()
        raw = f.readframes(n)
    data = np.frombuffer(raw, dtype={1: np.uint8, 2: np.int16, 4: np.int32}[width]).astype(np.float32)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data / float(2 ** (8 * width - 1)), rate


def mouth_levels(samples: np.ndarray, rate: int, fps: int, frames: int) -> list[int]:
    """Mundöffnung je Bild (0..MOUTH_LEVELS-1) aus der Lautstärke der Sprachspur."""
    hop = rate / fps
    rms = np.zeros(frames, dtype=np.float32)
    for i in range(frames):
        a, b = int(i * hop), int((i + 1) * hop)
        chunk = samples[a:b]
        rms[i] = float(np.sqrt(np.mean(chunk * chunk))) if len(chunk) else 0.0
    loud = float(np.percentile(rms[rms > 0], 95)) if np.any(rms > 0) else 0.0
    if loud <= 1e-6:
        return [0] * frames
    level = np.clip(rms / loud, 0, 1)
    level[level < 0.12] = 0                       # Atempausen: Mund zu
    smooth, out = 0.0, []
    for v in level:                               # schnell auf, etwas langsamer zu – wirkt natürlich
        smooth = v if v > smooth else smooth * 0.55 + v * 0.45
        out.append(int(round(smooth * (MOUTH_LEVELS - 1))))
    return out


def blink_frames(frames: int, fps: int, seed: int = 7) -> set[int]:
    rnd, out, t = random.Random(seed), set(), 1.2
    while t * fps < frames:
        start = int(t * fps)
        out.update(range(start, start + max(2, fps // 8)))
        t += rnd.uniform(2.4, 5.0)
    return out


def render_layer(voice_wav: Path, duration: float, fps: int, out: Path, seed: int = 7) -> Path:
    """Video-Ebene mit Transparenz: CUDI spricht synchron zur Sprachspur."""
    samples, rate = _read_wav(voice_wav)
    frames = max(1, int(round(duration * fps)))
    levels = mouth_levels(samples, rate, fps, frames)
    blinks = blink_frames(frames, fps, seed)
    sprites = {(m, b): draw(m / (MOUTH_LEVELS - 1), b) for m in range(MOUTH_LEVELS) for b in (False, True)}
    w, h = CANVAS[0], CANVAS[1] + 16               # Platz zum Wippen
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(frames):
            frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            bob = int(round(8 + 6 * math.sin(i / fps * 2.2) + (levels[i] > 0) * -2))
            frame.alpha_composite(sprites[(levels[i], i in blinks)], (0, bob))
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Maskottchen-Ebene ließ sich nicht erzeugen")
    return out


def overlay_position(video_w: int = 1080, video_h: int = 1920) -> tuple[int, int]:
    return (video_w - CANVAS[0]) // 2, video_h - CANVAS[1] - 16 - BOTTOM_MARGIN
