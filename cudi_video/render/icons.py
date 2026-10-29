"""Einfache Vektor-Icons je Thema (für Karten ohne frei lizenziertes Foto)."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

ICON_BY_PROPERTY = {"P2044": "mountain", "P1082": "people", "P4511": "lake", "P2048": "building", "P2046": "globe"}


def icon_for(spec_icon: str | None, prop: str) -> str:
    return spec_icon or ICON_BY_PROPERTY.get(prop, "globe")


def draw_icon(kind: str, size: int, color=(255, 255, 255, 235)) -> Image.Image:
    """Zeichnet das Icon 3-fach vergrößert und skaliert es für glatte Kanten herunter."""
    s = size * 3
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(6, s // 22)                     # Strichstärke
    {"building": _building, "mountain": _mountain, "globe": _globe, "people": _people,
     "lake": _lake, "island": _island, "waterfall": _waterfall}.get(kind, _globe)(d, s, w, color)
    return img.resize((size, size), Image.LANCZOS)


def _building(d, s, w, c):
    base = int(s * 0.92)
    towers = [(0.12, 0.42, 0.55), (0.40, 0.62, 0.12), (0.66, 0.88, 0.38)]   # (links, rechts, oben)
    for left, right, top in towers:
        x0, x1, y0 = int(s * left), int(s * right), int(s * top)
        d.rectangle((x0, y0, x1, base), outline=c, width=w)
        step = max(w * 3, (x1 - x0) // 4)
        for y in range(y0 + step, base - step // 2, step):                # Fensterreihen
            for x in range(x0 + step // 2 + w, x1 - w, step):
                d.rectangle((x, y, x + w, y + w), fill=c)
    mid = int(s * 0.51)
    d.line((mid, int(s * 0.12), mid, int(s * 0.02)), fill=c, width=w)     # Spitze
    d.line((int(s * 0.05), base, int(s * 0.95), base), fill=c, width=w)


def _mountain(d, s, w, c):
    base = int(s * 0.88)
    d.polygon([(s * 0.05, base), (s * 0.42, s * 0.18), (s * 0.79, base)], outline=c, width=w)
    d.polygon([(s * 0.45, base), (s * 0.70, s * 0.40), (s * 0.95, base)], outline=c, width=w)
    d.polygon([(s * 0.42, s * 0.18), (s * 0.33, s * 0.35), (s * 0.39, s * 0.32), (s * 0.44, s * 0.37),
               (s * 0.51, s * 0.35)], fill=c)                                 # Schneekappe


def _globe(d, s, w, c):
    m = int(s * 0.08)
    d.ellipse((m, m, s - m, s - m), outline=c, width=w)
    d.ellipse((int(s * 0.32), m, int(s * 0.68), s - m), outline=c, width=w)
    d.line((m, s // 2, s - m, s // 2), fill=c, width=w)
    for frac in (0.3, 0.7):
        y = int(s * frac)
        half = math.sqrt(max(0.0, (0.42 * s) ** 2 - (y - s / 2) ** 2))
        d.line((s / 2 - half, y, s / 2 + half, y), fill=c, width=w)


def _people(d, s, w, c):
    """Gruppe aus drei gefüllten Silhouetten; die mittlere steht vorne."""
    faded = (*c[:3], int(c[3] * 0.55))
    for cx, scale, color in ((0.27, 0.78, faded), (0.73, 0.78, faded), (0.5, 1.0, c)):
        r = s * 0.12 * scale
        x, head_y = s * cx, s * (0.30 if scale == 1.0 else 0.36)
        shoulders = s * 0.22 * scale
        top = head_y + r * 1.35
        d.ellipse((x - r, head_y - r, x + r, head_y + r), fill=color)
        d.chord((x - shoulders, top, x + shoulders, top + shoulders * 2.2), 180, 360, fill=color)


def _lake(d, s, w, c):
    for row, y_frac in enumerate((0.35, 0.55, 0.75)):
        points = []
        for i in range(41):
            x = s * (0.08 + 0.84 * i / 40)
            y = s * y_frac + math.sin(i / 40 * math.pi * 4 + row) * s * 0.04
            points.append((x, y))
        d.line(points, fill=c, width=w, joint="curve")


def _island(d, s, w, c):
    d.chord((int(s * 0.1), int(s * 0.62), int(s * 0.9), int(s * 1.1)), 180, 360, outline=c, width=w)
    trunk = [(s * 0.50, s * 0.66), (s * 0.53, s * 0.45), (s * 0.58, s * 0.28)]
    d.line(trunk, fill=c, width=w, joint="curve")
    tx, ty = s * 0.58, s * 0.28
    for dx in (-0.24, -0.13, 0.13, 0.24):                 # herabhängende Palmwedel (Bézier-Kurven)
        end = (tx + s * dx, ty + s * (0.10 if abs(dx) > 0.2 else 0.05))
        ctrl = (tx + s * dx * 0.5, ty - s * 0.07)
        pts = [((1 - t) ** 2 * tx + 2 * (1 - t) * t * ctrl[0] + t ** 2 * end[0],
                (1 - t) ** 2 * ty + 2 * (1 - t) * t * ctrl[1] + t ** 2 * end[1]) for t in [i / 12 for i in range(13)]]
        d.line(pts, fill=c, width=w, joint="curve")
    _lake_line(d, s, w, c, 0.9)


def _lake_line(d, s, w, c, y_frac):
    points = [(s * (0.05 + 0.9 * i / 30), s * y_frac + math.sin(i / 30 * math.pi * 3) * s * 0.025) for i in range(31)]
    d.line(points, fill=c, width=w, joint="curve")


def _waterfall(d, s, w, c):
    d.line((s * 0.1, s * 0.18, s * 0.9, s * 0.18), fill=c, width=w)
    for x in (0.35, 0.45, 0.55, 0.65):
        d.line((s * x, s * 0.2, s * x, s * 0.72), fill=c, width=w)
    d.ellipse((s * 0.2, s * 0.7, s * 0.8, s * 0.86), outline=c, width=w)
    _lake_line(d, s, w, c, 0.92)
