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


YUNET_NAME = "face_detection_yunet_2023mar.onnx"
YUNET_URLS = (
    "https://huggingface.co/opencv/face_detection_yunet/resolve/main/" + YUNET_NAME,
    "https://cdn.jsdelivr.net/gh/opencv/opencv_zoo@main/models/face_detection_yunet/" + YUNET_NAME,
)


def yunet_modell() -> Path | None:
    """YuNet (OpenCV Zoo, MIT-Lizenz, 230 KB): einmal laden, unter video_output/_models zwischenspeichern."""
    import os

    from .. import config

    env = os.environ.get("CUDI_YUNET_MODELL")
    if env and Path(env).is_file():
        return Path(env)
    ziel = config.OUTPUT_DIR / "_models" / YUNET_NAME
    if ziel.is_file() and ziel.stat().st_size > 100_000:
        return ziel
    try:
        import requests
    except ImportError:  # pragma: no cover
        return None
    for url in YUNET_URLS:
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 100_000:
                ziel.parent.mkdir(parents=True, exist_ok=True)
                ziel.write_bytes(r.content)
                return ziel
        except requests.RequestException:
            continue
    return None


def _detektor(fw: int, fh: int):
    """Funktion Graubild -> [(x, y, w, h)]: YuNet (cv2.FaceDetectorYN, auch OpenCV 5), sonst Haar-Kaskade, sonst None."""
    import cv2

    if hasattr(cv2, "FaceDetectorYN"):
        modell = yunet_modell()
        if modell is not None:
            try:
                yn = cv2.FaceDetectorYN.create(str(modell), "", (fw, fh), 0.6, 0.3, 50)

                def erkenne_yunet(bild):
                    _ok, res = yn.detect(cv2.cvtColor(bild, cv2.COLOR_GRAY2BGR))
                    return [(int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in (res if res is not None else [])]

                return erkenne_yunet
            except cv2.error:
                pass
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
        kask = [cv2.CascadeClassifier(cv2.data.haarcascades + f) for f in
                ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml", "haarcascade_profileface.xml")]
        if not any(k.empty() for k in kask):
            def erkenne_haar(bild):
                g = cv2.equalizeHist(bild)
                for k in kask:
                    fl = k.detectMultiScale(g, 1.1, 5, minSize=(24, 24))
                    if len(fl):
                        return [tuple(int(v) for v in f) for f in fl]
                return []

            return erkenne_haar
    return None


def _glaetten(pos: np.ndarray, fenster: int = 5) -> np.ndarray:
    """Ausreißer-Erkennungen je Spur per gleitendem Median (ca. 0,8 s) glätten; NaN (Person nicht im Bild) bleibt NaN."""
    out = pos.copy()
    h = fenster // 2
    for k in range(pos.shape[0]):
        for c in range(3):
            r = pos[k, :, c]
            for i in range(len(r)):
                if np.isnan(r[i]):
                    continue
                teil = r[max(0, i - h):i + h + 1]
                out[k, i, c] = np.median(teil[~np.isnan(teil)])
    return out


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
    detektor = _detektor(fw, fh)
    if detektor is None:
        leer.hinweise.append("Gesichtserkennung nicht verfügbar (weder YuNet-Modell noch Haar-Kaskade) – Bildmitte verwendet.")
        return leer
    mindest = max(24, int(fh * 0.07))
    spuren: list[dict] = []
    pos_liste: list[list] = []   # je Bild: {spur: (x, y, w)}
    bewegung: list[dict] = []
    prev = None
    for i, bild in enumerate(frames):
        if i % ERKENNUNG_ALLE == 0:
            fl = [f for f in detektor(bild) if f[2] >= mindest]
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
    gueltig = [k for k, sp in enumerate(spuren) if sp["n"] >= 2]
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
    pos, mot = _glaetten(pos[behalten]), mot[behalten]
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
    cx, cy, fw = an.mitte(person, a, b)
    if zoom > 1.0 and an.spuren and fw / (cw / zoom) > 0.6:
        zoom = 1.0       # Gesicht füllt schon fast die Breite: kein weiteres Heranzoomen (Stirn/Kinn blieben abgeschnitten)
    ch0, cw0 = ch, cw
    if an.spuren:        # Augenlinie (ca. 12 % der Gesichtsbreite über der Boxmitte) höchstens bei 45 % der Bildhöhe
        augen = cy - 0.12 * fw
        stufen = sorted({zoom, 1.0} | {round(zoom - 0.05 * i, 2) for i in range(1, 6) if zoom - 0.05 * i > 1.0}, reverse=True)
        for z in stufen:
            hoehe = ch0 / z
            yy = min(max(cy - 0.38 * hoehe, 0), sh - hoehe)
            zoom = z
            if (augen - yy) / hoehe <= 0.45:
                break
    cw, ch = cw0 / zoom, ch0 / zoom
    x = min(max(cx - cw / 2, 0), sw - cw)
    y = min(max(cy - 0.38 * ch, 0), sh - ch)
    return int(round(x)) // 2 * 2, int(round(y)) // 2 * 2, int(cw) // 2 * 2, int(ch) // 2 * 2
