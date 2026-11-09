"""Bildqualität: Schärfe, Auflösung, Doppelbilder (pHash) und eine Ausschlussliste für offensichtlich falsche Motive.

Gilt für alle Fotos/Clips-Vorschauen, die als Bild eines Platzes, Fakts oder Reportage-Satzes in Frage kommen.
Alles läuft mit PIL + numpy (keine zusätzlichen Pakete); Fehler beim Lesen eines Bildes führen nie zum Abbruch,
das Bild zählt dann einfach nicht.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

MIN_SHORT_SIDE = 700          # kürzere Seite in Pixel (Karten sind 960 breit, Vollbild 1080)
MIN_LONG_SIDE = 1000
MIN_SHARPNESS = 55.0          # Varianz des Laplace-Filters (auf 512 px Breite normiert); Unscharfes liegt meist < 30
DUP_DISTANCE = 8              # pHash: höchstens so viele von 64 Bit verschieden = „dasselbe Bild“

# Offensichtlich falsche Motive bei Orten, Landschaften und Bauwerken (Tags, Titel, Dateinamen): Planeten/Mond,
# Globen, Karten, Logos, Zeichnungen, Computerbilder. Steht das Wort im eigenen Motiv, zählt es nicht als falsch.
EXCLUDE_WORDS = ("planet", "planets", "moon", "mond", "globe", "galaxy", "universe", "astronomy", "map", "maps", "karte",
                 "logo", "icon", "emblem", "cartoon", "clipart", "clip art", "illustration", "vector", "3d", "3d model",
                 "render", "rendering", "wallpaper", "infographic", "diagram", "mockup", "template", "coin", "sticker",
                 "chef", "baby", "toddler", "alpha", "without background", "transparent")
_EXCLUDE = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in sorted(EXCLUDE_WORDS, key=len, reverse=True))
                      + r")(?![a-z0-9])", re.I)


def excluded(text: str, motif: str = "") -> str:
    """Ausschlusswort im Text (Tags/Titel/Dateiname) oder "" – Wörter, die das Motiv selbst nennt, zählen nicht."""
    own = {w.lower() for w in re.findall(r"[a-z0-9]+", (motif or "").lower())}
    for m in _EXCLUDE.finditer(text or ""):
        word = m.group(1).lower()
        if word not in own and not (word in ("map", "maps") and "map" in own):
            return word
    return ""


# --------------------------------------------------------------------------- Bilddaten

def load(path_or_image, max_side: int = 1400) -> Image.Image | None:
    try:
        img = path_or_image if hasattr(path_or_image, "convert") else Image.open(path_or_image)
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:                                   # noqa: BLE001 – kaputte Datei = Bild zählt nicht
        return None
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))
    return img


def sharpness(img: Image.Image) -> float:
    """Varianz des Laplace-Filters auf 512 px Breite (Graustufen) – je höher, desto schärfer."""
    gray = img.convert("L")
    gray = gray.resize((512, max(8, int(gray.height * 512 / gray.width))), Image.BILINEAR)
    a = np.asarray(gray, dtype=np.float32)
    lap = a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return float(lap.var())


def resolution_ok(size: tuple[int, int], min_long: int = MIN_LONG_SIDE, min_short: int = MIN_SHORT_SIDE) -> bool:
    return max(size) >= min_long and min(size) >= min_short


_DCT: np.ndarray | None = None


def _dct_matrix(n: int = 32) -> np.ndarray:
    global _DCT
    if _DCT is None:
        k, i = np.mgrid[0:n, 0:n]
        m = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2 / n)
        m[0] /= np.sqrt(2)
        _DCT = m.astype(np.float32)
    return _DCT


def phash(img: Image.Image) -> int:
    """Wahrnehmungs-Hash (64 Bit): 32×32 Graustufen -> DCT -> obere linke 8×8 gegen den Median."""
    a = np.asarray(img.convert("L").resize((32, 32), Image.LANCZOS), dtype=np.float32)
    m = _dct_matrix()
    low = (m @ a @ m.T)[:8, :8].ravel()
    bits = low > np.median(low[1:])
    return int("".join("1" if b else "0" for b in bits), 2)


def distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


class Seen:
    """Merkt sich die Hashes schon verwendeter Bilder, damit kein Bild (auch nicht in anderer Größe/Quelle) doppelt kommt."""

    def __init__(self) -> None:
        self.hashes: list[int] = []

    def duplicate(self, img: Image.Image) -> bool:
        h = phash(img)
        return any(distance(h, x) <= DUP_DISTANCE for x in self.hashes)

    def add(self, img: Image.Image) -> None:
        self.hashes.append(phash(img))


def check(path, seen: Seen | None = None, min_long: int = MIN_LONG_SIDE) -> tuple[bool, str]:
    """(taugt das Bild?, Grund bei Nein): Auflösung, Schärfe, Doppelbild (gegen `seen`; mit `remember` vormerken)."""
    img = load(path, max_side=3000)
    if img is None:
        return False, "nicht lesbar"
    # load() verkleinert nur große Bilder; die Originalgröße steht in der Datei
    try:
        with Image.open(path) as raw:
            size = raw.size
    except Exception:                                   # noqa: BLE001
        size = img.size
    if not resolution_ok(size, min_long):
        return False, f"zu klein ({size[0]}×{size[1]})"
    if (s := sharpness(img)) < MIN_SHARPNESS:
        return False, f"unscharf ({s:.0f})"
    if seen is not None:
        if seen.duplicate(img):
            return False, "Doppelbild"
    return True, ""


def check_file_name(name: str) -> str:
    """Dateiname/Titel eines Treffers: Ausschlusswort oder ""."""
    return excluded(Path(str(name)).stem.replace("_", " ").replace("-", " "))


def remember(seen: Seen | None, path) -> None:
    """Angenommenes Bild für die Doppelbild-Prüfung vormerken."""
    img = load(path, max_side=600) if seen is not None else None
    if img is not None:
        seen.add(img)
