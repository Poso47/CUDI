"""Auftrag aus der CUDI-App in Claude – ein Befehl von der Eingabe bis zur fertigen App-Fassung.

Die CUDI-App-Seite startet für jeden Auftrag eine Claude-Sitzung in der Cloud. Diese führt aus:

  bash scripts/cudi_auftrag.sh '<json>'                       rendern (Ordner video_output/auftrag-<id>)
  bash scripts/cudi_auftrag.sh --weiter <id>                  nach Claudes Übersetzung weiterrendern
  python -m cudi_video auftrag --dokument <id> --adressen '{"<datei>": "<url>"}'
                                                              Dokument für die Ablage der App-Seite

Zeilen, auf die die Sitzung achtet:
  UEBERSETZEN: <datei>   Story in anderer Sprache und kein Übersetzungsdienst: Claude übersetzt die Texte
  SCHREIBEN: <datei>     (nur mit CUDI_SCHREIBEN=1) Claude deutet ein freies Thema oder erzählt das Ranking
                         (handoff.py); der Code prüft jede Antwort und hat immer einen Ausweichweg
  DATEIEN: [...]         in die App hochzuladen (App-Fassungen ≤ 19 MB und Titelbilder)
  ERGEBNIS: <datei>      Ergebnis (auch bei Fehlern – dann mit Fehlermeldung)

Die App-Fassung passt in die Ablage der App-Seite (höchstens 20 MiB je Datei): 1080×1920, Bitrate aus
der Dauer berechnet. Gemessen: Ranking 155 s -> 15,7 MB bei SSIM 0,995; Story 107 s -> 13,1 MB.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import config, handoff

log = logging.getLogger(__name__)

APP_BUDGET = 19 * 1024 * 1024          # Ablage der App-Seite: 20 MiB je Datei, etwas Luft
LONG_APP_BUDGET = 150 * 1024 * 1024    # lange Videos (> 3 Min.): ganze Datei, in Stücken ≤ APP_BUDGET abgelegt
AUDIO_BPS = 96_000
MAX_REVIEW = 40_000
MOODS = ("auto", "creepy", "suspense", "funny", "drama", "revenge", "wholesome")
TRANSLATION_FILE = "uebersetzen.json"
EXIT_TRANSLATE = 3
EXIT_WRITE = 4
RETRY_PAUSE = 60                       # Sekunden Pause vor dem zweiten Versuch nach einer Störung
# Story in zwei Schritten: „skelett“ (suchen, übersetzen, Lektorat -> Skelett in die App) und „video“
# (aus dem in der App bearbeiteten Skelett rendern). Leer = alles in einem Lauf.
STEPS = ("", "skelett", "video")
SKELETON_DIR = "cudi_skelette"         # dorthin legt die Sitzung das bearbeitete Skelett (ArtifactData out_dir)


class OrderError(ValueError):
    pass


# --------------------------------------------------------------------------- Eingaben prüfen

def _text(value, limit: int) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "")).strip()
    return re.sub(r"\s+", " ", text)[:limit]


def _flag(value, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "ja", "yes", "an")


def _upload_wish(raw) -> dict | None:
    """Auftragsfeld „hochladen“ (Standard aus): {"ziel": youtube|tiktok|beide, "sichtbarkeit": privat|ungelistet|oeffentlich}
    oder nur der Zielname. Nur Backend – Zugangsdaten stehen in Umgebungsvariablen (docs/upload-einrichten.md)."""
    if not raw:
        return None
    wish = raw if isinstance(raw, dict) else {"ziel": raw}
    target = str(wish.get("ziel") or "").strip().lower()
    if target in ("1", "true", "ja"):
        target = "youtube"
    if target not in ("youtube", "tiktok", "beide"):
        raise OrderError("Hochladen: „youtube“, „tiktok“ oder „beide“.")
    visibility = str(wish.get("sichtbarkeit") or "privat").lower().replace("ö", "oe")
    if visibility not in ("privat", "ungelistet", "oeffentlich"):
        raise OrderError("Sichtbarkeit: privat, ungelistet oder oeffentlich.")
    return {"ziel": target, "sichtbarkeit": visibility}


def _seconds(value, name: str) -> float | None:
    """Zeitangabe als Sekunden (Zahl) oder „m:ss“ / „h:mm:ss“; leer = nicht angegeben."""
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().replace(",", ".")
    try:
        if ":" in text:
            parts = [float(p) for p in text.split(":")]
            if not 2 <= len(parts) <= 3 or any(p < 0 for p in parts):
                raise ValueError
            seconds = 0.0
            for p in parts:
                seconds = seconds * 60 + p
        else:
            seconds = float(text)
    except ValueError:
        raise OrderError(f"{name}: bitte Sekunden oder Minuten:Sekunden angeben (z. B. 90 oder 1:30).") from None
    if not 0 <= seconds <= 86400:
        raise OrderError(f"{name}: außerhalb des erlaubten Bereichs.")
    return round(seconds, 2)


def _clip_url(value) -> str:
    """Nur öffentliche http(s)-Adressen – keine lokalen oder privaten Ziele (Datei-Upload kommt später)."""
    url = str(value or "").strip()
    if not url:
        raise OrderError("Clip: bitte den Link zum Video angeben.")
    if len(url) > 500 or re.search(r"\s", url):
        raise OrderError("Clip: ungültiger Link.")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        raise OrderError("Clip: bitte einen vollständigen Link (https://…) angeben.")
    if host == "localhost" or re.fullmatch(r"(127|10|0)\.[\d.]+|192\.168\.[\d.]+|169\.254\.[\d.]+|172\.(1[6-9]|2\d|3[01])\.[\d.]+", host):
        raise OrderError("Clip: lokale Adressen sind nicht erlaubt.")
    if "." not in host:
        raise OrderError("Clip: bitte einen vollständigen Link (https://…) angeben.")
    return url


def parse_preferences(raw) -> dict:
    """Vorlieben aus den Bewertungen der App: {"gut": [...], "schlecht": [...]}, je höchstens 8 kurze Einträge."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key in ("gut", "schlecht"):
        items = raw.get(key) if isinstance(raw.get(key), list) else []
        clean = [_text(x, 160) for x in items[:8] if isinstance(x, str)]
        if any(clean):
            out[key] = [c for c in clean if c]
    return out


FORMAT_ENV = "CUDI_FORMAT"


def _format(value) -> str:
    """Video-Format aus dem Auftrag: leer/„auto“ = je Video ein anderes, sonst ein Name aus theme.FORMAT_NAMES.
    Die Farben passen sich immer dem Thema an."""
    from .render.theme import FORMAT_NAMES

    name = str(value or "").strip().lower()
    if name in ("", "auto"):
        return ""
    if name not in FORMAT_NAMES:
        raise OrderError(f"Unbekanntes Format „{name}“ – erlaubt: {', '.join(FORMAT_NAMES)}.")
    return name


def parse_order(raw: dict, presets: set[str]) -> dict:
    """Auftrag der App-Seite prüfen: nur bekannte Felder und erlaubte Werte."""
    order = _parse_order(raw, presets)
    prefs = parse_preferences(raw.get("vorlieben"))
    if prefs:
        order["vorlieben"] = prefs
    return order


def _parse_order(raw: dict, presets: set[str]) -> dict:
    if not isinstance(raw, dict):
        raise OrderError("Auftrag muss ein JSON-Objekt sein.")
    job_id = str(raw.get("id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,40}", job_id):
        raise OrderError("Auftrag ohne gültige Kennung.")
    kind = raw.get("art")
    if kind == "ranking":
        topic, preset = _text(raw.get("thema"), 120), str(raw.get("vorlage") or "")
        if not topic and preset not in presets:
            raise OrderError(f"Unbekannte Vorlage „{preset}“.")
        langs = [l for l in ("de", "en") if l in (raw.get("sprachen") or ["de", "en"])]
        if not langs:
            raise OrderError("Mindestens eine Sprache wählen.")
        length = str(raw.get("laenge") or "")
        if length not in ("", "lang"):
            raise OrderError("Länge: leer (bis 3 Minuten) oder „lang“ (bis 10 Minuten).")
        most = 30 if length == "lang" else 20                 # lange Videos: mehr Plätze
        try:
            count = int(raw.get("plaetze", 10))
        except (TypeError, ValueError):
            raise OrderError(f"Plätze: bitte eine Zahl von 3 bis {most}.") from None
        if not 3 <= count <= most:
            raise OrderError(f"Plätze: bitte eine Zahl von 3 bis {most}.")
        return {"id": job_id, "art": "ranking", "thema": topic, "vorlage": preset, "sprachen": langs,
                "plaetze": count, "streng": _flag(raw.get("streng"), False), "laenge": length,
                "nur_skript": _flag(raw.get("nur_skript"), False), "maskottchen": _flag(raw.get("maskottchen"), None),
                "format": _format(raw.get("format")), "hochladen": _upload_wish(raw.get("hochladen"))}
    if kind == "story":
        wish = _text(raw.get("wunsch"), 300)
        mood = str(raw.get("stimmung") or "auto")
        if mood not in MOODS:
            raise OrderError(f"Unbekannte Stimmung „{mood}“.")
        if not wish and mood == "auto":
            raise OrderError("Stimmung wählen oder kurz beschreiben, was für eine Story es sein soll.")
        lang = raw.get("sprache") or "de"
        length = raw.get("laenge") or "3min"
        visuals = raw.get("bilder") or "videos"
        if lang not in ("de", "en") or length not in ("kurz", "3min", "teile", "lang") or visuals not in ("videos", "images", "gameplay", "cartoon"):
            raise OrderError("Sprache, Länge oder Bilder ungültig.")
        step = str(raw.get("schritt") or "")
        if step not in STEPS:
            raise OrderError("Unbekannter Schritt – „skelett“, „video“ oder leer.")
        return {"id": job_id, "art": "story", "wunsch": wish, "stimmung": mood, "sprache": lang,
                "laenge": length, "bilder": visuals, "entschaerfen": _flag(raw.get("entschaerfen"), True),
                "schritt": step, "maskottchen": _flag(raw.get("maskottchen"), None),
                "hochladen": _upload_wish(raw.get("hochladen"))}
    if kind == "clip":
        if not _flag(raw.get("bestaetigt_erlaubnis"), False):
            raise OrderError("Clip: Bitte bestätigen, dass du die Erlaubnis des Creators zum Clippen hast "
                             "(bestaetigt_erlaubnis).")
        start, end = _seconds(raw.get("start"), "Start"), _seconds(raw.get("ende"), "Ende")
        if start is not None and end is not None:
            if end <= start:
                raise OrderError("Ende muss nach dem Start liegen.")
            if end - start > 175:
                raise OrderError("Der Ausschnitt darf höchstens 175 Sekunden lang sein.")
        lang = str(raw.get("sprache") or "de")
        if lang not in ("de", "en", "auto"):
            raise OrderError("Sprache: „de“, „en“ oder „auto“.")
        try:
            length = int(float(raw.get("laenge") or 90))
        except (TypeError, ValueError):
            raise OrderError("Länge: Sekunden von 30 bis 170.") from None
        if not 30 <= length <= 170:
            raise OrderError("Länge: Sekunden von 30 bis 170.")
        return {"id": job_id, "art": "clip", "quelle": _clip_url(raw.get("quelle")), "start": start, "ende": end,
                "sprache": lang, "laenge": length, "format": _format(raw.get("format")), "bestaetigt_erlaubnis": True,
                "hochladen": _upload_wish(raw.get("hochladen"))}
    raise OrderError("Unbekannte Art – „ranking“, „story“ oder „clip“.")


def job_folder(job_id: str) -> Path:
    return config.OUTPUT_DIR / f"auftrag-{job_id}"


# --------------------------------------------------------------------------- App-Fassung

def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def app_version(src: Path, dst: Path, budget: int = APP_BUDGET) -> Path:
    """Fassung für die App-Ablage: ≤ budget Bytes, Bitrate aus der Dauer, Qualität so hoch wie möglich."""
    if src.stat().st_size <= budget:
        shutil.copyfile(src, dst)
        return dst
    seconds = max(_duration(src), 1.0)
    for scale, share in (("1080:-2", 0.95), ("1080:-2", 0.82), ("720:-2", 0.82)):
        video_bps = max(250_000, int((budget * 8 / seconds - AUDIO_BPS) * share))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", f"scale={scale}:flags=lanczos",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", str(video_bps),
                        "-bufsize", str(video_bps * 2), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(dst)], check=True)
        if dst.stat().st_size <= budget:
            return dst
    raise RuntimeError(f"{src.name}: App-Fassung bleibt über {budget / 1048576:.0f} MB")


def split_for_app(path: Path, size: int = APP_BUDGET) -> list[Path]:
    """Datei in Stücke ≤ size teilen (Ablage: 20 MiB je Datei). Die App setzt die Bytes wieder zusammen –
    das ergibt genau die ursprüngliche MP4-Datei. Kleine Dateien bleiben ein Stück."""
    if path.stat().st_size <= size:
        return [path]
    chunks = []
    with open(path, "rb") as src:
        for n in range(1, 1000):
            data = src.read(size)
            if not data:
                break
            chunk = path.with_name(f"{path.stem}_stueck{n:02d}.mp4")
            chunk.write_bytes(data)
            chunks.append(chunk)
    return chunks


# --------------------------------------------------------------------------- Rendern

def _read(path: Path, limit: int = 20_000) -> str:
    try:
        return path.read_text("utf-8")[:limit]
    except OSError:
        return ""


def _summary(order: dict, result: dict | None, error: str = "") -> dict:
    """ergebnis.json: alles, was die App zeigt – Videos (App-Fassung), Texte, Hinweise, Prüfbericht."""
    data = {"id": order["id"], "art": order["art"], "ok": False, "titel": "", "fehler": error, "videos": [],
            "hinweise": [], "pruefbericht": "", "ordner": ""}
    if result is None:
        return data
    out = Path(result["output_dir"])
    data["ordner"] = str(out)
    from . import tts
    data["hinweise"] = (tts.take_notes() + list(result.get("warnings", [])))[:20]
    if result.get("skelett"):
        data["schritt"], data["skelett"] = "skelett", result["skelett"]
    spec = out / "spec.json"
    if spec.exists():
        titles = json.loads(spec.read_text("utf-8")).get("title", {})
        data["titel"] = titles.get("de") or next(iter(titles.values()), "")
    for key, files in result.get("videos", {}).items():
        video = out / files["video"]
        long_video = (files.get("duration") or _duration(video)) > 185
        app = app_version(video, video.with_name(video.stem + "_app.mp4"), LONG_APP_BUDGET if long_video else APP_BUDGET)
        chunks = split_for_app(app)
        cover = out / files["cover"] if files.get("cover") and (out / files["cover"]).exists() else None
        data["videos"].append({
            "key": key, "video": str(app), "cover": str(cover) if cover else None,
            "teile": [str(c) for c in chunks] if len(chunks) > 1 else [],
            "dauer": files.get("duration"), "mb": round(app.stat().st_size / 1048576, 1),
            "youtube": _read(out / files["description_file"]) if files.get("description_file") else "",
            "tiktok": _read(out / files["caption_file"]) if files.get("caption_file") else "",
        })
    data["pruefbericht"] = _read(out / "review.md", MAX_REVIEW)
    data["ok"] = True
    return data


def _ranking(order: dict, folder: Path, progress) -> dict:
    from .__main__ import _load
    from .pipeline import run

    from .planner import plan_with_claude
    from .spec import VideoSpec
    from .topics import PlanError

    try:
        spec = _load(order["thema"] or order["vorlage"], order["plaetze"])
    except PlanError as exc:                             # Thema außerhalb der Vorlagen: Claude deutet es
        planned = plan_with_claude(order["thema"], order["plaetze"]) if order["thema"] else None
        if planned is None:
            raise
        spec = VideoSpec.from_dict(planned)
        print(f"  Thema verstanden: {spec.title['de']}", flush=True)
        log.info("Thema per Claude geplant (Stichwort-Planer: %s): %s", exc, planned)
    if order.get("laenge") == "lang":                    # bis 10 Minuten: mehr Plätze, ausführlicher erzählt
        spec.target_seconds = int(min(config.LONG_MAX_SECONDS - 10, 30 + 22 * order["plaetze"]))
    out = folder / "video"
    out.mkdir(parents=True, exist_ok=True)
    return run(spec, out=out, langs=order["sprachen"], render=not order["nur_skript"], strict=order["streng"],
               progress=progress)


def app_skeleton(job_id: str, wait: int = 60) -> dict:
    """Das in der App bearbeitete Skelett (Sammlung „skelette“, von der Sitzung als Datei abgelegt)."""
    root = Path(__file__).resolve().parent.parent
    candidates = [base / SKELETON_DIR / "skelette" / f"{job_id}.json"
                  for base in dict.fromkeys((Path.cwd().parent, root.parent, Path.cwd(), Path.home()))]
    candidates.append(config.OUTPUT_DIR / "app" / "skelette" / f"{job_id}.json")
    deadline = time.time() + wait
    while True:
        for path in candidates:
            if path.exists():
                data = json.loads(path.read_text("utf-8"))
                return data["data"] if isinstance(data.get("data"), dict) and "parts" not in data else data
        if time.time() >= deadline:
            raise RuntimeError("Das bearbeitete Skelett ist nicht angekommen – bitte in der App erneut „Video erstellen“.")
        time.sleep(5)                                   # kommt die Datei gerade erst an: kurz warten


def fit_parts(skeleton: dict) -> list[str]:
    """Nach der Bearbeitung in der App: Teile so ordnen, dass jeder ≤ Höchstlänge bleibt (zu lange Szenen
    satzweise teilen, Szenen auf Teile verteilen), Einstiege/Abschlüsse passend zu Titel und Teilezahl."""
    from .story.editor import FOLLOW, INTRO_PART, OUTRO_NEXT
    from .story.moods import MOODS, seconds_per_word
    from .story.sources import OVERHEAD_SECONDS

    lang, mood, title = skeleton["lang"], skeleton["mood"], skeleton["title"]
    per_word = seconds_per_word(mood, lang)
    limit = (config.LONG_MAX_SECONDS if skeleton.get("length") == "lang" else config.STORY_MAX_SECONDS) - OVERHEAD_SECONDS
    secs = lambda scene: len(str(scene.get("text", "")).split()) * per_word
    hook = str(skeleton.get("hook") or "")             # Einstieg statt Titel: Teil 1 wird länger
    limit -= max(0.0, (len(hook.split()) - len(title.split())) * per_word)
    next_outro = re.compile(re.escape(OUTRO_NEXT[lang]).replace(r"\{n\}", r"\d+"))
    final = next((p["outro"] for p in reversed(skeleton["parts"]) if p.get("outro") and not next_outro.fullmatch(p["outro"])),
                 f"{MOODS[mood]['outro'][lang]} {FOLLOW[lang]}")
    notes = []
    scenes = []
    for scene in (s for p in skeleton["parts"] for s in p["scenes"]):
        if secs(scene) <= limit:
            scenes.append(scene)
            continue
        chunk = []                                           # sehr lange Szene: satzweise aufteilen
        for sentence in re.split(r"(?<=[.!?…])\s+", str(scene["text"]).strip()):
            if chunk and secs({"text": " ".join(chunk + [sentence])}) > limit:
                scenes.append({**scene, "text": " ".join(chunk)})
                chunk = []
            chunk.append(sentence)
        if chunk:
            scenes.append({**scene, "text": " ".join(chunk)})
    too_long = any(sum(secs(s) for s in p["scenes"]) > limit for p in skeleton["parts"])
    if too_long:                                             # neu verteilen, sonst die Aufteilung behalten
        groups, current, total = [], [], 0.0
        for scene in scenes:
            if current and total + secs(scene) > limit:
                groups.append(current)
                current, total = [], 0.0
            current.append(scene)
            total += secs(scene)
        if current:
            groups.append(current)
        notes.append(f"Nach deinen Änderungen war ein Teil zu lang für ein Video – verteilt auf {len(groups)} Teile.")
    else:
        groups = [p["scenes"] for p in skeleton["parts"]]
    n = len(groups)
    skeleton["parts"] = [{
        "intro": title if i == 1 else f"{INTRO_PART[lang].format(n=i)} {title}",
        "scenes": group,
        "outro": final if i == n else OUTRO_NEXT[lang].format(n=i + 1),
        "estimated_seconds": round(sum(secs(s) for s in group) + OVERHEAD_SECONDS),
    } for i, group in enumerate(groups, 1)]
    return notes


def _story(order: dict, folder: Path, progress) -> dict:
    """Story suchen (Auswahl wird gemerkt, damit ein Weiterlauf dieselbe nimmt), Skelett, Video."""
    from .story import pipeline

    if order.get("schritt") == "video":                 # aus dem in der App bearbeiteten Skelett rendern
        progress("Skelett übernehmen", 0.02)
        skeleton = app_skeleton(order["id"])
        pipeline.validate_skeleton(skeleton)            # Eingabefehler -> klare Meldung, keine Wiederholung
        notes = fit_parts(skeleton)                     # Länge, Teilnummern, Titel in allen Teilen
        result = pipeline.render(pipeline.new_folder(skeleton["title"]), skeleton=skeleton,
                                 progress=lambda stage, f: progress(stage, 0.05 + 0.9 * f))
        result.setdefault("warnings", [])[:0] = notes
        return result

    state_file = folder / "story_auswahl.json"
    mood = None if order["stimmung"] == "auto" else order["stimmung"]
    wish = order["wunsch"]
    link = wish if re.search(r"reddit\.com|redd\.it", wish) else ""
    state = json.loads(state_file.read_text("utf-8")) if state_file.exists() else None
    if state is None:
        story, note = None, ""
        if not link:
            progress("Story suchen", 0.02)
            found = pipeline.search(wish, mood, order["sprache"], order["laenge"], limit=3)
            if not found["stories"] and wish:              # Beschreibung zu speziell: beliebte Story der Stimmung
                mood = mood or found["plan"]["mood"]
                found = pipeline.search("", mood, order["sprache"], order["laenge"], limit=3)
                note = "Zur Beschreibung fand sich keine Story – stattdessen eine beliebte Story der Stimmung."
            if not found["stories"]:
                raise RuntimeError(" ".join(found["notes"]) or "Keine passende Story gefunden.")
            story = found["stories"][0]
            mood = mood or found["plan"]["mood"]
        state = {"story": story, "link": link, "mood": mood, "hinweis": note}
        state_file.write_text(json.dumps(state, ensure_ascii=False), "utf-8")
    progress("Skelett und Lektorat", 0.06)
    skeleton, story_folder = pipeline.prepare(story=state["story"], url=state["link"], lang=order["sprache"],
                                              mood=state["mood"], length=order["laenge"], visuals=order["bilder"],
                                              soften=order["entschaerfen"])
    if order.get("schritt") == "skelett":               # erst prüfen und anpassen lassen, dann rendern
        progress("Skelett fertig", 1.0)
        return {"output_dir": str(story_folder), "skelett": skeleton, "videos": {}, "kind": "story",
                "warnings": [w for w in [state.get("hinweis")] if w] + list(skeleton.get("rights", []))}
    result = pipeline.render(story_folder, progress=lambda stage, f: progress(stage, 0.1 + 0.85 * f))
    if state.get("hinweis"):
        result.setdefault("warnings", []).insert(0, state["hinweis"])
    return result


def _clip(order: dict, folder: Path, progress) -> dict:
    """Clip aus einem Link: Quelle laden, Spracherkennung, Hook (ggf. von Claude), Schnitt, Untertitel."""
    from .clip import pipeline as clip_pipeline, texte

    out = folder / "clip"
    out.mkdir(parents=True, exist_ok=True)
    stages = ["Quelle beschaffen", "Spracherkennung", "Höhepunkt suchen", "Gesichter und Sprecher analysieren",
              "Schnittplan", "Untertitel"]

    def stage(text: str) -> None:
        base = text.split(" (")[0]
        progress(text, (stages.index(base) + 1) / 8 if base in stages else 0.9)

    info = clip_pipeline.make_clip(order["quelle"], order["start"], order["ende"], order["sprache"],
                                   float(order["laenge"]), name="clip", fortschritt=stage, ausgabe=out,
                                   arbeit=folder / "_work", herkunft=order["quelle"])
    videos = texte.schreibe(out, info, order, order["quelle"], order["sprache"])
    return {"output_dir": str(out), "videos": videos, "kind": "clip", "warnings": list(info.get("hinweise", []))}


def _transient(exc: Exception) -> bool:
    """Vorübergehende Störung (Netz, Dienst, Prozess) – nicht: falsche Eingaben oder eine gelöschte Story."""
    if hasattr(exc, "wiederholbar"):
        return bool(exc.wiederholbar)
    return isinstance(exc, json.JSONDecodeError) or not isinstance(exc, (OrderError, ValueError))


def run_order(order: dict, folder: Path, via_claude: bool = True, on_progress=None) -> tuple[int, dict | None]:
    """Auftrag ausführen. Rückgabe (Exit-Code, ergebnis.json-Daten oder None bei Übersetzungsbedarf).
    via_claude=False (Web-App/Notbetrieb): keine Claude-Übersetzung, Schreibaufgaben nur über das Sprachmodell."""
    from .story.translate import CLAUDE_FILE_ENV, TranslationNeeded

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "auftrag.json").write_text(json.dumps(order, ensure_ascii=False, indent=1), "utf-8")
    translation = folder / TRANSLATION_FILE
    if via_claude:
        os.environ[CLAUDE_FILE_ENV] = str(translation)    # Story-Übersetzung übernimmt Claude (s. translate.py)
    else:
        os.environ.pop(CLAUDE_FILE_ENV, None)
    os.environ[handoff.DIR_ENV] = str(folder)              # Schreibaufgaben (Thema deuten, erzählen) ebenso
    if order.get("vorlieben"):                            # gelernte Vorlieben gehen in jede Schreibaufgabe
        os.environ[handoff.PREFS_ENV] = json.dumps(order["vorlieben"], ensure_ascii=False)
    else:
        os.environ.pop(handoff.PREFS_ENV, None)
    if order.get("format"):                               # gewähltes Format; sonst je Video ein anderes
        os.environ[FORMAT_ENV] = order["format"]
    else:
        os.environ.pop(FORMAT_ENV, None)
    if order.get("maskottchen") is not None:              # nur ausdrücklich gewählt überschreibt CUDI_MASCOT
        os.environ["CUDI_MASCOT"] = "1" if order["maskottchen"] else "0"
    last = [""]

    def progress(stage: str, fraction: float) -> None:
        if stage != last[0]:
            last[0] = stage
            print(f"  {fraction:4.0%} {stage}", flush=True)
        if on_progress:
            on_progress(stage, fraction)

    for attempt in (1, 2):                                    # eine vorübergehende Störung heilt sich selbst
        try:
            run = {"ranking": _ranking, "story": _story, "clip": _clip}[order["art"]]
            result = run(order, folder, progress)
            data = _summary(order, result)
            break
        except handoff.WritingNeeded as need:
            (folder / "schreiben_offen.txt").write_text(str(need.path), "utf-8")
            return EXIT_WRITE, None
        except TranslationNeeded as need:
            translation.write_text(json.dumps({"quelle": need.source, "ziel": need.target, "texte": need.texts,
                                               "uebersetzt": []}, ensure_ascii=False, indent=1), "utf-8")
            return EXIT_TRANSLATE, None
        except Exception as exc:                              # Fehler kommen als Meldung in die App
            log.exception("Auftrag %s fehlgeschlagen (Versuch %d)", order["id"], attempt)
            if attempt == 1 and _transient(exc):
                print(f"  Störung ({type(exc).__name__}) – neuer Versuch in {RETRY_PAUSE} s", flush=True)
                time.sleep(RETRY_PAUSE)
                from . import net
                net.reset_blocks()
                last[0] = ""
                continue
            data = _summary(order, None, f"{type(exc).__name__}: {exc}"[:1500])
            data["wiederholbar"] = _transient(exc)
            break
    if data["ok"] and order.get("hochladen") and not data.get("schritt"):
        from .upload.cli import upload_order

        data["hochgeladen"] = upload_order(order["hochladen"], data)           # Fehler werden Hinweise, nie ein Abbruch
    (folder / "ergebnis.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    return (0 if data["ok"] else 1), data


def uploads(data: dict) -> list[str]:
    """Hochzuladende Dateien: je Video die App-Fassung (bei langen Videos ihre Stücke) und das Titelbild."""
    return [p for v in data.get("videos", []) for p in (*(v.get("teile") or [v["video"]]), v.get("cover")) if p]


# --------------------------------------------------------------------------- Dokument für die App

def upload_note(entry: dict) -> str:
    """Eine Zeile je Upload für die App: Ziel, Ergebnis, Link bzw. Fehler."""
    name = {"youtube": "YouTube", "tiktok": "TikTok"}.get(entry.get("ziel"), entry.get("ziel", "Upload"))
    if not entry.get("ok"):
        return f"{name}: Hochladen fehlgeschlagen – {entry.get('fehler', 'unbekannter Fehler')}"
    if entry.get("url"):
        return f"{name}: hochgeladen ({entry.get('sichtbarkeit', 'privat')}) – {entry['url']}"
    return f"{name}: als Entwurf in der TikTok-App gesendet" if name == "TikTok" else f"{name}: hochgeladen"


def document(folder: Path, addresses: dict[str, str]) -> dict:
    """Dokument für die Ablage der App-Seite (Sammlung results): Dateipfade durch Upload-Adressen ersetzt."""
    path = folder / "ergebnis.json"
    if path.exists():
        data = json.loads(path.read_text("utf-8"))
    else:                                       # abgebrochen (z. B. Pakete fehlten): Fehlermeldung für die App
        order_file = folder / "auftrag.json"
        order = (json.loads(order_file.read_text("utf-8")) if order_file.exists()
                 else {"id": folder.name.removeprefix("auftrag-"), "art": ""})
        log_tail = _read(folder / "auftrag.log", 200_000).strip().splitlines()[-3:]
        data = _summary(order, None, "Der Auftrag ist abgebrochen, bevor ein Ergebnis entstand."
                        + (" " + " ".join(log_tail)[-600:] if log_tail else ""))
    videos = []
    for v in data.get("videos", []):
        url = addresses.get(v["video"]) or addresses.get(Path(v["video"]).name) or ""
        cover = (addresses.get(v["cover"]) or addresses.get(Path(v["cover"]).name) or "") if v.get("cover") else ""
        parts = [addresses.get(p) or addresses.get(Path(p).name) or "" for p in v.get("teile") or []]
        if parts:
            url = ""                                       # langes Video: nur als Stücke in der Ablage
        videos.append({"key": v["key"], "video_url": url, "teile_urls": parts, "cover_url": cover, "dauer": v.get("dauer"),
                       "mb": v.get("mb"), "datei": Path(v["video"]).name.replace("_app.mp4", ".mp4"),
                       "youtube": v.get("youtube", ""), "tiktok": v.get("tiktok", "")})
    ok = bool(data.get("ok"))
    error = data.get("fehler", "")
    repeatable = bool(data.get("wiederholbar", True))
    if ok and videos and not all(v["video_url"] or (v["teile_urls"] and all(v["teile_urls"])) for v in videos):
        error = "Das Video ist fertig, ließ sich aber nicht in die App laden (Speicher voll?)."
        ok, repeatable = False, False
    doc = {"id": data["id"], "art": data.get("art", ""), "ok": ok, "titel": data.get("titel", ""), "fehler": error,
            "wiederholbar": ok or repeatable,
            "videos": videos, "hinweise": data.get("hinweise", []), "pruefbericht": data.get("pruefbericht", ""),
            "fertig": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if data.get("hochgeladen") is not None:      # Upload-Ergebnis sichtbar machen (Link oder Fehler, geschwärzt)
        doc["hochgeladen"] = data["hochgeladen"]
        doc["hinweise"] = list(doc["hinweise"]) + [upload_note(e) for e in data["hochgeladen"]]
    if data.get("skelett"):                       # Schritt 1 einer Story: Skelett zum Prüfen in der App
        doc["schritt"], doc["skelett"] = "skelett", data["skelett"]
    return doc


# --------------------------------------------------------------------------- Kommandozeile

def main(args) -> int:
    logging.getLogger().handlers.clear()                      # Protokoll in die Datei, Ausgabe knapp halten
    if args.dokument:
        folder = job_folder(args.dokument)
        addresses = json.loads(args.adressen) if args.adressen else {}
        doc = document(folder, addresses)
        target = folder / "dokument.json"
        target.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
        print(f"DOKUMENT: {target}")
        return 0
    if args.weiter:
        folder = job_folder(args.weiter)
        order = json.loads((folder / "auftrag.json").read_text("utf-8"))
    else:
        from .spec import list_presets

        try:
            order = parse_order(json.loads(args.auftrag), {s.id for s in list_presets()})
        except (OrderError, json.JSONDecodeError) as exc:
            print(f"FEHLER: {exc}")
            return 2
        folder = job_folder(order["id"])
    folder.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=str(folder / "auftrag.log"),
                        format="%(asctime)s %(levelname)s %(message)s", force=True)
    print(f"Auftrag {order['id']} ({order['art']}) – Ordner {folder}", flush=True)
    code, data = run_order(order, folder)
    if code == EXIT_WRITE:
        path = (folder / "schreiben_offen.txt").read_text("utf-8").strip()
        print(f"SCHREIBEN: {path}")
        print("Bitte die Aufgabe aus „anleitung“ nur mit „daten“ erledigen, das Ergebnis als „antwort“ in dieselbe "
              f"Datei schreiben und dann ausführen: CUDI_SCHREIBEN=1 bash scripts/cudi_auftrag.sh --weiter {order['id']}")
        return code
    if code == EXIT_TRANSLATE:
        print(f"UEBERSETZEN: {folder / TRANSLATION_FILE}")
        print("Bitte die Liste „texte“ übersetzen, als „uebersetzt“ (gleiche Länge) in dieselbe Datei schreiben "
              f"und dann ausführen: bash scripts/cudi_auftrag.sh --weiter {order['id']}")
        return code
    print(f"DATEIEN: {json.dumps(uploads(data), ensure_ascii=False)}")
    for entry in data.get("hochgeladen") or []:
        print("HOCHGELADEN: " + upload_note(entry))
    print(f"ERGEBNIS: {folder / 'ergebnis.json'}" + ("" if data["ok"] else f"  (Fehler: {data['fehler'][:300]})"))
    return code
