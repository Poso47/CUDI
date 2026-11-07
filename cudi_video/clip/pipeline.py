"""Gesamtablauf der Clip-Engine."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from .. import config
from . import FPS, MAX_SECONDS, ClipError
from . import cuts, highlights, reframe, render, source, subtitles, transcribe

log = logging.getLogger(__name__)


def _ausschnitt(words: list[dict], a: float, b: float) -> list[dict]:
    return [w for w in words if w["s"] >= a - 0.01 and w["e"] <= b + 0.01]


def _kuerzen(words: list[dict], limit: float, reserve: float) -> list[dict]:
    """Wörter am Satzende kürzen, bis Hauptteil (nach Pausenschnitt) + Reserve in `limit` passt."""
    def dauer(ws):
        return sum(b - a for a, b in cuts.pausen_intervalle(ws))

    ws = list(words)
    while len(ws) > 5 and dauer(ws) + reserve > limit:
        sats = highlights.saetze_bilden(ws)
        ws = ws[: sats[-1].i0] if len(sats) > 1 else ws[: len(ws) * 9 // 10]
    return ws


def make_clip(quelle: str, start: float | None = None, ende: float | None = None, sprache: str | None = "de",
              max_laenge: float = 90.0, name: str | None = None, fortschritt=None) -> dict:
    def schritt(text: str):
        log.info(text)
        if fortschritt:
            fortschritt(text)

    if start is not None and ende is not None and ende <= start:
        raise ClipError("--ende muss größer als --start sein.")
    stem = name or source.slug(Path(quelle).stem if not source.ist_url(quelle) else quelle.rstrip("/").split("/")[-1].split("?")[-1])
    arbeit = config.OUTPUT_DIR / "_work" / f"clip_{stem}"
    ausgabe = config.OUTPUT_DIR / "clips" / stem
    arbeit.mkdir(parents=True, exist_ok=True)

    schritt("Quelle beschaffen")
    video = source.beschaffen(quelle, arbeit)
    sw, sh, vdauer = reframe.probe(video)
    forced = start is not None or ende is not None
    t_start = max(0.0, start or 0.0)
    t_ende = min(ende if ende is not None else vdauer, vdauer)

    schritt("Spracherkennung")
    words, audio, offset = transcribe.transkribiere(video, arbeit, sprache, t_start if forced else 0.0,
                                                    t_ende if forced else None)
    rms = transcribe.lautstaerke(audio)
    median = float(np.median(rms[rms > 1e-5])) if (rms > 1e-5).any() else 1e-5

    def laut(a: float, b: float) -> float:
        i, j = int((a - offset) / 0.1), int((b - offset) / 0.1) + 1
        seg = rms[max(0, i):max(i + 1, j)]
        return float(seg.mean()) / median if len(seg) else 1.0

    schritt("Höhepunkt suchen")
    saetze = highlights.saetze_bilden(words)
    highlights.bewerte(saetze, words, rms, offset, sprache)
    max_fenster = min(max_laenge, MAX_SECONDS - 10)
    if forced:
        fenster = highlights.fenster_erzwingen(saetze, t_start, t_ende)
    else:
        fenster = highlights.fenster_finden(saetze, 30.0, max_fenster)
    fw = _ausschnitt(words, fenster.start, fenster.ende)
    if not fw:
        raise ClipError("Im gewählten Bereich wurde nichts gesprochen.")
    hook = highlights.hook_finden(fenster)
    teaser = hook is not None and highlights.braucht_teaser(hook, fenster)
    reserve = (hook.dauer + cuts.BLITZ + 0.2) if teaser else 0.0
    fw = _kuerzen(fw, MAX_SECONDS - 1.0, reserve)
    if teaser and hook.ende > fw[-1]["e"]:
        teaser = False

    schritt("Gesichter und Sprecher analysieren")
    an = reframe.analysiere(video, fw[0]["s"], fw[-1]["e"] + 0.3, sw, sh)

    schritt("Schnittplan")
    ab_main = cuts.Abschnitt("main", cuts.pausen_intervalle(fw))
    abschnitte = [ab_main]
    hook_words: list[dict] = []
    ab_teaser = None
    if teaser:
        hook_words = words[hook.i0:hook.i1 + 1]
        ab_teaser = cuts.Abschnitt("teaser", cuts.pausen_intervalle(hook_words))
        abschnitte = [ab_teaser, ab_main]
    schnitte = cuts.plane(abschnitte, an, words, laut, hook.ende if teaser else None, blitz=teaser)
    erste_main = next(s for s in schnitte if s.art == "main")
    ab_main.out0 = erste_main.out0
    if ab_teaser:
        ab_teaser.out0 = 0.0
    gesamt = sum(s.frames for s in schnitte) / FPS

    def mappe(ws, ab):
        return [{"w": w["w"], "s": round(ab.mappe(w["s"]), 3), "e": round(ab.mappe(w["e"]), 3)} for w in ws]

    out_words = (mappe(hook_words, ab_teaser) if ab_teaser else []) + mappe(fw, ab_main)

    schritt("Untertitel")
    fontsdir, familie, fett = subtitles.schrift_bereitstellen(arbeit / "fonts")
    ass_text, n_gruppen = subtitles.ass_bauen(out_words, sprache, familie, fett, gesamt)
    ass = arbeit / "untertitel.ass"
    ass.write_text(ass_text, "utf-8")

    schritt(f"Rendern ({len(schnitte)} Schnitte)")
    ziel = ausgabe / "clip.mp4"
    dauer = render.rendern(video, schnitte, an, ass, fontsdir, arbeit, ziel)

    info = {
        "quelle": quelle,
        "datei": str(ziel),
        "dauer": round(dauer, 2),
        "fenster": {"start": round(fw[0]["s"], 2), "ende": round(fw[-1]["e"], 2), "erzwungen": forced,
                    "wert": round(fenster.wert, 2)},
        "hook": ({"text": hook.text, "start": round(hook.start, 2), "ende": round(hook.ende, 2),
                  "wert": round(hook.hook_wert, 2), "teaser_vorangestellt": bool(teaser)} if hook else None),
        "pausen_entfernt_s": round((fw[-1]["e"] - fw[0]["s"]) - ab_main.dauer, 2),
        "personen": an.spuren,
        "hinweise": an.hinweise,
        "schnitte": [{"art": s.art, "ausgabe_start": round(s.out0, 2), "dauer": round(s.frames / FPS, 2),
                      "quelle_start": round(s.a, 2), "person": s.person, "zoom": s.zoom, "punch": s.punch}
                     for s in schnitte],
        "untertitel": {"gruppen": n_gruppen, "schrift": familie},
        "transkript": " ".join(w["w"] for w in fw),
        "woerter": out_words,
    }
    ausgabe.mkdir(parents=True, exist_ok=True)
    (ausgabe / "clip.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), "utf-8")
    return info
