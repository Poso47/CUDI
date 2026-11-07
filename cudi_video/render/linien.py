"""Linien-Animationen für den Stil „manuskript“ und das Erklärvideo (alles prozedural mit PIL, geglättet).

Jede Grafik zeichnet in eine `Art`-Leinwand (960 × 960, Mitte = Grafikmitte des Videos). `u` (0–1) ist der Aufbau der
Grafik (Partikel ordnen sich, Linie zeichnet sich …), `t` die Szenenzeit für das langsame Weiterschweben danach.
"""

from __future__ import annotations

import functools
import math
import random

import numpy as np
from PIL import Image

from .manuskript import Art, mfont, partial
from .theme import clamp, ease_in_out, ease_out_cubic

PHI = (1 + 5 ** 0.5) / 2
SIZE = 960
C = SIZE / 2
VISUALS = ["spirale_partikel", "zahl_zaehler", "linie_zeichnen", "punktmuster", "figur", "gitterkoerper", "baum", "tuer",
           "wolke", "zitatkarte", "beschriftung"]
POSES = ["stehen", "beten", "zwei", "liegen", "sitzen"]


def seg(u: float, a: float, b: float) -> float:
    """Anteil von u im Abschnitt a–b (0–1)."""
    return clamp((u - a) / (b - a))


def golden_squares(art: Art, x: float, y: float, h: float, a: float) -> None:
    """Sehr feine Quadrate eines Goldenen Rechtecks (Hintergrunddeko)."""
    w = h * PHI
    art.rect((x, y, x + w, y + h), a_line=a, width=2)
    for k in range(7):
        s = h
        if k % 4 == 0:
            art.rect((x, y, x + s, y + s), a_line=a, width=2)
            x, w = x + s, w - s
        elif k % 4 == 1:
            art.rect((x, y, x + w, y + w), a_line=a, width=2)
            y, h = y + w, h - w
        elif k % 4 == 2:
            art.rect((x + w - h, y, x + w, y + h), a_line=a, width=2)
            w -= h
        else:
            art.rect((x, y + h - w, x + w, y + h), a_line=a, width=2)
            h -= w


@functools.lru_cache(maxsize=1)
def decor_layer() -> Image.Image:
    """Große, leicht geneigte Fibonacci-Rechtecke als feine Hintergrundlinien über fast die ganze Bildbreite."""
    from .theme import H, W
    from .manuskript import INK

    art = Art(W, H, ss=1)
    golden_squares(art, -250, 410, 940, 1.0)
    mask = art.f.rotate(-1.6, resample=Image.BICUBIC, center=(W / 2, H / 2))
    out = Image.new("RGBA", (W, H), (*INK, 0))
    out.putalpha(mask.point(lambda v: int(v * 0.15)))
    return out


DECOR = {"spirale_partikel", "zahl_zaehler", "beschriftung", "linie_zeichnen", "punktmuster"}


# --------------------------------------------------------------------------- Spirale aus Partikeln

@functools.lru_cache(maxsize=1)
def _spiral() -> tuple[list[tuple[float, float]], np.ndarray]:
    th = np.linspace(0.0, 3.7 * math.pi, 2400)
    r = 10.0 * PHI ** (2 * th / math.pi)
    x, y = r * np.cos(th), r * np.sin(th)
    x, y = x - (x.max() + x.min()) / 2 + 20, y - (y.max() + y.min()) / 2
    pts = np.stack([x, y], 1)
    length = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    n = 360
    idx = np.searchsorted(length, np.linspace(0, length[-1], n))
    return [(C + float(px), C + float(py)) for px, py in pts], pts[np.clip(idx, 0, len(pts) - 1)] + C


def v_spirale_partikel(art: Art, u: float, t: float, p: dict) -> None:
    """Verstreute Lichtpunkte ordnen sich, dann zeichnet sich die Spirale als saubere Leuchtlinie; Lichtpunkte laufen daran entlang."""
    line, targets = _spiral()
    rnd = random.Random(5)
    n = len(targets)
    dust = seg(u, 0.0, 0.5)
    for i in range(0, n, 3):
        tx, ty = targets[i]
        sx, sy = rnd.uniform(-30, SIZE + 30), rnd.uniform(40, SIZE - 40)
        q = ease_in_out(seg(u, i / n * 0.15, i / n * 0.15 + 0.4))
        swirl = math.sin(i * 1.7) * 60 * q * (1 - q)
        fade = 1.0 - 0.85 * seg(u, 0.45, 0.8)                      # die Linie übernimmt
        art.dot(sx + (tx - sx) * q - swirl, sy + (ty - sy) * q + swirl, 1.5 + 0.8 * q, (0.3 + 0.6 * q) * fade)
    v = ease_in_out(seg(u, 0.3, 0.92))
    if v > 0.005:
        shown = partial(line, v)
        art.line(shown, 3.4, 1.0)
        art.dot(shown[-1][0], shown[-1][1], 5.5, 1.0 if v < 0.995 else 0.0)        # leuchtende Spitze
    run = seg(u, 0.55, 0.8)
    if run > 0:
        for k in range(6):                                            # Lichtpunkte laufen an der Linie entlang
            f = (t * 0.1 + k / 6) % 1.0
            x, y = partial(line, max(0.02, f))[-1]
            art.dot(x, y, 3.6, run * (0.55 + 0.45 * math.sin(t * 3 + k)))
    c = line[0]
    art.ring(c[0], c[1], 11, 2.2, 0.95 * seg(u, 0.1, 0.4))
    art.dot(c[0], c[1], 3.6, seg(u, 0.1, 0.4))


# --------------------------------------------------------------------------- Zahl

def v_zahl_zaehler(art: Art, u: float, t: float, p: dict) -> None:
    text = str(p.get("wert") or "1,6180339887...")
    size = 240
    while size > 50 and mfont("serif_m", size).getlength(text) > 850:        # ≈ 78 % der Bildbreite
        size -= 4
    fnt = mfont("serif_m", size)
    shown = seg(u, 0.02, 0.88) * len(text)
    full, frac = int(shown), shown - int(shown)
    n = min(len(text), full + (1 if frac > 0 else 0))
    if n <= 0:
        return
    prefix_w = fnt.getlength(text[:n])
    x = C - prefix_w / 2
    y = C + size * 0.3
    for i in range(n):
        a = frac if i == full else 1.0
        art.text((x + fnt.getlength(text[:i]), y), text[i], fnt, a * max(0.42, 1.0 - 0.075 * max(0, i - 6)))


# --------------------------------------------------------------------------- Linie / Teilung im Goldenen Schnitt

def v_linie_zeichnen(art: Art, u: float, t: float, p: dict) -> None:
    x0, x1, y = 100.0, 860.0, C
    xs = x0 + (x1 - x0) / PHI
    v = ease_in_out(seg(u, 0.0, 0.45))
    art.line(partial([(x0, y), (x1, y)], v), 3.4, 0.95)
    art.dot(x0, y, 5, 1.0 if v > 0.02 else 0)
    art.dot(x0 + (x1 - x0) * v, y, 5, 1.0 if v > 0.02 else 0)
    k = ease_out_cubic(seg(u, 0.5, 0.65))
    art.line([(xs, y - 26 * k), (xs, y + 26 * k)], 3.2, 0.95)
    br = ease_out_cubic(seg(u, 0.62, 0.85))
    f = mfont("italic", 46)
    for a, b, name in ((x0, xs, "a"), (xs, x1, "b")) if br > 0.01 else ():
        m = (a + b) / 2
        w = (b - a) / 2 * br
        art.line([(m - w, y + 60), (m + w, y + 60)], 2.2, 0.75)
        art.line([(m - w, y + 52), (m - w, y + 68)], 2.2, 0.75)
        art.line([(m + w, y + 52), (m + w, y + 68)], 2.2, 0.75)
        art.text((m, y + 128), name, f, seg(u, 0.8, 1.0), anchor="ms")
    art.text((C, y - 70), "a : b", mfont("italic", 40), 0.0 if u < 0.9 else seg(u, 0.9, 1.0) * 0.85, anchor="ms")


# --------------------------------------------------------------------------- Punktmuster (Sonnenblume)

def v_punktmuster(art: Art, u: float, t: float, p: dict) -> None:
    n = int(clamp(float(p.get("n") or 320), 20, 900))
    c = 395 / math.sqrt(n)
    shown = ease_out_cubic(seg(u, 0.0, 0.85)) * n
    rot = 0.06 * t
    golden = math.pi * (3 - 5 ** 0.5)
    for i in range(int(shown) + 1):
        r = c * math.sqrt(i + 0.5)
        a = i * golden + rot
        edge = 1.0 if i < shown - 8 else clamp(shown - i) * 0.9
        art.dot(C + r * math.cos(a), C + r * math.sin(a), 2.0 + 3.6 * (r / 395) ** 1.2, edge * (0.55 + 0.4 * r / 395))


# --------------------------------------------------------------------------- Strichmännchen

def _stick_parts(pose: str, dress: bool = False) -> dict:
    """Linien (Einheit: Körperhöhe ≈ 100, y nach oben ab Boden)."""
    if pose == "beten":
        return {"head": (10, 70), "lines": [[(-8, 26), (4, 62)], [(-8, 26), (14, 2), (-18, 2)], [(4, 58), (22, 36)], [(4, 56), (20, 33)]]}
    if pose == "sitzen":
        return {"head": (-6, 92), "lines": [[(-6, 84), (-6, 40)], [(-6, 40), (22, 40), (22, 0)], [(-6, 78), (10, 56), (22, 46)],
                                            [(-26, 37), (32, 37)], [(-18, 37), (-18, 0)], [(28, 37), (28, 22)]]}
    if pose == "liegen":
        return {"head": (-50, 11), "lines": [[(-42, 7), (10, 7)], [(10, 7), (34, 15), (58, 3)], [(-36, 7), (-8, 3)], [(-40, 9), (-14, 14)]]}
    if dress:
        return {"head": (0, 91), "lines": [[(0, 83), (0, 66)], [(-12, 22), (0, 66), (12, 22), (-12, 22)], [(-4, 22), (-4, 0)],
                                           [(4, 22), (4, 0)], [(0, 78), (-13, 52)], [(0, 78), (13, 52)]]}
    return {"head": (0, 91), "lines": [[(0, 83), (0, 46)], [(0, 46), (-8, 0)], [(0, 46), (8, 0)], [(0, 78), (-13, 50)],
                                       [(0, 78), (13, 50)]]}


def _draw_stick(art: Art, cx: float, gy: float, pose: str, sc: float, q: float, dress: bool = False, sway: float = 0.0) -> None:
    parts = _stick_parts(pose, dress)
    tr = lambda x, y: (cx + x * sc + sway, gy - y * sc)
    hx, hy = tr(*parts["head"])
    art.dot(hx, hy, 7.2 * sc, clamp(q * 3))
    for i, line in enumerate(parts["lines"]):
        lq = clamp(q * 1.6 - i * 0.08)
        art.line(partial([tr(*pt) for pt in line], lq), 4.2, 0.95)


def v_figur(art: Art, u: float, t: float, p: dict) -> None:
    pose = p.get("pose") if p.get("pose") in POSES else "stehen"
    cx0, cy0 = 590, 205
    card = ease_out_cubic(seg(u, 0.0, 0.2))
    art.rect((C - 300, C - 240 + (1 - card) * 20, C + 300, C + 240 + (1 - card) * 20), a_fill=0.07 * card, a_line=0.16 * card,
             width=2, radius=30)
    gy = C + 175
    art.line([(C - 235, gy), (C + 235, gy)], 2.2, 0.35 * card, flat=True)
    sway = math.sin(t * 1.3) * 1.2
    q = ease_out_cubic(seg(u, 0.12, 0.5))
    sc = 2.3
    if pose == "zwei":
        x1, x2 = C - 95, C + 95
        _draw_stick(art, x1, gy, "stehen", sc, q, False, sway)
        _draw_stick(art, x2, gy, "stehen", sc, q, True, -sway)
        top = gy - 91 * sc - 26
        arc = [(x1 + (x2 - x1) * s / 40, top - 78 * (1 - (2 * s / 40 - 1) ** 2)) for s in range(41)]
        dots = partial(arc, ease_in_out(seg(u, 0.5, 0.85)))
        for i in range(0, len(dots), 2):
            art.dot(dots[i][0], dots[i][1], 2.6, 0.9)
        art.text((C, top - 100), "?", mfont("sans", 62), seg(u, 0.82, 1.0) * 0.95, anchor="ms")
    else:
        _draw_stick(art, C - (30 if pose == "liegen" else 0), gy, pose, sc * (0.92 if pose != "liegen" else 1.5), q, False, sway)


# --------------------------------------------------------------------------- Drahtgitter-Körper (Ikosaeder)

@functools.lru_cache(maxsize=1)
def _ico() -> tuple[np.ndarray, list[tuple[int, int]]]:
    v = []
    for a in (-1, 1):
        for b in (-PHI, PHI):
            v += [(0, a, b), (a, b, 0), (b, 0, a)]
    v = np.array(v, dtype=float)
    edges = [(i, j) for i in range(12) for j in range(i + 1, 12) if abs(np.sum((v[i] - v[j]) ** 2) - 4) < 1e-6]
    return v, edges


def v_gitterkoerper(art: Art, u: float, t: float, p: dict) -> None:
    verts, edges = _ico()
    yaw, pitch = 0.5 * t + 0.6, 0.45 + 0.12 * math.sin(t * 0.4)
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    pts = verts @ ry.T @ rx.T
    scale = 235.0
    persp = 1 / (1 - pts[:, 2] * 0.12)
    xy = [(C + pts[i, 0] * scale * persp[i], C - pts[i, 1] * scale * persp[i]) for i in range(12)]
    for k, (i, j) in enumerate(edges):
        q = clamp((u * (len(edges) + 4) - k) / 3)
        depth = (pts[i, 2] + pts[j, 2]) / 2
        art.line(partial([xy[i], xy[j]], q), 2.3, (0.4 + 0.22 * depth / PHI) * (1.0 if q >= 1 else 0.9))
    for i in range(12):
        art.dot(*xy[i], 3.6, seg(u, 0.5, 0.8) * (0.7 + 0.3 * pts[i, 2] / PHI))
    rects = [[(0, 1, PHI), (0, -1, PHI), (0, -1, -PHI), (0, 1, -PHI)], [(1, PHI, 0), (-1, PHI, 0), (-1, -PHI, 0), (1, -PHI, 0)],
             [(PHI, 0, 1), (PHI, 0, -1), (-PHI, 0, -1), (-PHI, 0, 1)]]
    for r, corners in enumerate(rects):
        k = seg(u, 0.62 + r * 0.1, 0.8 + r * 0.1)
        if k <= 0:
            continue
        pr = np.array(corners, float) @ ry.T @ rx.T
        ps = [(C + x * scale * (1 / (1 - z * 0.12)), C - y * scale * (1 / (1 - z * 0.12))) for x, y, z in pr]
        art.line(partial(ps + [ps[0]], k), 3.4, 0.95)


# --------------------------------------------------------------------------- Baum

def _branches(x: float, y: float, ang: float, length: float, depth: int, rnd: random.Random, out: list, sway: float,
              max_depth: int) -> None:
    ex, ey = x + math.sin(ang) * length, y - math.cos(ang) * length
    out.append((x, y, ex, ey, depth))
    if depth >= max_depth:
        return
    spread = 0.42 + rnd.uniform(-0.07, 0.07)
    for sign in (-1, 1):
        a = ang + sign * spread + math.sin(sway + depth) * 0.02 * depth
        _branches(ex, ey, a, length * (0.7 + rnd.uniform(-0.04, 0.04)), depth + 1, rnd, out, sway, max_depth)


def v_baum(art: Art, u: float, t: float, p: dict) -> None:
    out: list = []
    _branches(C, 800, 0.0, 168, 0, random.Random(8), out, t * 0.9, 7)
    ground = ease_out_cubic(seg(u, 0.0, 0.15))
    if ground > 0.01:
        art.line([(C - 150 * ground, 800), (C + 150 * ground, 800)], 2.2, 0.6)
    for x, y, ex, ey, depth in out:
        q = clamp(u * 9.2 - depth * 1.0)
        if q <= 0:
            continue
        art.line(partial([(x, y), (ex, ey)], q), max(1.6, 8.5 - depth * 1.15), 0.95, caps=depth < 5)
        if depth == 7 and q >= 1:
            art.dot(ex, ey, 3.0, seg(u, 0.9, 1.0) * 0.8)


# --------------------------------------------------------------------------- Tür

def v_tuer(art: Art, u: float, t: float, p: dict) -> None:
    x0, x1, top, bot = C - 135, C + 135, 240.0, 740.0
    h = bot - top
    fr = ease_out_cubic(seg(u, 0.0, 0.3))
    art.line(partial([(x0, bot), (x0, top), (x1, top), (x1, bot)], fr), 3.6, 0.95)
    art.line([(x0 - 60, bot), (x1 + 60, bot)], 2.4, 0.5 * fr)
    ang = ease_in_out(seg(u, 0.3, 0.9)) * 1.0
    ca, sa = math.cos(ang), math.sin(ang)
    mid = (top + bot) / 2

    def leaf(fx: float, fy: float) -> tuple[float, float]:     # fx 0..1 Breite, fy 0..1 Höhe
        x = x0 + 8 + (x1 - x0 - 16) * fx * ca
        shrink = 1 - 0.16 * sa * fx
        return x, mid + (top + h * fy - mid) * shrink

    if ang > 0.05:
        pts = [(x0 + 8, bot - 4)]
        spill = [leaf(1, 0), leaf(1, 1)]
        art.polygon([(x1 - 8, top + 4), (x1 - 8, bot - 4)] + spill[::-1] + [], 0.10 * sa)
        art.polygon([spill[1], (x1 - 8, bot - 4), (x1 + 120, bot + 30), spill[1]], 0.05 * sa)
    box = [leaf(0, 0.02), leaf(1, 0.02), leaf(1, 0.98), leaf(0, 0.98), leaf(0, 0.02)]
    art.line(box, 3.2, 0.95 * seg(u, 0.25, 0.4))
    for (a, b, c, d) in ((0.2, 0.08, 0.8, 0.44), (0.2, 0.56, 0.8, 0.92)):
        art.line([leaf(a, b), leaf(c, b), leaf(c, d), leaf(a, d), leaf(a, b)], 2.0, 0.55 * seg(u, 0.3, 0.5))
    hx, hy = leaf(0.86, 0.52)
    art.dot(hx, hy, 6, 0.95 * seg(u, 0.3, 0.5))


# --------------------------------------------------------------------------- Wolke

_CLOUD = [(-130, 20, 55), (-55, -25, 80), (45, -50, 95), (140, 5, 70)]


def v_wolke(art: Art, u: float, t: float, p: dict) -> None:
    ox, oy = C + 14 * math.sin(t * 0.5), C + 10 + 5 * math.sin(t * 0.9)
    base = 75.0
    reveal = -230 + 470 * ease_in_out(seg(u, 0.0, 0.85))
    for i, (cx, cy, r) in enumerate(_CLOUD):
        run: list[tuple[float, float]] = []
        for k in range(0, 361, 2):
            a = math.radians(k)
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            inside = any(j != i and math.hypot(x - ox2, y - oy2) < r2 - 1.5 for j, (ox2, oy2, r2) in enumerate(_CLOUD))
            if inside or y > base + 0.5 or x > reveal:
                if len(run) > 1:
                    art.line([(ox + a_, oy + b_) for a_, b_ in run], 3.4, 0.95)
                run = []
            else:
                run.append((x, y))
        if len(run) > 1:
            art.line([(ox + a_, oy + b_) for a_, b_ in run], 3.4, 0.95)
    if reveal > -130:
        art.line([(ox - 130, oy + base), (ox + min(140, reveal), oy + base)], 3.4, 0.95)
    for k in range(7):                                       # ein paar Tropfen, wenn die Wolke steht
        rain = seg(u, 0.8, 1.0)
        if rain > 0:
            x = ox - 120 + k * 42
            ph = (t * 0.7 + k * 0.37) % 1.0
            art.line([(x, oy + 120 + ph * 90), (x - 5, oy + 140 + ph * 90)], 2.2, 0.55 * rain * (1 - ph))


# --------------------------------------------------------------------------- nur Punkt + Beschriftung

def v_beschriftung(art: Art, u: float, t: float, p: dict) -> None:
    k = ease_out_cubic(seg(u, 0.0, 0.5))
    pulse = 0.5 + 0.5 * math.sin(t * 2.0)
    if k > 0.01:
        art.dot(C, C, 6.5 * k, 0.95)
        art.ring(C, C, (22 + 3 * pulse) * k, 2.0, 0.8)
        art.ring(C, C, (44 + 10 * pulse) * k, 1.4, 0.25 * (1 - pulse))


VISUAL_FUNCS = {
    "spirale_partikel": v_spirale_partikel, "zahl_zaehler": v_zahl_zaehler, "linie_zeichnen": v_linie_zeichnen,
    "punktmuster": v_punktmuster, "figur": v_figur, "gitterkoerper": v_gitterkoerper, "baum": v_baum, "tuer": v_tuer,
    "wolke": v_wolke, "beschriftung": v_beschriftung,
}
LABEL_Y = {"zahl_zaehler": 1085, "linie_zeichnen": 1190, "figur": 1240, "beschriftung": 1030}


def draw_visual(name: str, params: dict, u: float, t: float) -> Image.Image | None:
    """Ebene (960 × 960) der Grafik zum Aufbau u und der Szenenzeit t; None bei Zitat-Karte (eigener Text-Aufbau)."""
    fn = VISUAL_FUNCS.get(name)
    if fn is None:
        return None
    art = Art(SIZE, SIZE)
    fn(art, u, t, params)
    glow = {"spirale_partikel": (0.85, 8.0), "zahl_zaehler": (1.0, 11.0)}.get(name, (0.4, 7.0))
    return art.image(glow=glow[0], blur=glow[1])
