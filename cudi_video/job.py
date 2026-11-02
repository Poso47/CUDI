"""Auftrag aus der CUDI-App in Claude – ein Befehl von der Eingabe bis zur fertigen App-Fassung.

Die CUDI-App-Seite startet für jeden Auftrag eine Claude-Sitzung in der Cloud. Diese führt aus:

  bash scripts/cudi_auftrag.sh '<json>'                       rendern (Ordner video_output/auftrag-<id>)
  bash scripts/cudi_auftrag.sh --weiter <id>                  nach Claudes Übersetzung weiterrendern
  python -m cudi_video auftrag --dokument <id> --adressen '{"<datei>": "<url>"}'
                                                              Dokument für die Ablage der App-Seite

Zeilen, auf die die Sitzung achtet:
  UEBERSETZEN: <datei>   Story in anderer Sprache und kein Übersetzungsdienst: Claude übersetzt die Texte
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

from . import config

log = logging.getLogger(__name__)

APP_BUDGET = 19 * 1024 * 1024          # Ablage der App-Seite: 20 MiB je Datei, etwas Luft
AUDIO_BPS = 96_000
MAX_REVIEW = 40_000
MOODS = ("auto", "creepy", "suspense", "funny", "drama", "revenge", "wholesome")
TRANSLATION_FILE = "uebersetzen.json"
EXIT_TRANSLATE = 3
RETRY_PAUSE = 60                       # Sekunden Pause vor dem zweiten Versuch nach einer Störung


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


def parse_order(raw: dict, presets: set[str]) -> dict:
    """Auftrag der App-Seite prüfen: nur bekannte Felder und erlaubte Werte."""
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
        try:
            count = int(raw.get("plaetze", 10))
        except (TypeError, ValueError):
            raise OrderError("Plätze: bitte eine Zahl von 3 bis 20.") from None
        if not 3 <= count <= 20:
            raise OrderError("Plätze: bitte eine Zahl von 3 bis 20.")
        return {"id": job_id, "art": "ranking", "thema": topic, "vorlage": preset, "sprachen": langs,
                "plaetze": count, "streng": _flag(raw.get("streng"), False),
                "nur_skript": _flag(raw.get("nur_skript"), False)}
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
        if lang not in ("de", "en") or length not in ("kurz", "3min", "teile") or visuals not in ("videos", "images", "gameplay"):
            raise OrderError("Sprache, Länge oder Bilder ungültig.")
        return {"id": job_id, "art": "story", "wunsch": wish, "stimmung": mood, "sprache": lang,
                "laenge": length, "bilder": visuals, "entschaerfen": _flag(raw.get("entschaerfen"), True)}
    raise OrderError("Unbekannte Art – „ranking“ oder „story“.")


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
    spec = out / "spec.json"
    if spec.exists():
        titles = json.loads(spec.read_text("utf-8")).get("title", {})
        data["titel"] = titles.get("de") or next(iter(titles.values()), "")
    for key, files in result.get("videos", {}).items():
        video = out / files["video"]
        app = app_version(video, video.with_name(video.stem + "_app.mp4"))
        cover = out / files["cover"] if files.get("cover") and (out / files["cover"]).exists() else None
        data["videos"].append({
            "key": key, "video": str(app), "cover": str(cover) if cover else None,
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

    spec = _load(order["thema"] or order["vorlage"], order["plaetze"])
    out = folder / "video"
    out.mkdir(parents=True, exist_ok=True)
    return run(spec, out=out, langs=order["sprachen"], render=not order["nur_skript"], strict=order["streng"],
               progress=progress)


def _story(order: dict, folder: Path, progress) -> dict:
    """Story suchen (Auswahl wird gemerkt, damit ein Weiterlauf dieselbe nimmt), Skelett, Video."""
    from .story import pipeline

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
    _, story_folder = pipeline.prepare(story=state["story"], url=state["link"], lang=order["sprache"],
                                       mood=state["mood"], length=order["laenge"], visuals=order["bilder"],
                                       soften=order["entschaerfen"])
    result = pipeline.render(story_folder, progress=lambda stage, f: progress(stage, 0.1 + 0.85 * f))
    if state.get("hinweis"):
        result.setdefault("warnings", []).insert(0, state["hinweis"])
    return result


def _transient(exc: Exception) -> bool:
    """Vorübergehende Störung (Netz, Dienst, Prozess) – nicht: falsche Eingaben oder eine gelöschte Story."""
    return isinstance(exc, json.JSONDecodeError) or not isinstance(exc, (OrderError, ValueError))


def run_order(order: dict, folder: Path) -> tuple[int, dict | None]:
    """Auftrag ausführen. Rückgabe (Exit-Code, ergebnis.json-Daten oder None bei Übersetzungsbedarf)."""
    from .story.translate import CLAUDE_FILE_ENV, TranslationNeeded

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "auftrag.json").write_text(json.dumps(order, ensure_ascii=False, indent=1), "utf-8")
    translation = folder / TRANSLATION_FILE
    os.environ[CLAUDE_FILE_ENV] = str(translation)        # Story-Übersetzung übernimmt Claude (s. translate.py)
    last = [""]

    def progress(stage: str, fraction: float) -> None:
        if stage != last[0]:
            last[0] = stage
            print(f"  {fraction:4.0%} {stage}", flush=True)

    for attempt in (1, 2):                                    # eine vorübergehende Störung heilt sich selbst
        try:
            result = _ranking(order, folder, progress) if order["art"] == "ranking" else _story(order, folder, progress)
            data = _summary(order, result)
            break
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
            break
    (folder / "ergebnis.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    return (0 if data["ok"] else 1), data


def uploads(data: dict) -> list[str]:
    return [p for v in data.get("videos", []) for p in (v["video"], v.get("cover")) if p]


# --------------------------------------------------------------------------- Dokument für die App

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
        videos.append({"key": v["key"], "video_url": url, "cover_url": cover, "dauer": v.get("dauer"),
                       "mb": v.get("mb"), "datei": Path(v["video"]).name.replace("_app.mp4", ".mp4"),
                       "youtube": v.get("youtube", ""), "tiktok": v.get("tiktok", "")})
    ok = bool(data.get("ok"))
    error = data.get("fehler", "")
    if ok and videos and not all(v["video_url"] for v in videos):
        error = "Das Video ist fertig, ließ sich aber nicht in die App laden (Speicher voll?)."
        ok = False
    return {"id": data["id"], "art": data.get("art", ""), "ok": ok, "titel": data.get("titel", ""), "fehler": error,
            "videos": videos, "hinweise": data.get("hinweise", []), "pruefbericht": data.get("pruefbericht", ""),
            "fertig": datetime.now(timezone.utc).isoformat(timespec="seconds")}


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
    if code == EXIT_TRANSLATE:
        print(f"UEBERSETZEN: {folder / TRANSLATION_FILE}")
        print("Bitte die Liste „texte“ übersetzen, als „uebersetzt“ (gleiche Länge) in dieselbe Datei schreiben "
              f"und dann ausführen: bash scripts/cudi_auftrag.sh --weiter {order['id']}")
        return code
    print(f"DATEIEN: {json.dumps(uploads(data), ensure_ascii=False)}")
    print(f"ERGEBNIS: {folder / 'ergebnis.json'}" + ("" if data["ok"] else f"  (Fehler: {data['fehler'][:300]})"))
    return code
