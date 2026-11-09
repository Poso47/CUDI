"""Stil „vollbild“: das ganze Bild bleibt sichtbar, davor ein unscharfer Hintergrund aus demselben Video.

Aufbau (wie im Clipper des Nutzers festgelegt): Hook-Titel oben, Video in voller Breite in der Mitte, Wort-für-Wort-
Untertitel unten, Pausen geschnitten, optional ein Teaser (stärkster Moment vorangestellt). Kein Gesichts-Zuschnitt –
dadurch schnell und ohne Modelle.
"""

from __future__ import annotations

import re

from . import FPS, H, W
from .cuts import Abschnitt, Schnitt
from .subtitles import GELB, WEISS, _anzeige, _zeit

TITEL_Y = 230            # Mitte des Titelblocks (unterhalb der oberen UI-Leiste der Plattformen)
TITEL_GROESSE = 76
WORT_Y = 1380            # Wort-für-Wort-Zeile, oberhalb von Beschreibung/Buttons
WORT_GROESSE = 104
TITEL_MAX = 60


def filter_fn(sw: int, sh: int):
    """ffmpeg-Filterkette je Schnitt: Hintergrund = dasselbe Bild gefüllt + weichgezeichnet, davor das Bild ganz."""
    def f(s: Schnitt) -> str:
        return (f"fps={FPS},split=2[bg][fg];"
                f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:6,eq=brightness=-0.12[b];"
                f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[f];"
                f"[b][f]overlay=(W-w)/2:(H-h)/2,format=yuv420p")
    return f


def plane(abschnitte: list[Abschnitt]) -> list[Schnitt]:
    """Ein Schnitt je behaltenes Intervall (Pausen sind schon herausgenommen), Bildzahlen ohne Drift gerundet."""
    stuecke = [Schnitt(ab.name, a, b) for ab in abschnitte for a, b in ab.intervalle if b - a >= 0.05]
    kum = 0.0
    for s in stuecke:
        s.out0 = kum
        kum += s.dauer
        s.frames = max(1, round(kum * FPS) - round(s.out0 * FPS))
    return stuecke


def titel_text(titel: str) -> str:
    t = re.sub(r"\s+", " ", titel).strip().rstrip(".,;:")
    if len(t) > TITEL_MAX:
        t = t[:TITEL_MAX].rsplit(" ", 1)[0].rstrip(",;:-") + "…"
    return t


def ass_bauen(out_words: list[dict], titel: str, familie: str, fett: bool, dauer: float) -> tuple[str, int]:
    """ASS: Titel oben (ganze Dauer), Wort-für-Wort-Untertitel unten (aktuelles Wort, Zahlen gelb). Gibt (Text, Wörter)."""
    b = -1 if fett else 0
    kopf = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        f"Style: Titel,{familie},{TITEL_GROESSE},&H00FFFFFF,&H00FFFFFF,&H00101010,&H00101010,{b},0,0,0,100,100,1,0,1,6,2,5,70,70,40,1\n"
        f"Style: Wort,{familie},{WORT_GROESSE},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,{b},0,0,0,100,100,1.5,0,1,8,3,5,50,50,40,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    zeilen = []
    t = titel_text(titel).replace("{", "").replace("}", "").replace("\\", "")
    if t:
        zeilen.append(f"Dialogue: 0,{_zeit(0)},{_zeit(dauer)},Titel,,0,0,0,,"
                      "{\\an8\\pos(%d,%d)}%s" % (W // 2, TITEL_Y - 60, t.upper()))
    ws = [w for w in out_words if _anzeige(w["w"])]
    for i, w in enumerate(ws):
        start = w["s"]
        nxt = ws[i + 1]["s"] if i + 1 < len(ws) else None
        ende = w["e"] + 0.08
        if nxt is not None:
            ende = min(max(ende, start + 0.12), nxt)           # nie zwei Wörter gleichzeitig
        ende = min(max(ende, start + 0.12), dauer)
        start = min(start, ende - 0.05)
        wort = _anzeige(w["w"]).replace("{", "").replace("}", "").replace("\\", "")
        farbe = GELB if re.search(r"\d", wort) else WEISS
        text = "{\\an5\\pos(%d,%d)\\c%s\\fscx85\\fscy85\\t(0,70,\\fscx100\\fscy100)}%s" % (W // 2, WORT_Y, farbe, wort)
        zeilen.append(f"Dialogue: 1,{_zeit(start)},{_zeit(ende)},Wort,,0,0,0,,{text}")
    return kopf + "\n".join(zeilen) + "\n", len(ws)
