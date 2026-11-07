"""Sprecher-Zuschnitt 9:16: Gesichter (OpenCV-Haar-Kaskade), aktive Person = meiste Bewegung im Mund-/Unterbereich."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import ClipError

ANALYSE_FPS = 6          # Bewegungsmessung
ERKENNUNG_ALLE = 3       # Gesichter alle 3 Messbilder = 0,5 s
BREITE = 640             # Analysebreite
ZOOM_NAH = 1.22          # „Nah“; 1.0 = „Halbtotale“


def probe(video: Path) -> tuple[int, int, float]:
    import json

    res = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(video)], capture_output=True, text=True)
    try:
        d = json.loads(res.stdout)
        return int(d["streams"][0]["width"]), int(d["streams"][0]["height"]), float(d["format"]["duration"])
    except (KeyError, IndexError, ValueError) as exc:
        raise ClipError(f"Video nicht lesbar: {video}") from exc


def _frames(video: Path, t0: float, t1: float, w: int, h: int):
    """Graustufen-Bilder mit ANALYSE_FPS (ffmpeg-Pipe, unabhängig vom OpenCV-Videodecoder)."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t0:.3f}", "-t", f"{max(0.2, t1 - t0):.3f}", "-i", str(video),
           "-an", "-vf", f"fps={ANALYSE_FPS},scale={w}:{h},format=gray", "-f", "rawvideo", "-"]
    res = subprocess.run(cmd, capture_output=True)
    data = np.frombuffer(res.stdout, dtype=np.uint8)
    n = len(data) // (w * h)
    return data[: n * w * h].reshape(n, h, w)


@dataclass
class Analyse:
    src_w: int
    src_h: int
    t0: float
    pos: np.ndarray            # [spur, bild, 3] (cx, cy, Gesichtsbreite) in Quellpixeln, NaN = unbekannt
    aktiv: np.ndarray          # [bild] Index der aktiven Spur
    spuren: int = 0
    hinweise: list[str] = field(default_factory=list)

    @property
    def hochformat(self) -> bool:
        return self.src_w / self.src_h <= 9 / 16 * 1.04

    def person_bei(self, t: float) -> int:
        if self.spuren == 0:
            return 0
        i = int(np.clip(round((t - self.t0) * ANALYSE_FPS), 0, len(self.aktiv) - 1))
        return int(self.aktiv[i])

    def wechsel(self, a: float, b: float) -> list[tuple[float, int]]:
        """Zeitpunkte (Quellzeit) im Bereich, an denen die aktive Person wechselt."""
        out = []
        if self.spuren < 2:
            return out
        prev = self.person_bei(a)
        for i in range(int((a - self.t0) * ANALYSE_FPS) + 1, int((b - self.t0) * ANALYSE_FPS) + 1):
            if 0 <= i < len(self.aktiv) and int(self.aktiv[i]) != prev:
                prev = int(self.aktiv[i])
                out.append((self.t0 + i / ANALYSE_FPS, prev))
        return out

    def mitte(self, person: int, a: float, b: float) -> tuple[float, float, float]:
        """Mittleres Gesicht (cx, cy, Breite) der Person im Bereich; ohne Gesicht: Bildmitte."""
        if self.spuren == 0:
            return self.src_w / 2, self.src_h * 0.4, self.src_w * 0.2
        person = min(person, self.spuren - 1)
        i0 = int(np.clip((a - self.t0) * ANALYSE_FPS, 0, self.pos.shape[1] - 1))
        i1 = int(np.clip((b - self.t0) * ANALYSE_FPS + 1, i0 + 1, self.pos.shape[1]))
        teil = self.pos[person, i0:i1]
        if np.isnan(teil[:, 0]).all():
            teil = self.pos[person]
        if np.isnan(teil[:, 0]).all():
            return self.src_w / 2, self.src_h * 0.4, self.src_w * 0.2
        m = np.nanmedian(teil, axis=0)
        return float(m[0]), float(m[1]), float(m[2])


def analysiere(video: Path, t0: float, t1: float, src_w: int, src_h: int) -> Analyse:
    import cv2

    fw = min(BREITE, src_w)
    fh = int(round(src_h * fw / src_w / 2)) * 2
    skala = src_w / fw
    frames = _frames(video, t0, t1, fw, fh)
    n = len(frames)
    leer = Analyse(src_w, src_h, t0, np.full((0, max(n, 1), 3), np.nan), np.zeros(max(n, 1), dtype=int), 0,
                   ["Keine Videobilder analysierbar – Bildmitte verwendet."] if n == 0 else [])
    if n == 0:
        return leer
    kaskaden = []
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):   # OpenCV 5 hat keine Haar-Kaskaden mehr
        kaskaden = [cv2.CascadeClassifier(cv2.data.haarcascades + f) for f in
                    ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml",
                     "haarcascade_profileface.xml")]
    if not kaskaden or any(k.empty() for k in kaskaden):
        leer.hinweise.append("Gesichtserkennung nicht verfügbar (opencv-python-headless 4.x nötig) – Bildmitte verwendet.")
        return leer
    mindest = max(24, int(fh * 0.07))
    spuren: list[dict] = []
    pos_liste: list[list] = []   # je Bild: {spur: (x, y, w)}
    bewegung: list[dict] = []
    prev = None
    for i, bild in enumerate(frames):
        if i % ERKENNUNG_ALLE == 0:
            g = cv2.equalizeHist(bild)
            fl = []
            for k in kaskaden:
                fl = k.detectMultiScale(g, 1.1, 5, minSize=(mindest, mindest))
                if len(fl):
                    break
            for (x, y, w, h) in sorted(fl, key=lambda f: -f[2]):
                cx, cy = x + w / 2, y + h / 2
                bestes, bd = None, 1e9
                for sp in spuren:
                    d = np.hypot(sp["x"] - cx, sp["y"] - cy)
                    if d < bd:
                        bestes, bd = sp, d
                if bestes is not None and bd < 0.9 * max(w, bestes["w"]):
                    a = 0.35
                    bestes["x"] += a * (cx - bestes["x"])
                    bestes["y"] += a * (cy - bestes["y"])
                    bestes["w"] += a * (w - bestes["w"])
                    bestes["n"] += 1
                    bestes["last"] = i
                else:
                    spuren.append({"x": cx, "y": cy, "w": float(w), "n": 1, "last": i})
        pos_liste.append({k: (sp["x"], sp["y"], sp["w"]) for k, sp in enumerate(spuren) if i - sp["last"] <= 4 * ANALYSE_FPS})
        mv = {}
        if prev is not None:
            for k, (x, y, w) in pos_liste[-1].items():
                x0, x1 = int(max(0, x - 0.35 * w)), int(min(fw, x + 0.35 * w))
                y0, y1 = int(max(0, y + 0.1 * w)), int(min(fh, y + 0.75 * w))
                if x1 > x0 and y1 > y0:
                    mv[k] = float(cv2.absdiff(bild[y0:y1, x0:x1], prev[y0:y1, x0:x1]).mean())
        bewegung.append(mv)
        prev = bild
    gueltig = [k for k, sp in enumerate(spuren) if sp["n"] >= 3]
    if not gueltig:
        leer.hinweise.append("Kein Gesicht gefunden – Bildmitte verwendet.")
        return leer
    # Spuren nach horizontaler Lage sortieren (stabile Nummern)
    gueltig.sort(key=lambda k: (spuren[k]["x"], spuren[k]["y"]))
    m = len(gueltig)
    pos = np.full((m, n, 3), np.nan)
    mot = np.zeros((m, n))
    for i in range(n):
        for j, k in enumerate(gueltig):
            if k in pos_liste[i]:
                x, y, w = pos_liste[i][k]
                pos[j, i] = (x * skala, y * skala, w * skala)
            mot[j, i] = bewegung[i].get(k, 0.0)
    # Spuren, die sich räumlich praktisch decken (Doppelerkennung), zusammenführen
    behalten = []
    for j in range(m):
        if all(np.hypot(*(np.nanmedian(pos[j, :, :2], axis=0) - np.nanmedian(pos[o, :, :2], axis=0)))
               > 0.6 * np.nanmedian(pos[o, :, 2]) for o in behalten):
            behalten.append(j)
    pos, mot = pos[behalten], mot[behalten]
    m = len(behalten)
    kern = np.ones(7) / 7
    glatt = np.stack([np.convolve(r, kern, mode="same") for r in mot]) if m else mot
    aktiv = np.zeros(n, dtype=int)
    if m > 1:
        cur, letzter = int(np.argmax(glatt[:, : min(n, 12)].sum(axis=1))), -99
        for i in range(n):
            best = int(np.argmax(glatt[:, i]))
            if best != cur and glatt[best, i] > 1.4 * glatt[cur, i] + 0.05 and i - letzter >= 5:
                cur, letzter = best, i
            aktiv[i] = cur
    return Analyse(src_w, src_h, t0, pos, aktiv, m)


def zuschnitt(an: Analyse, person: int, a: float, b: float, zoom: float) -> tuple[int, int, int, int]:
    """Zuschnittsrechteck (x, y, w, h) in Quellpixeln, Seitenverhältnis 9:16, Gesicht im oberen Bilddrittel-Zentrum."""
    sw, sh = an.src_w, an.src_h
    if sw / sh > 9 / 16:
        ch = sh
        cw = ch * 9 / 16
    else:
        cw = sw
        ch = cw * 16 / 9
    cw, ch = cw / zoom, ch / zoom
    cx, cy, _w = an.mitte(person, a, b)
    x = min(max(cx - cw / 2, 0), sw - cw)
    y = min(max(cy - 0.40 * ch, 0), sh - ch)
    return int(round(x)) // 2 * 2, int(round(y)) // 2 * 2, int(cw) // 2 * 2, int(ch) // 2 * 2
