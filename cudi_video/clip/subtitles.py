"""Untertitel: 1–3 Wörter, GROSSBUCHSTABEN, Schlüsselwort gelb, ASS (libass) mit Schriftsuche."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import H, W
from .highlights import STOP, _norm

GELB = "&H00D4FF&"      # #FFD400 in ASS-Reihenfolge (BGR)
WEISS = "&HFFFFFF&"
Y_ANTEIL = 0.63         # Mitte der Zeile bei 63 % der Bildhöhe
SCHRIFTGROESSE = 112
MAX_ZEICHEN = 17


def _anzeige(w: str) -> str:
    """Großbuchstaben, nur ? ! als Satzzeichen behalten."""
    t = re.sub(r"[^\w?!äöüÄÖÜß'%€$-]", "", w.replace("…", ""))
    return t.upper()


def _inhaltswort(w: str, lg: str) -> bool:
    n = _norm(w)
    return bool(n) and (n.isdigit() or (len(n) >= 4 and n not in STOP[lg]))


def gruppen_bilden(words: list[dict], sprache: str | None = "de") -> list[list[dict]]:
    """Gruppen aus 1–3 Wörtern; Satzzeichen beenden eine Gruppe, kurze Füllwörter hängen am Nachbarn."""
    lg = "en" if sprache == "en" else "de"
    gr: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if not _anzeige(w["w"]):
            continue
        if cur:
            laenge = sum(len(_anzeige(x["w"])) + 1 for x in cur) + len(_anzeige(w["w"]))
            voll = len(cur) >= 3 or laenge > MAX_ZEICHEN
            # zwei Inhaltswörter und das dritte ebenfalls -> lieber trennen
            if not voll and len(cur) == 2 and _inhaltswort(cur[0]["w"], lg) and _inhaltswort(cur[1]["w"], lg) \
                    and _inhaltswort(w["w"], lg):
                voll = True
            if voll or w["s"] - cur[-1]["e"] > 0.45:
                gr.append(cur)
                cur = []
        cur.append(w)
        if re.search(r"[.?!,;:…]$", w["w"]):
            gr.append(cur)
            cur = []
    if cur:
        gr.append(cur)
    # einzelne Füllwörter an die vorige/nächste Gruppe hängen, solange es passt
    i = 0
    while i < len(gr):
        g = gr[i]
        if len(g) == 1 and not _inhaltswort(g[0]["w"], lg) and len(_anzeige(g[0]["w"])) <= 4:
            nxt = gr[i + 1] if i + 1 < len(gr) else None
            if nxt and len(nxt) < 3 and not re.search(r"[.?!,;:…]$", g[0]["w"]) \
                    and sum(len(_anzeige(x["w"])) + 1 for x in g + nxt) <= MAX_ZEICHEN + 2:
                gr[i + 1] = g + nxt
                del gr[i]
                continue
        i += 1
    return gr


def schluesselwort(gruppe: list[dict], sprache: str | None = "de") -> int | None:
    """Index des Schlüsselworts: Zahl, sonst längstes Inhaltswort (bei Gleichstand das spätere)."""
    lg = "en" if sprache == "en" else "de"
    for i, w in enumerate(gruppe):
        if _norm(w["w"]).isdigit():
            return i
    kand = [(len(_norm(w["w"])), i) for i, w in enumerate(gruppe) if _inhaltswort(w["w"], lg)]
    return max(kand)[1] if kand else None


def _zeit(t: float) -> str:
    t = max(0.0, t)
    h, rest = divmod(t, 3600)
    m, s = divmod(rest, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def schrift_finden() -> tuple[Path | None, str, bool]:
    """(Datei, Familienname, fett-Flag): Anton/Bebas aus video_assets/fonts, sonst fette Schrift aus render/theme."""
    from .. import config

    for name in ("Anton-Regular.ttf", "BebasNeue-Regular.ttf"):
        p = config.ASSETS_DIR / "fonts" / name
        if p.exists():
            return p, _familie(p, "Anton" if "Anton" in name else "Bebas Neue"), False
    try:
        from ..render import theme

        index = theme._font_index()
        for name in theme.FONT_CANDIDATES["black"] + theme.FONT_CANDIDATES["bold"]:
            if name.lower() in index:
                p = index[name.lower()]
                return p, _familie(p, p.stem), True
    except Exception:  # pragma: no cover
        pass
    return None, "DejaVu Sans", True


def _familie(pfad: Path, standard: str) -> str:
    try:
        from PIL import ImageFont

        return ImageFont.truetype(str(pfad), 20).getname()[0]
    except Exception:
        return standard


def ass_bauen(words: list[dict], sprache: str | None, familie: str, fett: bool, dauer: float) -> tuple[str, int]:
    """ASS-Text und Zahl der Gruppen."""
    kopf = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        f"Style: Clip,{familie},{SCHRIFTGROESSE},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,{-1 if fett else 0},0,0,0,"
        "100,100,1.5,0,1,7,3,5,40,40,40,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    gr = gruppen_bilden(words, sprache)
    zeilen = []
    y = int(H * Y_ANTEIL)
    for gi, g in enumerate(gr):
        start = g[0]["s"]
        nxt = gr[gi + 1][0]["s"] if gi + 1 < len(gr) else None
        ende = g[-1]["e"] + 0.12
        if nxt is not None and nxt - g[-1]["e"] < 0.3:
            ende = nxt
        ende = min(max(ende, start + 0.2), dauer)
        if nxt is not None:
            ende = min(ende, nxt)        # nie zwei eigene Untertitelzeilen gleichzeitig
        start = min(start, ende - 0.05)
        k = schluesselwort(g, sprache)
        teile = []
        for i, w in enumerate(g):
            t = _anzeige(w["w"]).replace("{", "").replace("}", "").replace("\\", "")
            teile.append("{\\c%s}%s{\\c%s}" % (GELB, t, WEISS) if i == k else t)
        text = "{\\pos(%d,%d)\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)}%s" % (W // 2, y, " ".join(teile))
        zeilen.append(f"Dialogue: 0,{_zeit(start)},{_zeit(ende)},Clip,,0,0,0,,{text}")
    return kopf + "\n".join(zeilen) + "\n", len(gr)


def schrift_bereitstellen(ziel: Path) -> tuple[Path, str, bool]:
    """Kopiert die Schrift nach `ziel` (fontsdir für libass); gibt (Ordner, Familie, fett) zurück."""
    datei, familie, fett = schrift_finden()
    ziel.mkdir(parents=True, exist_ok=True)
    if datei is not None:
        shutil.copy(datei, ziel / datei.name)
    return ziel, familie, fett
