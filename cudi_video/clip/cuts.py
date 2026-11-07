"""Pausen herausschneiden (Jump-Cuts), Zeitabbildung und Schnittplan (Kameraschnitte, Zoomstufen)."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import FPS
from .reframe import ZOOM_NAH, Analyse

PAUSE = 0.35         # Lücken zwischen Wörtern darüber werden geschnitten
LEAD, TAIL = 0.07, 0.12   # Luft vor/nach einer Sprechgruppe
BLITZ = 0.15
MAX_SHOT = 6.5
MIN_SHOT = 0.8


def pausen_intervalle(words: list[dict], pause: float = PAUSE) -> list[tuple[float, float]]:
    """Behaltene Quellzeit-Intervalle: aufeinanderfolgende Wörter ohne Lücke > `pause`."""
    if not words:
        return []
    gruppen: list[list[dict]] = [[words[0]]]
    for w in words[1:]:
        if w["s"] - gruppen[-1][-1]["e"] > pause:
            gruppen.append([w])
        else:
            gruppen[-1].append(w)
    out = []
    for gi, g in enumerate(gruppen):
        vor = (g[0]["s"] - gruppen[gi - 1][-1]["e"]) if gi else 99
        nach = (gruppen[gi + 1][0]["s"] - g[-1]["e"]) if gi + 1 < len(gruppen) else 99
        a = g[0]["s"] - min(LEAD, vor / 2)
        b = g[-1]["e"] + min(TAIL, nach / 2)
        out.append((max(0.0, a), b))
    return out


@dataclass
class Abschnitt:
    name: str                       # "teaser" | "main"
    intervalle: list[tuple[float, float]]
    out0: float = 0.0
    _kum: list[float] = field(default_factory=list)

    def __post_init__(self):
        k, t = [], 0.0
        for a, b in self.intervalle:
            k.append(t)
            t += b - a
        self._kum = k
        self.dauer = t

    def mappe(self, t: float) -> float:
        """Quellzeit -> Ausgabezeit (ins nächste Intervall gedrückt)."""
        for (a, b), k in zip(self.intervalle, self._kum):
            if t <= b:
                return self.out0 + k + max(0.0, t - a)
        return self.out0 + self.dauer


@dataclass
class Schnitt:
    art: str                # "teaser" | "blitz" | "main"
    a: float                # Quellzeit
    b: float
    person: int = 0
    zoom: float = 1.0
    punch: bool = False
    out0: float = 0.0       # Ausgabezeit (Sekunden)
    frames: int = 0

    @property
    def dauer(self) -> float:
        return self.b - self.a


def _snap(grenzen: list[float], t: float, lo: float, hi: float) -> float | None:
    kand = [g for g in grenzen if lo <= g <= hi]
    return min(kand, key=lambda g: abs(g - t)) if kand else None


def _zerlege(a: float, b: float, an: Analyse, words: list[dict]) -> list[tuple[float, float]]:
    """Intervall an Personenwechseln und nach MAX_SHOT an Wortgrenzen teilen."""
    grenzen = [(x["e"] + y["s"]) / 2 for x, y in zip(words, words[1:]) if a < (x["e"] + y["s"]) / 2 < b]
    punkte: list[float] = []
    for t, _p in an.wechsel(a, b):
        s = _snap(grenzen, t, a + MIN_SHOT, b - MIN_SHOT)
        if s is not None and all(abs(s - q) >= MIN_SHOT for q in punkte):
            punkte.append(s)
    teile, start = [], a
    for p in sorted(punkte) + [b]:
        teile.append((start, p))
        start = p
    out = []
    for x, y in teile:
        n = int((y - x) // MAX_SHOT) + (1 if (y - x) % MAX_SHOT > MIN_SHOT else 0)
        if y - x > MAX_SHOT and n > 1:
            cur = x
            for k in range(1, n):
                ziel = x + (y - x) * k / n
                s = _snap(grenzen, ziel, cur + MIN_SHOT, y - MIN_SHOT)
                if s is None:
                    continue
                out.append((cur, s))
                cur = s
            out.append((cur, y))
        else:
            out.append((x, y))
    return out


def plane(abschnitte: list[Abschnitt], an: Analyse, words: list[dict], laut, hook_ende: float | None,
          blitz: bool) -> list[Schnitt]:
    """Schnittliste über Teaser, Blitz und Hauptteil. `laut(a, b)` liefert die mittlere Lautstärke (relativ)."""
    stuecke: list[Schnitt] = []
    for ab in abschnitte:
        for (a, b) in ab.intervalle:
            for (x, y) in _zerlege(a, b, an, words):
                if y - x < 0.05:
                    continue
                stuecke.append(Schnitt(ab.name, x, y, an.person_bei((x + y) / 2)))
        if ab.name == "teaser" and blitz and stuecke:
            p = stuecke[-1].person
            anderer = (p + 1) % an.spuren if an.spuren > 1 else p
            t = hook_ende if hook_ende is not None else stuecke[-1].b
            stuecke.append(Schnitt("blitz", t, t + BLITZ, anderer, ZOOM_NAH))
    # Zoomstufen: Wechsel Nah/Halbtotale bei Personenwechsel oder nach >= 3.5 s; Punch-in bei lauten Stellen
    werte = sorted(laut(s.a, s.b) for s in stuecke if s.art != "blitz") or [1.0]
    schwelle = werte[int(len(werte) * 0.75)]
    nah, t_aus, letzter_wechsel, vorher = False, 0.0, 0.0, None
    for s in stuecke:
        s.out0 = t_aus
        if s.art == "blitz":
            t_aus += s.dauer
            vorher = None
            continue
        if vorher is None or s.person != vorher.person or t_aus - letzter_wechsel >= 3.5:
            nah = not nah if vorher is not None else False
            letzter_wechsel = t_aus
        s.zoom = ZOOM_NAH if nah else 1.0
        s.punch = s.dauer >= 1.2 and laut(s.a, s.b) >= schwelle and s.zoom == 1.0
        t_aus += s.dauer
        vorher = s
    # auf ganze Bilder runden (kumulativ, kein Drift)
    kum = 0.0
    for s in stuecke:
        s.out0 = kum
        kum += s.dauer
        s.frames = max(1, round(kum * FPS) - round(s.out0 * FPS))
    return stuecke
