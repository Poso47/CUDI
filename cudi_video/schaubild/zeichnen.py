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
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MAX_ELEMENTE, MAX_SCHRITTE = 20, 30
ARTEN = ("figur", "form", "schlauch", "huelle", "schale", "kristalle", "partikel", "traube", "pfeil", "uhr", "beschriftung")
AKTIONEN = ("erscheine", "verschwinde", "bewege", "wachse", "faerbe", "fuelle", "drehe", "pulsiere", "zoom", "picke", "flattere")
KAMERA = "kamera"                         # Ziel der Aktion „zoom“: die Kamera fährt an eine Stelle heran
FORMEN = ("kreis", "ei", "tropfen", "herz", "quadrat", "sechseck")
FARBEN = {"dotter": (255, 176, 32), "eiklar": (236, 244, 248), "schale": (214, 150, 96), "kalk": (246, 244, 236), "rot": (226, 68, 62),
          "blau": (64, 140, 230), "gruen": (70, 180, 110), "gelb": (250, 210, 60), "orange": (245, 140, 50), "weiss": (250, 250, 248),
          "grau": (150, 158, 170), "braun": (150, 96, 60), "rosa": (240, 150, 170), "lila": (150, 110, 220), "tuerkis": (60, 190, 200),
          "gold": (232, 176, 72), "haut": (236, 190, 160), "schwarz": (30, 32, 38)}


FIGUREN = Path(__file__).resolve().parent.parent / "data" / "figuren"
ANKER = re.compile(r"^([a-z0-9_]{1,20})\.([a-z_]{2,20})$")


@functools.lru_cache(maxsize=16)
def figur_name(name: str) -> str:
    """Ordnername einer Figur: klein, Umlaute ausgeschrieben („Blüte“ -> „bluete“)."""
    n = str(name or "").strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        n = n.replace(a, b)
    return re.sub(r"[^a-z0-9_]", "", n)


def figur_info(name: str) -> dict | None:
    """Gezeichnete Figur (Ebenen-PNGs + figur.json aus data/figuren/<name>/) oder None."""
    pfad = FIGUREN / figur_name(name) / "figur.json"
    if not pfad.exists():
        return None
    import json

    info = json.loads(pfad.read_text("utf-8"))
    info["ordner"] = pfad.parent
    return info


def figuren() -> dict[str, dict]:
    """Alle verfügbaren Figuren mit ihren Ankerpunkten (für die Schreibanleitung)."""
    return {d.parent.name: figur_info(d.parent.name) for d in sorted(FIGUREN.glob("*/figur.json"))}


@functools.lru_cache(maxsize=64)
def _ebene(name: str, ebene: str, px: int) -> Image.Image:
    with Image.open(figur_info(name)["ordner"] / f"{ebene}.png") as im:
        return im.convert("RGBA").resize((px, px), Image.LANCZOS)


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

MAX_BESCHRIFTUNGEN = 6
LEERE_DINGE = {"ende", "anfang", "antwort", "frage", "weise", "art", "fall", "grund", "beispiel", "teil", "ding", "sache", "mal",
               "prozent", "schritt", "schritte", "schritten"}                                     # Hauptwörter ohne zeigbares Ding: keine Beschriftung


def beschriftungen_pruefen(szene: dict | None, text: str) -> dict | None:
    """Beschriftungen dürfen nur Wörter zeigen, die im gesprochenen (geprüften) Text vorkommen – sonst fliegen sie raus."""
    if not szene:
        return szene
    low = re.sub(r"\s+", " ", text.lower())
    szene["elemente"] = [e for e in szene["elemente"] if e["art"] != "beschriftung" or e["text"].lower() in low]
    from . import _wort, hauptwoerter                          # Deutsch: Beschriftungen nur an Dingen (Hauptwörtern), nie an Füllwörtern
    deutsch = re.search(r"\b(der|die|das|und|ist|wird|ein|eine)\b", low) is not None
    if deutsch:
        dinge = set(hauptwoerter(text)) - LEERE_DINGE
        szene["elemente"] = [e for e in szene["elemente"] if e["art"] != "beschriftung"
                             or (e["text"][:1].isupper() and _wort(e["text"].split()[0]) in dinge)]
    labels = [e for e in szene["elemente"] if e["art"] == "beschriftung"][MAX_BESCHRIFTUNGEN:]
    szene["elemente"] = [e for e in szene["elemente"] if e not in labels]   # höchstens MAX_BESCHRIFTUNGEN je Szene
    return szene


def abdeckung(szene: dict | None, saetze: int) -> list[int]:
    """Nummern der Sätze, zu denen die Szene nichts zeigt (kein Schritt, keine Beschriftung) – für den Prüfbericht."""
    if not szene:
        return list(range(1, saetze + 1))
    if any(s.get("bei") for s in szene["schritte"]) or any(e.get("bei") for e in szene["elemente"]):
        return []                                             # Wort-genaue Schritte lassen sich erst mit der Stimme zuordnen
    da = {s["ab"] for s in szene["schritte"]}
    return [n for n in range(1, saetze + 1) if n not in da]


def _koord(v, standard: float):
    """Zahl 0–100 oder Anker „figur.teil“ (wird in der Bühne aufgelöst)."""
    if isinstance(v, str) and ANKER.match(v.strip().lower()):
        return v.strip().lower()
    return _zahl(v, standard, -20, 120)


def _punkt(p):
    if isinstance(p, str) and ANKER.match(p.strip().lower()):
        return p.strip().lower()
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return (_koord(p[0], 50), _koord(p[1], 50))
    return None


MIN_FORM = 12.0


def _fuellen(elemente: list[dict]) -> None:
    """Bild nie leer, nie winzig: (1) Ist am Anfang nichts zu sehen, erscheint das erste Element sofort (Grundbild).
    (2) Nutzen die Elemente (ohne Figur) weniger als die Hälfte der Fläche, werden sie um die Mitte vergrößert."""
    koerper = [e for e in elemente if e["art"] != "beschriftung"]
    for e in koerper:                                          # keine winzigen Kügelchen: Formen mindestens gut sichtbar
        if e["art"] in ("form", "traube", "uhr") and e["groesse"] < MIN_FORM:
            e["groesse"] = MIN_FORM
    if koerper and all(e["alpha"] <= 0 for e in koerper):
        koerper[0]["alpha"] = 1.0
    if any(e["art"] == "figur" for e in elemente):
        return
    boxen = []
    for e in koerper:
        pts = list(e.get("punkte") or []) or [(e["x"], e["y"])]
        r = e["groesse"] / 2 if not e.get("punkte") else e.get("breite", 0) / 2
        for p in pts:
            if isinstance(p, (list, tuple)) and all(isinstance(v, (int, float)) for v in p):
                boxen.append((p[0] - r, p[1] - r, p[0] + r, p[1] + r))
    if not boxen:
        return
    x0, y0 = min(b[0] for b in boxen), min(b[1] for b in boxen)
    x1, y1 = max(b[2] for b in boxen), max(b[3] for b in boxen)
    spanne = max(x1 - x0, y1 - y0, 1.0)
    if spanne >= 50:
        return
    f, cx, cy = min(1.8, 72 / spanne), (x0 + x1) / 2, (y0 + y1) / 2
    zieh = lambda v, c: max(8.0, min(92.0, 50 + (v - c) * f)) if isinstance(v, (int, float)) else v   # noqa: E731
    for e in koerper:
        e["x"], e["y"] = zieh(e["x"], cx), zieh(e["y"], cy)
        e["groesse"] = min(100.0, e["groesse"] * f)
        if e.get("punkte"):
            e["punkte"] = [(zieh(p[0], cx), zieh(p[1], cy)) if isinstance(p, (list, tuple)) else p for p in e["punkte"]]
        if "breite" in e:
            e["breite"] = min(60.0, e["breite"] * f)


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
        if e["art"] == "figur" and not figur_info(str(e.get("figur") or "")):
            continue
        neu = {"id": eid, "art": e["art"], "x": _koord(e.get("x"), 50), "y": _koord(e.get("y"), 50),
               "groesse": _zahl(e.get("groesse"), 18, 1, 100), "farbe": farbe(e.get("farbe")),
               "alpha": 0.0 if e.get("sichtbar") is False else _zahl(e.get("deckkraft"), 1, 0, 1),
               "f": _zahl(e.get("fuellung"), 1 if e["art"] in ("schlauch", "pfeil", "traube") else 0, 0, 1), "rot": _zahl(e.get("drehung"), 0, -360, 360)}
        if e["art"] == "form":
            neu["form"] = e.get("form") if e.get("form") in FORMEN else "kreis"
            neu["pfad"] = str(e.get("pfad") or "")[:1500]
            neu["streckung"] = _zahl(e.get("streckung"), 1, .3, 3)
        if e["art"] in ("schlauch", "pfeil"):
            pts = [_punkt(p) for p in (e.get("punkte") or [])][:16]
            pts = [p for p in pts if p is not None]
            if len(pts) < 2:
                continue
            neu["punkte"], neu["breite"] = pts, _zahl(e.get("breite"), 9 if e["art"] == "schlauch" else 1.6, .5, 60)
            neu["durchsichtig"] = bool(e.get("durchsichtig"))
        if e["art"] == "beschriftung":
            neu["text"] = re.sub(r"\s+", " ", str(e.get("text") or "")).strip()[:26]
            neu["seite"] = e.get("seite") if e.get("seite") in ("links", "rechts", "oben", "unten") else ""
            neu["an"] = str(e.get("an") or "")
            if not neu["text"]:
                continue
        if e.get("bei"):
            neu["bei"] = str(e["bei"])[:30]
        if e["art"] == "figur":
            neu["figur"] = figur_name(e["figur"])
            neu["durchsichtig"] = bool(e.get("durchsichtig"))
            neu["blick"] = -1 if e.get("blick") == "links" else 1
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
    figs = {e["id"]: figur_info(e["figur"]) for e in elemente if e["art"] == "figur"}

    def gueltig(v, standard):
        if isinstance(v, str):
            m = ANKER.match(v)
            return v if m and m.group(1) in figs and m.group(2) in figs[m.group(1)]["anker"] else standard
        return v

    for e in elemente:
        e["x"], e["y"] = gueltig(e["x"], 50.0), gueltig(e["y"], 50.0)
        if "punkte" in e:
            e["punkte"] = [gueltig(p, None) if isinstance(p, str) else (gueltig(p[0], 50.0), gueltig(p[1], 50.0)) for p in e["punkte"]]
            e["punkte"] = [p for p in e["punkte"] if p is not None]
            if len(e["punkte"]) < 2:
                e["art"] = "_weg"
        if e["art"] == "beschriftung" and e["an"] not in ids:
            e["an"] = ""
    elemente = [e for e in elemente if e["art"] != "_weg"]
    elemente = [e for e in elemente if not (e["art"] in ("huelle", "schale", "kristalle") and not isinstance(e.get("um"), str))
                and not (e["art"] == "beschriftung" and not e["an"])
                and not (e["art"] == "partikel" and ("von" not in e or "nach" not in e))]
    ids = {e["id"] for e in elemente}
    _fuellen(elemente)
    schritte = []
    for s in (roh.get("schritte") or [])[:MAX_SCHRITTE]:
        if not isinstance(s, dict) or s.get("aktion") not in AKTIONEN:
            continue
        if (s["aktion"] == "zoom") != (str(s.get("ziel")) == KAMERA) or (s["aktion"] != "zoom" and str(s.get("ziel")) not in ids):
            continue
        neu = {"ziel": str(s["ziel"]), "aktion": s["aktion"], "ab": int(_zahl(s.get("ab"), 1, 1, 9)), "nach_s": _zahl(s.get("nach"), .2, 0, 12)
               if not isinstance(s.get("nach"), (list, tuple, str)) else .2, "dauer": _zahl(s.get("dauer"), 1.4, .15, 9)}
        if s.get("bei"):
            neu["bei"] = str(s["bei"])[:30]
            if s.get("nach") is None or isinstance(s.get("nach"), (list, tuple, str)):
                neu["nach_s"] = 0.0
        a = s["aktion"]
        if a == "zoom":
            neu["auf"] = _zahl(s.get("auf"), 1.8, 1, 3.5)
            if str(s.get("zu")) in ids:
                neu["zu"] = str(s["zu"])
            elif isinstance(s.get("punkt"), str) and gueltig(s["punkt"].strip().lower(), None):
                neu["punkt"] = (s["punkt"].strip().lower(),) * 2
            elif isinstance(s.get("punkt"), (list, tuple)) and len(s["punkt"]) == 2:
                neu["punkt"] = (_zahl(s["punkt"][0], 50, 0, 100), _zahl(s["punkt"][1], 50, 0, 100))
            else:
                neu["punkt"] = (50.0, 50.0)
        elif a == "bewege":
            if str(s.get("entlang")) in ids:
                neu["entlang"], neu["von"], neu["bis"] = str(s["entlang"]), _zahl(s.get("von"), 0, 0, 1), _zahl(s.get("bis"), 1, 0, 1)
            elif str(s.get("zu")) in ids:
                neu["zu"] = str(s["zu"])
            elif isinstance(s.get("nach"), (list, tuple)) and len(s["nach"]) == 2:
                neu["punkt"] = (_zahl(s["nach"][0], 50, -20, 120), _zahl(s["nach"][1], 50, -20, 120))
            elif isinstance(s.get("punkt"), str) and gueltig(s["punkt"].strip().lower(), None):
                neu["punkt"] = (s["punkt"].strip().lower(),) * 2
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

    def __init__(self, szene: dict, size: int, satz_zeiten: list[float], ink: tuple, akzent: tuple, seed: int = 0, wort_zeit=None):
        self.size, self.ink, self.ak, self.seed = size, tuple(ink), tuple(akzent), seed
        szene = self._anker_aufloesen(szene)
        self.el = {e["id"]: e for e in szene["elemente"]}
        self.order = [e["id"] for e in szene["elemente"]]
        zeiten = satz_zeiten or [0.0]

        def beginn(s: dict) -> float:                          # genau beim genannten Wort – sonst zum Satzbeginn
            t = wort_zeit(s["bei"]) if (wort_zeit and s.get("bei")) else None
            return (t if t is not None else zeiten[min(len(zeiten), s.get("ab", 1)) - 1]) + s.get("nach_s", 0.0)

        self.schritte = sorted(({**s, "t": beginn(s)} for s in szene["schritte"]), key=lambda s: s["t"])
        for e in szene["elemente"]:                            # Beschriftung erscheint, wenn ihr Wort fällt
            if e["art"] == "beschriftung":
                e["_t"] = beginn({"bei": e.get("bei") or e["text"], "ab": 1, "nach_s": 0.0}) if wort_zeit else zeiten[0]
        self._pillen: dict = {}
        self.kurven = {}
        for e in szene["elemente"]:
            if e["art"] in ("schlauch", "pfeil"):
                pts = _dicht(_glatt(e["punkte"])) if e["art"] == "schlauch" else list(e["punkte"])
                laengen = [0.0]
                for a, b in zip(pts, pts[1:]):
                    laengen.append(laengen[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
                self.kurven[e["id"]] = (pts, laengen)
        self.rng = np.random.default_rng(seed + 5).random((64, 3))

    @staticmethod
    def _anker_aufloesen(szene: dict) -> dict:
        """„huhn.bauch“ -> Bildkoordinaten (aus Lage und Größe der Figur). Kopie, das Original bleibt unverändert."""
        import copy

        szene = copy.deepcopy(szene)
        figs = {e["id"]: e for e in szene["elemente"] if e["art"] == "figur"}

        def los(v, achse):
            if not isinstance(v, str):
                return v
            fid, teil = v.split(".")
            f, info = figs[fid], figur_info(figs[fid]["figur"])
            a = info["anker"][teil][achse] / info["groesse"] - .5
            if achse == 0:
                a *= f.get("blick", 1)
            return f["x" if achse == 0 else "y"] + a * f["groesse"]

        for e in szene["elemente"]:
            if e["art"] == "figur":
                continue
            e["x"], e["y"] = los(e["x"], 0), los(e["y"], 1)
            if "punkte" in e:
                e["punkte"] = [(los(p, 0), los(p, 1)) if isinstance(p, str) else (los(p[0], 0), los(p[1], 1)) for p in e["punkte"]]
            for ref in ("von", "nach"):
                if isinstance(e.get(ref), tuple):
                    e[ref] = (los(e[ref][0], 0), los(e[ref][1], 1))
        for s in szene["schritte"]:
            if isinstance(s.get("punkt"), tuple):
                s["punkt"] = (los(s["punkt"][0], 0), los(s["punkt"][1], 1))
        return szene

    def _figur(self, e: dict, z: dict, t: float) -> Image.Image:
        """Figur aus ihren Ebenen zusammensetzen – mit Eigenleben: atmen, blinzeln, Kopf nicken, Schwanz wippen;
        dazu die Aktionen „picke“ (Kopf runter) und „flattere“ (Flügel schlagen)."""
        info = figur_info(e["figur"])
        px = max(16, int(z["g"] * self.size / 100 / 8) * 8)
        f = px / info["groesse"]
        bild = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        dreh = info.get("drehpunkte", {})
        phase = self.seed % 5
        atem = 1 + .014 * math.sin(t * 2.4 + phase)
        winkel = {"kopf": 2.2 * math.sin(t * 1.3 + phase) - 22 * z.get("picke", 0.0),
                  "schwanz": 1.8 * math.sin(t * 1.7 + phase + 1),
                  "fluegel": -16 * abs(math.sin(t * 14)) * z.get("flattere", 0.0)}
        blinzeln = (t + phase * .7) % 3.4 < .14
        deck = z["alpha"]
        for ebene in info["ebenen"]:
            if ebene in info.get("versteckt", []) and not (ebene == "lid" and blinzeln):
                continue
            lage = _ebene(e["figur"], ebene, px)
            haupt = "kopf" if ebene in info.get("mit_kopf", []) else ebene
            w = winkel.get(haupt, 0.0)
            if abs(w) > .05:
                cx, cy = (v * f for v in dreh.get(haupt, (info["groesse"] / 2,) * 2))
                lage = lage.rotate(w, resample=Image.BICUBIC, center=(cx, cy))
            if ebene in ("koerper", "fluegel") and abs(atem - 1) > .001:
                h = int(px * atem)
                lage = lage.resize((px, h), Image.BILINEAR).crop((0, h - px, px, h))
            a = deck * (.55 if e.get("durchsichtig") and ebene in ("koerper", "fluegel") else 1.0)
            if a < .995:
                lage = lage.copy()
                lage.putalpha(lage.getchannel("A").point(lambda q: int(q * a)))
            bild.alpha_composite(lage)
        if e.get("blick", 1) < 0:
            bild = bild.transpose(Image.FLIP_LEFT_RIGHT)
        return bild

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
        st[KAMERA] = {"x": 50.0, "y": 50.0, "f": 1.0}
        for s in self.schritte:
            if t < s["t"]:
                continue
            p, a = ease((t - s["t"]) / s["dauer"]), s["aktion"]
            if a == "zoom":
                k = st[KAMERA]
                ziel = (st[s["zu"]]["x"], st[s["zu"]]["y"]) if "zu" in s else s["punkt"]
                k["x"], k["y"], k["f"] = k["x"] + (ziel[0] - k["x"]) * p, k["y"] + (ziel[1] - k["y"]) * p, k["f"] + (s["auf"] - k["f"]) * p
                continue
            z = st[s["ziel"]]
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
            elif a in ("picke", "flattere"):                  # kurze Bewegung: hin und zurück
                z[a] = math.sin(math.pi * clamp((t - s["t"]) / s["dauer"])) if t - s["t"] < s["dauer"] else 0.0
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
            if art == "figur":
                sicher(self._figur(e, {**z, "g": g}, t), z["x"], z["y"])
                continue
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
                    if e.get("durchsichtig"):                  # Schnittbild: kräftige Wand, blasses Inneres – der Inhalt bleibt gut zu sehen
                        lagen = ((1.0, .50, 0.0, 255), (.80, 1.25, 0.0, 46), (.10, 1.6, -.30, 150))
                    else:                                      # runde Röhre: dunkler Rand, helle Mitte, Glanzstreifen
                        lagen = ((1.0, .48, 0.0, 255), (.84, .78, 0.0, 255), (.56, 1.0, -.07, 255), (.20, 1.38, -.20, 255))
                    for anteil, hell, versatz, deckung in lagen:
                        col = tuple(int(clamp(v * hell, 0, 255)) for v in c) + (deckung,)
                        r, v = w * anteil / 2, w * versatz
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
        kam = st[KAMERA]
        f, ox, oy = 1.0, 0.0, 0.0
        if kam["f"] > 1.01:                                    # Kamera: Ausschnitt heranholen
            f = kam["f"]
            halb = n / f / 2
            cx, cy = clamp(kam["x"] * k, halb, n - halb), clamp(kam["y"] * k, halb, n - halb)
            ox, oy = cx - halb, cy - halb
            im = im.crop((int(ox), int(oy), int(ox + 2 * halb), int(oy + 2 * halb))).resize((n, n), Image.BILINEAR)
        belegt: list[tuple] = []                               # Beschriftungen zuletzt und in Bildschirmgröße: immer lesbar, nie vergrößert
        for eid in self.order:
            e = self.el[eid]
            if e["art"] != "beschriftung":
                continue
            sichtbar = clamp((t - e["_t"]) / .3) * (st[eid]["alpha"] if st[eid]["alpha"] > 0 else 1.0)
            ziel = st.get(e["an"])
            if sichtbar <= .01 or not ziel or ziel["alpha"] <= .01 and self.el[e["an"]]["art"] == "form":
                continue
            self._beschrifte(im, e, ziel, self.el[e["an"]], sichtbar, f, ox, oy, belegt)
        return im

    def _beschrifte(self, im: Image.Image, e: dict, ziel: dict, ziel_el: dict, sichtbar: float, f: float, ox: float, oy: float,
                    belegt: list) -> None:
        from PIL import ImageFont

        from ..render import theme as T

        n, k = self.size, self.size / 100
        if e["id"] not in self._pillen:
            pfad = T._font_index().get("inter-semibold.ttf")
            fnt = ImageFont.truetype(str(pfad), max(12, int(n * .04))) if pfad else ImageFont.load_default(max(12, int(n * .04)))
            w, h = int(fnt.getlength(e["text"])) + int(n * .058), int(n * .066)
            pille = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(pille)
            hell = sum(self.ink) > 380                         # helle Schrift = dunkler Grund -> helle Pille mit dunkler Schrift
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=(250, 248, 240, 245) if hell else (16, 44, 56, 245))
            d.ellipse((h * .28, h * .34, h * .28 + h * .32, h * .66), fill=self.ak + (255,))
            d.text((h * .78, h / 2), e["text"], font=fnt, fill=(20, 36, 44) if hell else (250, 248, 240), anchor="lm")
            self._pillen[e["id"]] = pille
        pille = self._pillen[e["id"]]
        radius = (ziel["g"] / 2 if ziel_el["art"] in ("form", "traube", "uhr") else ziel_el.get("breite", 8) / 2) + 2
        zx, zy = self._auf_kurve(ziel_el["id"], .5) if ziel_el["art"] in ("schlauch", "pfeil") else (ziel["x"], ziel["y"])
        seite = e["seite"] or ("rechts" if zx < 50 else "links")
        dx, dy = {"rechts": (1, -.35), "links": (-1, -.35), "oben": (0, -1), "unten": (0, 1)}[seite]
        ax, ay = ((zx + dx * radius) * k - ox) * f, ((zy + dy * radius) * k - oy) * f       # Punkt am Rand des Teils (nach der Kamera)
        ax, ay = clamp(ax, 8, n - 8), clamp(ay, 8, n - 8)
        pw, ph, rand = pille.width, pille.height, max(6, int(n * .012))

        def stelle(sdx, sdy, stufe):                           # Kandidat: Seite + Stufe (versetzt nach oben/unten)
            x = ax + sdx * n * .05 - (pw if sdx < 0 else pw / 2 if sdx == 0 else 0)
            y = ay + sdy * n * .05 - ph / 2 + stufe * (ph + rand)
            return clamp(x, 4, n - pw - 4), clamp(y, 4, n - ph - 4)

        def frei(x, y):                                        # mit Abstand zu allen schon gesetzten Beschriftungen
            return not any(x < bx + bw + rand and bx < x + pw + rand and y < by + bh + rand and by < y + ph + rand
                           for bx, by, bw, bh in belegt)

        seiten = [(dx, dy), (-dx if dx else 1, dy), (0, -1), (0, 1)]
        kandidaten = [stelle(sx, sy, st) for st in (0, 1, -1, 2, -2, 3, -3) for sx, sy in seiten]
        px, py = next((c for c in kandidaten if frei(*c)), kandidaten[0])       # Beschriftungen entzerrt: nie übereinander
        belegt.append((px, py, pw, ph))
        d = ImageDraw.Draw(im)
        ende = (clamp(ax, px, px + pille.width), py + pille.height / 2)
        d.line((ax, ay, ende[0], ende[1]), fill=self.ak + (int(235 * sichtbar),), width=max(2, int(n * .004)))
        d.ellipse((ax - n * .008, ay - n * .008, ax + n * .008, ay + n * .008), fill=self.ak + (int(255 * sichtbar),))
        if sichtbar < .995:
            pille = pille.copy()
            pille.putalpha(pille.getchannel("A").point(lambda q: int(q * sichtbar)))
        im.alpha_composite(pille, (int(px), int(py)))
