"""Eigene Animation: Das Programm zeichnet und bewegt die Szene selbst – ohne Bilder aus dem Netz, ohne Bild-KI.

Eine Szene ist eine kleine Beschreibung (vom Sprachmodell geschrieben, hier geprüft und gezeichnet):

    {"elemente": [{"id": "dotter", "art": "form", "form": "kreis", "farbe": "dotter", "x": 50, "y": 20, "groesse": 16}, …],
     "schritte": [{"ab": 1, "nach": 0.3, "dauer": 2.0, "ziel": "dotter", "aktion": "bewege", "entlang": "rohr"}, …]}

Koordinaten 0–100 (links oben = 0/0), `groesse` in Prozent der Bildbreite. `ab` = Nummer des Satzes, zu dem der Schritt
beginnt (die Bewegung läuft also genau dann, wenn darüber gesprochen wird), `nach` = Sekunden danach, `dauer` in Sekunden.

Elemente (`art`): form (kreis, ei, tropfen, herz, quadrat, sechseck oder eigener SVG-`pfad`), schlauch (Punkte, wird
gezeichnet), huelle (durchsichtige Schicht um ein Element), schale (feste Schicht, wächst von unten), kristalle (Körnchen
auf einem Element), partikel (Strom von A nach B), traube (Haufen Kugeln), pfeil, uhr.
Aktionen: erscheine, verschwinde, bewege (nach [x, y] | zu Element | entlang Schlauch), wachse, faerbe, fuelle, drehe, pulsiere.

Alles ist schematisch gemeint – eine Erklär-Zeichnung, keine Abbildung der Wirklichkeit; im Bild steht „Animation“.
"""

from __future__ import annotations

import functools
import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MAX_ELEMENTE, MAX_SCHRITTE = 14, 18
ARTEN = ("form", "schlauch", "huelle", "schale", "kristalle", "partikel", "traube", "pfeil", "uhr")
AKTIONEN = ("erscheine", "verschwinde", "bewege", "wachse", "faerbe", "fuelle", "drehe", "pulsiere")
FORMEN = ("kreis", "ei", "tropfen", "herz", "quadrat", "sechseck")
FARBEN = {"dotter": (255, 176, 32), "eiklar": (236, 244, 248), "schale": (214, 150, 96), "kalk": (246, 244, 236), "rot": (226, 68, 62),
          "blau": (64, 140, 230), "gruen": (70, 180, 110), "gelb": (250, 210, 60), "orange": (245, 140, 50), "weiss": (250, 250, 248),
          "grau": (150, 158, 170), "braun": (150, 96, 60), "rosa": (240, 150, 170), "lila": (150, 110, 220), "tuerkis": (60, 190, 200),
          "gold": (232, 176, 72), "haut": (236, 190, 160), "schwarz": (30, 32, 38)}


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def ease(x: float) -> float:
    x = clamp(x)
    return x * x * (3 - 2 * x)


def farbe(wert, standard=(232, 176, 72)) -> tuple:
    if isinstance(wert, (list, tuple)) and len(wert) == 3:
        return tuple(int(clamp(float(v), 0, 255)) for v in wert)
    text = str(wert or "").strip().lower()
    if text in FARBEN:
        return FARBEN[text]
    m = re.fullmatch(r"#?([0-9a-f]{6})", text)
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else standard


def _zahl(wert, standard: float, lo: float, hi: float) -> float:
    try:
        return clamp(float(wert), lo, hi)
    except (TypeError, ValueError):
        return standard


# --------------------------------------------------------------------------- Formen

def svg_punkte(pfad: str) -> list[list[tuple[float, float]]]:
    """SVG-Pfad (M L H V C Q Z, groß/klein) -> Polygone. Kurven werden in Stücke geteilt."""
    tokens = re.findall(r"[MmLlHhVvCcQqZz]|-?\d*\.?\d+(?:e-?\d+)?", pfad or "")
    polys, cur, pos, start, i, cmd = [], [], (0.0, 0.0), (0.0, 0.0), 0, ""

    def num() -> float:
        nonlocal i
        i += 1
        return float(tokens[i - 1])

    try:
        while i < len(tokens) and len(polys) < 12:
            if re.fullmatch(r"[A-Za-z]", tokens[i]):
                cmd = tokens[i]
                i += 1
            rel = cmd.islower()
            c = cmd.upper()
            ox, oy = pos if rel else (0.0, 0.0)
            if c == "M":
                if cur:
                    polys.append(cur)
                pos = start = (ox + num(), oy + num())
                cur, cmd = [pos], "l" if rel else "L"
            elif c == "L":
                pos = (ox + num(), oy + num())
                cur.append(pos)
            elif c == "H":
                pos = ((pos[0] if rel else 0.0) + num(), pos[1])
                cur.append(pos)
            elif c == "V":
                pos = (pos[0], (pos[1] if rel else 0.0) + num())
                cur.append(pos)
            elif c in "CQ":
                pts = [pos] + [(ox + num(), oy + num()) for _ in range(3 if c == "C" else 2)]
                for k in range(1, 13):
                    u = k / 12
                    q = pts
                    while len(q) > 1:
                        q = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for a, b in zip(q, q[1:])]
                    cur.append(q[0])
                pos = pts[-1]
            elif c == "Z":
                if cur:
                    polys.append(cur)
                cur, pos = [], start
            else:
                break
    except (IndexError, ValueError):
        pass
    if cur:
        polys.append(cur)
    return [p for p in polys if len(p) >= 3]


def form_punkte(form: str, pfad: str = "") -> list[list[tuple[float, float]]]:
    """Umriss in Einheitskoordinaten (−1 … 1)."""
    if pfad:
        polys = svg_punkte(pfad)
        if polys:
            xs = [x for p in polys for x, _ in p]
            ys = [y for p in polys for _, y in p]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            r = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 or 1.0
            return [[((x - cx) / r, (y - cy) / r) for x, y in p] for p in polys]
    n = 72
    if form == "ei":
        return [[(math.cos(a) * .76 * (1 - .16 * -math.sin(a)), math.sin(a)) for a in (2 * math.pi * k / n for k in range(n))]]
    if form == "tropfen":
        pts = [(0.0, -1.0)]
        for k in range(n + 1):
            a = math.radians(-40 + 260 * k / n)
            pts.append((math.cos(a) * .72, .28 + math.sin(a) * .72))
        return [pts]
    if form == "herz":
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            pts.append((16 * math.sin(a) ** 3 / 17, -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) / 17 - .1))
        return [pts]
    if form == "quadrat":
        r, pts = .28, []
        for cx, cy, a0 in ((1 - r, -1 + r, -90), (1 - r, 1 - r, 0), (-1 + r, 1 - r, 90), (-1 + r, -1 + r, 180)):
            pts += [(cx + r * math.cos(math.radians(a0 + 9 * k)), cy + r * math.sin(math.radians(a0 + 9 * k))) for k in range(11)]
        return [pts]
    if form == "sechseck":
        return [[(math.cos(math.radians(60 * k)), math.sin(math.radians(60 * k))) for k in range(6)]]
    return [[(math.cos(a), math.sin(a)) for a in (2 * math.pi * k / n for k in range(n))]]


@functools.lru_cache(maxsize=256)
def _maske(form: str, pfad: str, px: int, rot: int) -> tuple:
    """Maske + Lichtkarte + Glanz einer Form (px Kantenlänge): weiche Rundung zum Rand, Glanzpunkt oben links."""
    px = max(8, px)
    big = Image.new("L", (px * 2, px * 2), 0)
    d = ImageDraw.Draw(big)
    c, r = px, px * .94
    co, si = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    for poly in form_punkte(form, pfad):
        d.polygon([(c + (x * co - y * si) * r, c + (x * si + y * co) * r) for x, y in poly], fill=255)
    mask = big.resize((px, px), Image.LANCZOS)
    m = np.asarray(mask, dtype=np.float32) / 255
    tief = np.asarray(mask.filter(ImageFilter.GaussianBlur(px * .16)), dtype=np.float32) / 255
    licht = .50 + .62 * np.clip(tief, 0, 1) ** .8
    yy, xx = np.mgrid[0:px, 0:px] / px
    licht *= 1.08 - .30 * yy                                   # oben heller
    glanz = np.exp(-(((xx - .34) / .15) ** 2 + ((yy - .28) / .11) ** 2)) * np.clip(tief * 1.6, 0, 1) * .75
    return m, licht.astype(np.float32), glanz.astype(np.float32)


def glanzform(form: str, pfad: str, px: int, rgb: tuple, alpha: float = 1.0, rot: float = 0.0) -> Image.Image:
    m, licht, glanz = _maske(form, pfad, int(px), int(round(rot / 3) * 3) % 360)
    base = np.asarray(rgb, dtype=np.float32)[None, None, :]
    col = np.clip(base * licht[..., None] + 255 * glanz[..., None], 0, 255)
    out = np.dstack([col, m[..., None] * 255 * clamp(alpha)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# --------------------------------------------------------------------------- Prüfen

def pruefe_szene(roh) -> dict | None:
    """Szenen-Beschreibung säubern: nur bekannte Arten/Aktionen, Werte im Rahmen, Verweise müssen existieren."""
    if not isinstance(roh, dict):
        return None
    elemente, ids = [], set()
    for e in (roh.get("elemente") or [])[:MAX_ELEMENTE]:
        if not isinstance(e, dict) or e.get("art") not in ARTEN:
            continue
        eid = re.sub(r"[^a-z0-9_]", "", str(e.get("id") or f"e{len(elemente)}").lower())[:20] or f"e{len(elemente)}"
        if eid in ids:
            continue
        neu = {"id": eid, "art": e["art"], "x": _zahl(e.get("x"), 50, -20, 120), "y": _zahl(e.get("y"), 50, -20, 120),
               "groesse": _zahl(e.get("groesse"), 18, 1, 100), "farbe": farbe(e.get("farbe")),
               "alpha": 0.0 if e.get("sichtbar") is False else _zahl(e.get("deckkraft"), 1, 0, 1),
               "f": _zahl(e.get("fuellung"), 1 if e["art"] in ("schlauch", "pfeil", "traube") else 0, 0, 1), "rot": _zahl(e.get("drehung"), 0, -360, 360)}
        if e["art"] == "form":
            neu["form"] = e.get("form") if e.get("form") in FORMEN else "kreis"
            neu["pfad"] = str(e.get("pfad") or "")[:1500]
            neu["streckung"] = _zahl(e.get("streckung"), 1, .3, 3)
        if e["art"] in ("schlauch", "pfeil"):
            pts = [(_zahl(p[0], 50, -10, 110), _zahl(p[1], 50, -10, 110)) for p in (e.get("punkte") or [])
                   if isinstance(p, (list, tuple)) and len(p) == 2][:16]
            if len(pts) < 2:
                continue
            neu["punkte"], neu["breite"] = pts, _zahl(e.get("breite"), 9 if e["art"] == "schlauch" else 1.6, .5, 30)
        if e["art"] == "traube":
            neu["anzahl"] = int(_zahl(e.get("anzahl"), 9, 2, 24))
        for ref in ("um", "von", "nach"):
            if e.get(ref) is not None:
                neu[ref] = e[ref]
        elemente.append(neu)
        ids.add(eid)
    for e in elemente:                                         # Verweise: Element-Kennung oder Punkt
        for ref in ("um", "von", "nach"):
            v = e.get(ref)
            if v is None:
                continue
            if isinstance(v, (list, tuple)) and len(v) == 2:
                e[ref] = (_zahl(v[0], 50, -10, 110), _zahl(v[1], 50, -10, 110))
            elif str(v) in ids and str(v) != e["id"]:
                e[ref] = str(v)
            else:
                e.pop(ref)
    elemente = [e for e in elemente if not (e["art"] in ("huelle", "schale", "kristalle") and not isinstance(e.get("um"), str))
                and not (e["art"] == "partikel" and ("von" not in e or "nach" not in e))]
    ids = {e["id"] for e in elemente}
    schritte = []
    for s in (roh.get("schritte") or [])[:MAX_SCHRITTE]:
        if not isinstance(s, dict) or s.get("aktion") not in AKTIONEN or str(s.get("ziel")) not in ids:
            continue
        neu = {"ziel": str(s["ziel"]), "aktion": s["aktion"], "ab": int(_zahl(s.get("ab"), 1, 1, 9)), "nach_s": _zahl(s.get("nach"), .2, 0, 12)
               if not isinstance(s.get("nach"), (list, tuple, str)) else .2, "dauer": _zahl(s.get("dauer"), 1.4, .15, 9)}
        a = s["aktion"]
        if a == "bewege":
            if str(s.get("entlang")) in ids:
                neu["entlang"], neu["von"], neu["bis"] = str(s["entlang"]), _zahl(s.get("von"), 0, 0, 1), _zahl(s.get("bis"), 1, 0, 1)
            elif str(s.get("zu")) in ids:
                neu["zu"] = str(s["zu"])
            elif isinstance(s.get("nach"), (list, tuple)) and len(s["nach"]) == 2:
                neu["punkt"] = (_zahl(s["nach"][0], 50, -20, 120), _zahl(s["nach"][1], 50, -20, 120))
            elif isinstance(s.get("punkt"), (list, tuple)) and len(s["punkt"]) == 2:
                neu["punkt"] = (_zahl(s["punkt"][0], 50, -20, 120), _zahl(s["punkt"][1], 50, -20, 120))
            else:
                continue
        elif a == "wachse":
            neu["auf"] = _zahl(s.get("auf"), 24, 1, 100)
        elif a == "faerbe":
            neu["farbe"] = farbe(s.get("farbe"))
        elif a == "fuelle":
            neu["auf"] = _zahl(s.get("auf"), 1, 0, 1)
        elif a == "drehe":
            neu["um"] = _zahl(s.get("um"), 90, -720, 720)
        schritte.append(neu)
    return {"elemente": elemente, "schritte": schritte} if elemente else None


# --------------------------------------------------------------------------- Bühne

def _glatt(pts: list[tuple[float, float]], n: int = 14) -> list[tuple[float, float]]:
    """Catmull-Rom: weiche Kurve durch die Punkte."""
    if len(pts) < 3:
        return list(pts)
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        for k in range(n):
            u = k / n
            out.append(tuple(.5 * ((2 * p[i][d]) + (-p[i - 1][d] + p[i + 1][d]) * u + (2 * p[i - 1][d] - 5 * p[i][d] + 4 * p[i + 1][d] - p[i + 2][d]) * u * u
                                   + (-p[i - 1][d] + 3 * p[i][d] - 3 * p[i + 1][d] + p[i + 2][d]) * u ** 3) for d in (0, 1)))
    out.append(pts[-1])
    return out


def _dicht(pts: list[tuple[float, float]], abstand: float = .7) -> list[tuple[float, float]]:
    """Punkte so verdichten, dass sie höchstens `abstand` auseinanderliegen (für Röhren aus Kreisen)."""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / abstand))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


class Buehne:
    """Zeichnet eine geprüfte Szene zum Zeitpunkt t (Sekunden seit Szenenbeginn) als RGBA-Bild der Kantenlänge `size`."""

    def __init__(self, szene: dict, size: int, satz_zeiten: list[float], ink: tuple, akzent: tuple, seed: int = 0):
        self.size, self.ink, self.ak, self.seed = size, tuple(ink), tuple(akzent), seed
        self.el = {e["id"]: e for e in szene["elemente"]}
        self.order = [e["id"] for e in szene["elemente"]]
        zeiten = satz_zeiten or [0.0]
        self.schritte = sorted(({**s, "t": zeiten[min(len(zeiten), s["ab"]) - 1] + s["nach_s"]} for s in szene["schritte"]), key=lambda s: s["t"])
        self.kurven = {}
        for e in szene["elemente"]:
            if e["art"] in ("schlauch", "pfeil"):
                pts = _dicht(_glatt(e["punkte"])) if e["art"] == "schlauch" else list(e["punkte"])
                laengen = [0.0]
                for a, b in zip(pts, pts[1:]):
                    laengen.append(laengen[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
                self.kurven[e["id"]] = (pts, laengen)
        self.rng = np.random.default_rng(seed + 5).random((64, 3))

    def _auf_kurve(self, kid: str, f: float) -> tuple[float, float]:
        pts, laengen = self.kurven[kid]
        ziel = clamp(f) * laengen[-1]
        for i in range(1, len(pts)):
            if laengen[i] >= ziel:
                seg = laengen[i] - laengen[i - 1] or 1.0
                u = (ziel - laengen[i - 1]) / seg
                return pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * u, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * u
        return pts[-1]

    def zustand(self, t: float) -> dict:
        st = {k: {"x": e["x"], "y": e["y"], "g": e["groesse"], "farbe": e["farbe"], "alpha": e["alpha"], "f": e["f"], "rot": e["rot"], "puls": 0.0}
              for k, e in self.el.items()}
        for s in self.schritte:
            if t < s["t"]:
                continue
            z, p, a = st[s["ziel"]], ease((t - s["t"]) / s["dauer"]), s["aktion"]
            if a == "erscheine":
                z["alpha"] = max(z["alpha"], p)
                z["g"] *= .7 + .3 * p
            elif a == "verschwinde":
                z["alpha"] *= 1 - p
            elif a == "bewege":
                if "entlang" in s and s["entlang"] in self.kurven:
                    z["x"], z["y"] = self._auf_kurve(s["entlang"], s["von"] + (s["bis"] - s["von"]) * p)
                else:
                    ziel = (st[s["zu"]]["x"], st[s["zu"]]["y"]) if "zu" in s else s["punkt"]
                    z["x"], z["y"] = z["x"] + (ziel[0] - z["x"]) * p, z["y"] + (ziel[1] - z["y"]) * p
            elif a == "wachse":
                z["g"] += (s["auf"] - z["g"]) * p
            elif a == "faerbe":
                z["farbe"] = tuple(z["farbe"][i] + (s["farbe"][i] - z["farbe"][i]) * p for i in range(3))
            elif a == "fuelle":
                z["f"] += (s["auf"] - z["f"]) * p
            elif a == "drehe":
                z["rot"] += s["um"] * p
            elif a == "pulsiere":
                z["puls"] = math.sin((t - s["t"]) * 4.2) * .06 * min(1.0, (t - s["t"]) * 2)
        return st

    def _punkt(self, ref, st: dict) -> tuple[float, float]:
        return (st[ref]["x"], st[ref]["y"]) if isinstance(ref, str) else ref

    def bild(self, t: float) -> Image.Image:
        n, k = self.size, self.size / 100
        im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        st = self.zustand(t)

        def sicher(sprite: Image.Image, x: float, y: float) -> None:
            px, py = int(x * k - sprite.width / 2), int(y * k - sprite.height / 2)
            if px < 0 or py < 0 or px + sprite.width > n or py + sprite.height > n:      # am Rand: über eine Ebene einsetzen
                ebene = Image.new("RGBA", (n, n), (0, 0, 0, 0))
                ebene.paste(sprite, (px, py))
                im.alpha_composite(ebene)
            else:
                im.alpha_composite(sprite, (px, py))

        for eid in self.order:
            e, z = self.el[eid], st[eid]
            if z["alpha"] <= .01:
                continue
            art, g = e["art"], z["g"] * (1 + z["puls"])
            if art == "form":
                px = max(8, int(g * k))
                sp = glanzform(e["form"], e["pfad"], px, z["farbe"], z["alpha"], z["rot"])
                if abs(e["streckung"] - 1) > .02:
                    sp = sp.resize((px, max(4, int(px * e["streckung"]))), Image.BILINEAR)
                sicher(sp, z["x"], z["y"])
            elif art == "traube":
                for i in range(e["anzahl"]):
                    a, r, s = self.rng[i][0] * 2 * math.pi, math.sqrt(self.rng[i][1]) * g * .42, .22 + self.rng[i][2] * .3
                    if i / e["anzahl"] <= z["f"] + .001:
                        sicher(glanzform("kreis", "", max(8, int(g * s * k)), z["farbe"], z["alpha"]), z["x"] + math.cos(a) * r, z["y"] + math.sin(a) * r * .9)
            elif art in ("huelle", "schale", "kristalle"):
                ziel, zz = self.el[e["um"]], st[e["um"]]
                if ziel["art"] != "form" or z["f"] <= .01:
                    continue
                basis = zz["g"] * (1 + zz["puls"])
                if art == "huelle":                            # durchsichtige Schicht, wird mit der Füllung dicker
                    for lage, staerke in ((1.0, .30), (.6, .28)):
                        px = max(8, int(basis * (1 + (g / 100) * 2.2 * z["f"] * lage) * k))
                        sp = glanzform(ziel["form"], ziel["pfad"], px, z["farbe"], z["alpha"] * staerke * min(1, z["f"] * 3), zz["rot"])
                        if abs(ziel["streckung"] - 1) > .02:
                            sp = sp.resize((px, max(4, int(px * ziel["streckung"]))), Image.BILINEAR)
                        sicher(sp, zz["x"], zz["y"])
                elif art == "schale":                          # feste Schicht, wächst von unten nach oben
                    px = max(8, int(basis * (1 + g / 100) * k))
                    sp = glanzform(ziel["form"], ziel["pfad"], px, z["farbe"], z["alpha"], zz["rot"])
                    if abs(ziel["streckung"] - 1) > .02:
                        sp = sp.resize((px, max(4, int(px * ziel["streckung"]))), Image.BILINEAR)
                    arr = np.asarray(sp).copy()
                    hoehe = arr.shape[0]
                    grenze = (1 - z["f"]) * hoehe
                    rampe = np.clip((np.arange(hoehe) - grenze) / (hoehe * .06) + .5, 0, 1)
                    arr[..., 3] = (arr[..., 3] * rampe[:, None]).astype(np.uint8)
                    sicher(Image.fromarray(arr, "RGBA"), zz["x"], zz["y"])
                else:                                          # Körnchen setzen sich nach und nach auf die Oberfläche
                    d = ImageDraw.Draw(im)
                    for i in range(int(len(self.rng) * z["f"])):
                        a, r = self.rng[i][0] * 2 * math.pi, basis * (.30 + .19 * self.rng[i][1])
                        x, y, s = (zz["x"] + math.cos(a) * r * .8) * k, (zz["y"] + math.sin(a) * r * ziel["streckung"]) * k, (1.2 + self.rng[i][2] * 2.2) * g / 10
                        d.ellipse((x - s, y - s, x + s, y + s), fill=tuple(int(c) for c in z["farbe"]) + (int(235 * z["alpha"]),))
            elif art == "schlauch":
                pts, laengen = self.kurven[eid]
                bis = clamp(z["f"]) * laengen[-1]
                teil = [(x * k, y * k) for (x, y), l in zip(pts, laengen) if l <= bis + 1e-6]
                if len(teil) >= 2:
                    ebene = Image.new("RGBA", (n, n), (0, 0, 0, 0))
                    d = ImageDraw.Draw(ebene)
                    w, c = e["breite"] * k, z["farbe"]
                    for anteil, hell, versatz in ((1.0, .48, 0.0), (.84, .78, 0.0), (.56, 1.0, -.07), (.20, 1.38, -.20)):
                        col = tuple(int(clamp(v * hell, 0, 255)) for v in c) + (255,)
                        r, v = w * anteil / 2, w * versatz               # runde Röhre: dunkler Rand, helle Mitte, Glanzstreifen
                        for x, y in teil:                               # Kreise je Punkt = saubere, runde Bögen ohne Zacken
                            d.ellipse((x + v - r, y + v - r, x + v + r, y + v + r), fill=col)
                    if z["alpha"] < .995:
                        ebene.putalpha(ebene.getchannel("A").point(lambda q: int(q * z["alpha"])))
                    im.alpha_composite(ebene)
            elif art == "pfeil":
                pts, laengen = self.kurven[eid]
                (x0, y0), (x1, y1) = pts[0], self._auf_kurve(eid, z["f"])
                if z["f"] > .03:
                    d = ImageDraw.Draw(im)
                    col = tuple(int(c) for c in z["farbe"]) + (int(255 * z["alpha"]),)
                    w = max(2, int(e["breite"] * k))
                    d.line((x0 * k, y0 * k, x1 * k, y1 * k), fill=col, width=w)
                    a = math.atan2(y1 - y0, x1 - x0)
                    h = w * 3.2
                    d.polygon([(x1 * k + math.cos(a) * h, y1 * k + math.sin(a) * h), (x1 * k + math.cos(a + 2.5) * h, y1 * k + math.sin(a + 2.5) * h),
                               (x1 * k + math.cos(a - 2.5) * h, y1 * k + math.sin(a - 2.5) * h)], fill=col)
            elif art == "partikel":
                (ax, ay), (bx, by) = self._punkt(e["von"], st), self._punkt(e["nach"], st)
                d = ImageDraw.Draw(im)
                for i in range(16):
                    u = (t * .55 + self.rng[i][0]) % 1.0
                    if self.rng[i][1] > z["f"]:
                        continue
                    quer = math.sin(u * math.pi) * (self.rng[i][2] - .5) * 10
                    x, y = (ax + (bx - ax) * u - (by - ay) * quer / 60) * k, (ay + (by - ay) * u + (bx - ax) * quer / 60) * k
                    s = (.5 + self.rng[i][2]) * g * k / 14
                    d.ellipse((x - s, y - s, x + s, y + s), fill=tuple(int(c) for c in z["farbe"]) + (int(230 * z["alpha"] * math.sin(u * math.pi)),))
            elif art == "uhr":
                d = ImageDraw.Draw(im)
                r, x, y = g * k / 2, z["x"] * k, z["y"] * k
                col = tuple(int(c) for c in z["farbe"])
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, int(40 * z["alpha"])), outline=col + (int(255 * z["alpha"]),), width=max(2, int(r * .09)))
                if z["f"] > .005:
                    d.pieslice((x - r * .86, y - r * .86, x + r * .86, y + r * .86), -90, -90 + 360 * clamp(z["f"]), fill=col + (int(150 * z["alpha"]),))
                a = math.radians(-90 + 360 * z["f"])
                d.line((x, y, x + math.cos(a) * r * .8, y + math.sin(a) * r * .8), fill=tuple(self.ink) + (int(255 * z["alpha"]),), width=max(2, int(r * .08)))
        return im
