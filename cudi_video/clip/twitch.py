"""Twitch-Ranking: die meistgesehenen Clips eines Kanals als Countdown-Video (> 60 s, ≤ 175 s).

Die Zuschauer haben die besten Momente dort schon selbst geschnitten, die Aufrufe zeigen, was gezündet hat. Öffentlich,
ohne Login (yt-dlp). Vor allem anderen wird die Erlaubnis des Kanals geprüft (`erlaubnis.py`); jeder geladene Clip muss
laut Metadaten wirklich zu diesem Kanal gehören. Reihenfolge als Countdown: schwächster Moment zuerst, stärkster zuletzt.
Idee aus `ranking.py` des privaten Clippers, hier ohne Ollama und mit dem Vollbild-Stil neu geschrieben.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from . import FPS, MAX_SECONDS, ClipError
from . import cuts, erlaubnis as erlaubnis_mod, render, subtitles, transcribe, vollbild

log = logging.getLogger(__name__)

MIN_TOTAL = 65.0         # etwas über der 60-s-Grenze von TikTok
MAX_TOTAL = 175.0        # Shorts: höchstens 3 Minuten (MAX_SECONDS 179)
MIN_PARTS, MAX_PARTS = 3, 5
SAME_MOMENT = 90         # Clips, die so kurz nacheinander entstanden, zeigen meist denselben Moment (Sekunden)
MIN_CLIP_S = 5.0


def _json(cmd: list[str], timeout: int = 180) -> dict:
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0 or not res.stdout.strip():
        return {}
    return json.loads(res.stdout)


def _liste_holen(login: str, zeitraum: str, limit: int) -> dict:
    return _json(["yt-dlp", "--flat-playlist", "--playlist-end", str(limit), "-J",
                  f"https://www.twitch.tv/{login}/clips?filter=clips&range={zeitraum}"])


def _herunterladen(url: str, ordner: Path) -> Path | None:
    ordner.mkdir(parents=True, exist_ok=True)
    for f in ordner.glob("clip.*"):
        if f.suffix in (".mp4", ".mkv", ".webm"):
            return f
    subprocess.run(["yt-dlp", "--no-playlist", "-f", "best[height<=1080]/best", "--write-info-json",
                    "-o", str(ordner / "clip.%(ext)s"), url], capture_output=True, text=True, timeout=300)
    return next((f for f in ordner.glob("clip.*") if f.suffix in (".mp4", ".mkv", ".webm")), None)


def clips_holen(login: str, zeitraum: str = "7d", limit: int = 40) -> list[dict]:
    """Clips des Kanals im Zeitraum (24hr, 7d, 30d), meistgesehene zuerst. Leer, wenn Twitch nichts liefert."""
    try:
        eintraege = _liste_holen(login, zeitraum, limit).get("entries") or []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    clips = [{"id": str(e.get("id") or ""), "titel": str(e.get("title") or "").strip(),
              "aufrufe": int(e.get("view_count") or 0), "dauer": float(e.get("duration") or 0),
              "zeit": float(e.get("timestamp") or 0), "url": e.get("url")}
             for e in eintraege if e.get("url") and e.get("id")]
    return sorted(clips, key=lambda c: c["aufrufe"], reverse=True)


def unterschiedlich(clips: list[dict]) -> list[dict]:
    """Denselben Moment haben oft mehrere Zuschauer geclippt – nur den meistgesehenen behalten (nach Aufrufen sortiert)."""
    behalten: list[dict] = []
    for c in clips:
        if all(abs(c["zeit"] - k["zeit"]) > SAME_MOMENT or not c["zeit"] for k in behalten):
            behalten.append(c)
    return behalten


def teile_waehlen(kandidaten: list[dict]) -> list[dict]:
    """Aus nach Stärke sortierten Momenten {dauer, ...} so viele nehmen, dass MIN_TOTAL erreicht ist; sonst leer."""
    teile, summe = [], 0.0
    for c in kandidaten:
        if len(teile) >= MAX_PARTS or summe + c["dauer"] > MAX_TOTAL:
            continue
        teile.append(c)
        summe += c["dauer"]
        if len(teile) >= MIN_PARTS and summe >= MIN_TOTAL:
            break
    return teile if len(teile) >= MIN_PARTS and summe >= MIN_TOTAL else []


def _gehoert_zu(login: str, ordner: Path) -> bool:
    """Gehört der geladene Clip laut Metadaten zum Kanal? Ohne Metadaten gilt: ja (die Liste kam vom Kanal selbst)."""
    try:
        meta = json.loads(next(ordner.glob("clip.info.json")).read_text("utf-8"))
    except (StopIteration, OSError, ValueError):
        return True
    gefunden = {str(meta.get(k) or "").lower().lstrip("@") for k in ("creator", "uploader_id", "channel", "uploader")}
    gefunden.discard("")
    return not gefunden or login in gefunden


def _verstehen(video: Path, sprache: str, arbeit: Path) -> tuple[list[dict], list[tuple[float, float]], float]:
    """(Wörter, behaltene Intervalle nach Pausenschnitt, Dauer danach) – die Dauer nach dem Schnitt entscheidet über die Auswahl."""
    arbeit.mkdir(parents=True, exist_ok=True)
    words, _audio, _offset = transcribe.transkribiere(video, arbeit, sprache, 0.0, None)
    _w, _h, vdauer = render_probe(video)
    intervalle = cuts.pausen_intervalle(words) if words else [(0.0, min(vdauer, 60.0))]
    return words, intervalle, sum(b - a for a, b in intervalle)


def _teil_rendern(video: Path, platz: int, titel: str, words: list[dict], intervalle: list[tuple[float, float]],
                  arbeit: Path, ziel: Path) -> dict:
    _w, _h, _v = render_probe(video)
    ab = cuts.Abschnitt("main", intervalle)
    schnitte = vollbild.plane([ab])
    dauer_s = sum(s.frames for s in schnitte) / FPS
    out_words = [{"w": w["w"], "s": round(ab.mappe(w["s"]), 3), "e": round(ab.mappe(w["e"]), 3)} for w in words]
    fontsdir, familie, fett = subtitles.schrift_bereitstellen(arbeit / "fonts")
    kopf = f"#{platz} {titel}".strip()
    ass_text, _n = vollbild.ass_bauen(out_words, kopf, familie, fett, dauer_s)
    ass = arbeit / "untertitel.ass"
    ass.write_text(ass_text, "utf-8")
    dauer = render.rendern(video, schnitte, None, ass, fontsdir, arbeit, ziel, vollbild.filter_fn(_w, _h))
    return {"dauer": dauer, "woerter": len(words), "transkript": " ".join(w["w"] for w in words)}


def render_probe(video: Path) -> tuple[int, int, float]:
    from . import reframe

    return reframe.probe(video)


def _verbinden(dateien: list[Path], ziel: Path, arbeit: Path) -> None:
    liste = arbeit / "ranking_concat.txt"
    liste.write_text("".join(f"file '{d.resolve()}'\n" for d in dateien), "utf-8")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    render._ffmpeg(["-f", "concat", "-safe", "0", "-i", str(liste), "-c", "copy", "-movflags", "+faststart", str(ziel)])


def ranking(login: str, zeitraum: str, sprache: str, ausgabe: Path, arbeit: Path, bestaetigt_erlaubnis: bool = False,
            fortschritt=None, stil: str = "vollbild", min_aufrufe: int = 0) -> dict:
    """Countdown-Video aus den meistgesehenen Clips von `login`. Wirft ClipError (gesperrt/unklar ohne Bestätigung,
    zu wenige Clips, nichts ladbar)."""
    def schritt(text: str, anteil: float = 0.5):
        log.info(text)
        if fortschritt:
            fortschritt(text, anteil)

    login = login.strip().lstrip("@").lower()
    if not re.fullmatch(r"[a-z0-9_]{3,25}", login):
        raise ClipError("Twitch-Kanal: nur der Anmeldename (z. B. „beispielkanal“).")
    schritt("Erlaubnis prüfen", 0.05)
    erl = erlaubnis_mod.pruefe_auftrag(f"https://www.twitch.tv/{login}", bestaetigt_erlaubnis)
    hinweise: list[str] = []
    if stil == "zuschnitt":
        hinweise.append("Twitch-Ranking nutzt immer den Stil „vollbild“ (ganzes Bild) – Facecam und Spielbild bleiben sichtbar.")

    schritt("Clips des Kanals holen", 0.1)
    clips = unterschiedlich([c for c in clips_holen(login, zeitraum) if c["aufrufe"] >= min_aufrufe and c["dauer"] >= MIN_CLIP_S])
    if len(clips) < MIN_PARTS:
        raise ClipError(f"Für ein Ranking gibt es bei {login} im Zeitraum {zeitraum} zu wenige verschiedene Clips "
                        f"({len(clips)}). Anderen Zeitraum (30d) versuchen.", wiederholbar=False)
    arbeit.mkdir(parents=True, exist_ok=True)
    kandidaten: list[dict] = []
    for i, c in enumerate(clips[: MAX_PARTS + 4], 1):     # Reserve, falls Clips nicht ladbar sind
        schritt(f"Clip {i} laden und verstehen", 0.15 + 0.5 * i / (MAX_PARTS + 4))
        cwork = arbeit / f"c{re.sub(r'[^A-Za-z0-9_-]+', '_', c['id'])}"
        try:
            video = _herunterladen(c["url"], cwork)
        except (OSError, subprocess.SubprocessError):
            video = None
        if video is None:
            hinweise.append(f"Clip „{c['titel'] or c['id']}“ nicht ladbar – ausgelassen.")
            continue
        if not _gehoert_zu(login, cwork):
            hinweise.append(f"Clip „{c['titel'] or c['id']}“ gehört laut Metadaten nicht zum Kanal {login} – ausgelassen.")
            continue
        try:
            words, intervalle, dauer = _verstehen(video, sprache, cwork / "r")
        except ClipError:
            continue
        kandidaten.append({**c, "video": video, "arbeit": cwork, "dauer": dauer, "woerter": words, "intervalle": intervalle})
        if len(teile_waehlen(kandidaten)) >= MAX_PARTS:
            break
    teile = teile_waehlen(kandidaten)
    if not teile:
        raise ClipError(f"Ranking nicht möglich: {len(kandidaten)} brauchbare Clips ergeben zusammen weniger als "
                        f"{MIN_TOTAL:.0f} s.")
    n = len(teile)
    dateien, info_teile, transkripte = [], [], []
    for i, t in enumerate(reversed(teile)):                # Countdown: #n zuerst
        platz = n - i
        schritt(f"Platz {platz} rendern", 0.7 + 0.25 * i / n)
        ziel = t["arbeit"] / "teil.mp4"
        r = _teil_rendern(t["video"], platz, t["titel"], t["woerter"], t["intervalle"], t["arbeit"] / "r", ziel)
        dateien.append(ziel)
        transkripte.append(r["transkript"])
        info_teile.append({"platz": platz, "titel": t["titel"], "aufrufe": t["aufrufe"], "url": t["url"],
                           "dauer": round(r["dauer"], 1)})
    endziel = ausgabe / "clip.mp4"
    _verbinden(dateien, endziel, arbeit)
    gesamt = sum(p["dauer"] for p in info_teile)
    if gesamt < 60:
        hinweise.append(f"Ranking ist nur {gesamt:.0f} s lang – TikTok zahlt erst ab einer Minute.")
    if gesamt > MAX_SECONDS:
        hinweise.append(f"Ranking ist {gesamt:.0f} s lang (Shorts erlauben {MAX_SECONDS} s).")
    info_teile.reverse()                                     # Platz 1 zuerst in der Liste
    return {"art": "twitch-ranking", "kanal": login, "zeitraum": zeitraum, "quelle": f"https://www.twitch.tv/{login}/clips",
            "datei": str(endziel), "dauer": round(gesamt, 2), "teile": info_teile, "erlaubnis": erl, "stil": "vollbild",
            "hinweise": hinweise, "transkript": " ".join(transkripte)[:3000]}
