"""Web-Oberfläche (FastAPI). Läuft am PC und in der Cloud; fürs Handy optimiert."""

from __future__ import annotations

import hmac
import json
import logging
import os
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .. import config, llm
from ..render.theme import FORMAT_NAMES
from ..spec import VideoSpec, list_presets, preset_raw

log = logging.getLogger(__name__)
app = FastAPI(title="CUDI Video")

_executor = ThreadPoolExecutor(max_workers=1)   # Rendern ist rechenintensiv -> nacheinander
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _token_variants(given: str) -> set[str]:
    """Der Code kann URL-kodiert (Oberfläche), roh (Latin-1) oder als UTF-8-Bytes im Header ankommen."""
    variants = {given, unquote(given)}
    try:
        variants.add(given.encode("latin-1").decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return variants


def _check_token(request: Request) -> None:
    if not config.WEB_TOKEN:
        return
    given = request.headers.get("X-Token") or request.query_params.get("token") or ""
    expected = config.WEB_TOKEN.encode("utf-8")
    # Bytes vergleichen: compare_digest nimmt nur ASCII-Text, Codes wie „München“ würden sonst abstürzen
    if not any(hmac.compare_digest(v.encode("utf-8"), expected) for v in _token_variants(given)):
        raise HTTPException(401, "Zugangscode fehlt oder ist falsch")


class JobRequest(BaseModel):
    preset: str | None = None
    yaml_spec: str | None = None
    topic: str | None = None
    langs: list[str] = ["de", "en"]
    count: int = 10
    only_script: bool = False
    strict: bool = False


def upload_status() -> dict:
    """Welche Upload-Ziele Zugangsdaten haben (nur ja/nein – nie die Werte)."""
    def has(*names: str) -> bool:
        return all(os.environ.get(n) for n in names)

    return {"youtube": has("CUDI_YT_CLIENT_ID", "CUDI_YT_CLIENT_SECRET", "CUDI_YT_REFRESH_TOKEN"),
            "tiktok": has("CUDI_TIKTOK_ACCESS_TOKEN") or has("CUDI_TIKTOK_CLIENT_KEY", "CUDI_TIKTOK_CLIENT_SECRET",
                                                           "CUDI_TIKTOK_REFRESH_TOKEN")}


def _update(job_id: str, **kw) -> None:
    with _lock:
        _jobs[job_id].update(kw)


def _run_job(job_id: str, spec: VideoSpec, only_script: bool, strict: bool = False) -> None:
    from ..pipeline import new_output_dir, run

    try:
        out = new_output_dir(spec)
        _update(job_id, folder=out.name, status="läuft")
        result = run(spec, out=out, render=not only_script, strict=strict,
                     progress=lambda stage, f: _update(job_id, stage=stage, progress=round(f, 3)))
        _update(job_id, status="fertig", progress=1.0, result=result)
    except Exception as exc:
        log.exception("Job %s fehlgeschlagen", job_id)
        _update(job_id, status="fehler", error=f"{exc}", trace=traceback.format_exc()[-2000:])


def plan_topic(topic: str, count: int) -> dict:
    """Stichwort-Planer zuerst (ohne KI, nur geprüfte Themen); Sprachmodell nur als Rückfall."""
    from ..topics import PlanError, plan_from_text

    try:
        return plan_from_text(topic, count)
    except PlanError as exc:
        if not llm.available():
            raise
        from ..planner import plan, plan_with_claude

        log.info("Stichwort-Planer: %s – versuche Sprachmodell", exc)
        planned = plan_with_claude(topic, count)       # dieselbe Anleitung und Prüfung wie bei Claude (Notbetrieb)
        return planned if planned is not None else plan(topic, count)


def _spec_from_request(req: JobRequest) -> VideoSpec:
    if req.topic:
        data = plan_topic(req.topic, req.count)
    elif req.yaml_spec:
        data = yaml.safe_load(req.yaml_spec)
    elif req.preset:
        data = preset_raw(req.preset)
    else:
        raise ValueError("Bitte Vorlage, YAML oder Thema angeben")
    data["count"] = req.count
    data["langs"] = [l for l in req.langs if l in config.SUPPORTED_LANGS] or ["de"]
    return VideoSpec.from_dict(data)


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "index.html").read_text("utf-8")


@app.get("/api/info")
def info(request: Request):
    _check_token(request)
    from ..topics import supported_topics

    return {
        "presets": [{"id": s.id, "title": s.title} for s in list_presets()],
        "llm": llm.available(),
        "topics": supported_topics(),
        "formats": list(FORMAT_NAMES),
        "upload": upload_status(),
    }


@app.get("/api/plan")
def preview_plan(topic: str, request: Request, count: int = 10):
    """Zeigt vorab, wie ein freies Thema verstanden wird (Titel DE/EN)."""
    _check_token(request)
    try:
        data = plan_topic(topic, count)
        spec = VideoSpec.from_dict(data)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"title": spec.title, "count": spec.count}


@app.post("/api/jobs")
def create_job(req: JobRequest, request: Request):
    _check_token(request)
    try:
        spec = _spec_from_request(req)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    job_id = uuid.uuid4().hex[:10]
    with _lock:
        _jobs[job_id] = {
            "id": job_id, "title": spec.title.get("de") or next(iter(spec.title.values())),
            "status": "wartet", "stage": "In der Warteschlange", "progress": 0.0,
            "created": datetime.now().isoformat(timespec="seconds"), "langs": spec.langs,
        }
    _executor.submit(_run_job, job_id, spec, req.only_script, req.strict)
    with _lock:
        return dict(_jobs[job_id])


def _run_order_job(job_id: str, order: dict) -> None:
    """Auftrag wie in der CUDI-App (Ranking, freies Thema, Story, Format, Hochladen) – ohne Claude-Sitzung:
    Schreibaufgaben beantwortet das Sprachmodell (Notbetrieb), sonst gelten die Textbausteine."""
    from .. import job as jobmod

    try:
        _update(job_id, status="läuft", stage="Auftrag läuft")
        folder = jobmod.job_folder(order["id"])
        code, data = jobmod.run_order(
            order, folder, via_claude=False,
            on_progress=lambda stage, f: _update(job_id, stage=stage, progress=round(min(f, 0.99), 3)))
        if data is None:
            raise RuntimeError("Übersetzung nicht möglich – bitte Sprachmodell (CUDI_LLM_*) oder DeepL einrichten "
                               "oder eine Story in Videosprache wählen.")
        if not data["ok"]:
            raise RuntimeError(data["fehler"] or "Auftrag fehlgeschlagen")
        out = Path(data["ordner"])
        result = json.loads((out / "result.json").read_text("utf-8"))
        rel = out.resolve().relative_to(config.OUTPUT_DIR.resolve())
        result["warnings"] = data["hinweise"]
        if data.get("hochgeladen"):
            result["hochgeladen"] = data["hochgeladen"]
        _update(job_id, status="fertig", progress=1.0, result=result, folder=rel.as_posix())
    except Exception as exc:
        log.exception("Auftrag %s fehlgeschlagen", job_id)
        from ..upload import redact
        _update(job_id, status="fehler", error=redact(f"{exc}")[:1500], trace=redact(traceback.format_exc()[-2000:]))


@app.post("/api/auftrag")
async def create_order(request: Request):
    """Gleiches Auftragsformat wie die CUDI-App-Seite: {art: ranking|story, vorlage|thema, plaetze, sprachen, format,
    wunsch, stimmung, hochladen: {ziel, sichtbarkeit}, …}."""
    _check_token(request)
    from .. import job as jobmod

    try:
        raw = await request.json()
        if not isinstance(raw, dict) or raw.get("art") not in ("ranking", "story"):
            raise jobmod.OrderError("Art: „ranking“ oder „story“.")
        order = jobmod.parse_order({**raw, "id": uuid.uuid4().hex[:10]}, {s.id for s in list_presets()})
    except (jobmod.OrderError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    title = order.get("thema") or order.get("vorlage") or order.get("wunsch") or f"Story ({order.get('stimmung')})"
    with _lock:
        _jobs[order["id"]] = {
            "id": order["id"], "title": ("Story: " if order["art"] == "story" else "") + title[:80],
            "status": "wartet", "stage": "In der Warteschlange", "progress": 0.0,
            "created": datetime.now().isoformat(timespec="seconds"), "langs": order.get("sprachen") or [order.get("sprache")],
        }
    _executor.submit(_run_order_job, order["id"], order)
    with _lock:
        return dict(_jobs[order["id"]])


def _finished_from_disk(known: set[str]) -> list[dict]:
    """Fertige Ergebnisse früherer Läufe (z. B. nach Neustart) anzeigen. `known`: Ordner laufender Aufträge."""
    items = []
    if not config.OUTPUT_DIR.exists():
        return items
    folders = [f for f in config.OUTPUT_DIR.iterdir() if f.is_dir() and not f.name.startswith("_")]
    for folder in sorted(folders, reverse=True)[:30]:
        res = folder / "result.json"
        if folder.name in known or not res.exists():
            continue
        try:
            spec = json.loads((folder / "spec.json").read_text("utf-8"))
            title = spec["title"].get("de") or next(iter(spec["title"].values()))
            result = json.loads(res.read_text("utf-8"))
        except (OSError, ValueError, KeyError, AttributeError, StopIteration) as exc:
            log.warning("Ordner %s übersprungen (unvollständig): %s", folder.name, exc)
            continue
        items.append({
            "id": "disk-" + folder.name, "folder": folder.name, "status": "fertig", "progress": 1.0,
            "title": title, "stage": "Fertig", "result": result, "created": folder.name[:15],
        })
    return items


@app.get("/api/jobs")
def jobs(request: Request):
    _check_token(request)
    with _lock:   # Kopien unter der Sperre: der Auftrags-Thread ändert die Einträge gleichzeitig
        live = [dict(j) for j in sorted(_jobs.values(), key=lambda j: j["created"], reverse=True)]
    known = {j.get("folder") for j in live}
    return [*live, *_finished_from_disk(known)]


@app.get("/review/{folder:path}", response_class=HTMLResponse)
def review(folder: str, request: Request):
    """Prüfbericht als lesbare Seite (auch auf dem Handy)."""
    _check_token(request)
    from .markdown import page

    base = config.OUTPUT_DIR.resolve()
    path = (base / folder / "review.md").resolve()
    if base not in path.parents or not path.is_file():
        raise HTTPException(404)
    return page(path.read_text("utf-8"))


# --------------------------------------------------------------------------- Reddit-Storys

class StorySearch(BaseModel):
    description: str = ""
    mood: str | None = None
    lang: str = "de"
    length: str = "3min"
    seed: int | None = None


class StoryPrepare(BaseModel):
    story: dict | None = None
    url: str = ""
    title: str = ""
    text: str = ""
    lang: str = "de"
    mood: str | None = None
    length: str = "3min"
    visuals: str = "videos"
    soften: bool = True


class StoryRender(BaseModel):
    folder: str
    skeleton: dict | None = None


class StoryAuto(BaseModel):
    description: str = ""
    mood: str | None = None
    url: str = ""
    lang: str = "de"
    length: str = "3min"
    visuals: str = "videos"
    soften: bool = True


def _story_folder(name: str) -> Path:
    base = config.OUTPUT_DIR.resolve()
    folder = (base / name).resolve()
    if folder.parent != base or not (folder / "story.json").exists():
        raise HTTPException(404, "Story-Ordner nicht gefunden")
    return folder


def _start_story_job(title: str, lang: str, fn, folder: str | None = None, **kw) -> dict:
    job_id = uuid.uuid4().hex[:10]
    with _lock:
        _jobs[job_id] = {"id": job_id, "title": title, "status": "wartet", "stage": "In der Warteschlange",
                         "progress": 0.0, "created": datetime.now().isoformat(timespec="seconds"),
                         "langs": [lang], "folder": folder, "kind": "story"}

    def run() -> None:
        try:
            _update(job_id, status="läuft")
            result = fn(progress=lambda stage, f: _update(job_id, stage=stage, progress=round(f, 3)), **kw)
            _update(job_id, status="fertig", progress=1.0, result=result, folder=Path(result["output_dir"]).name)
        except Exception as exc:
            log.exception("Story-Job %s fehlgeschlagen", job_id)
            _update(job_id, status="fehler", error=f"{exc}", trace=traceback.format_exc()[-2000:])

    _executor.submit(run)
    with _lock:
        return dict(_jobs[job_id])


@app.get("/api/story/info")
def story_info(request: Request):
    _check_token(request)
    from ..story.moods import MOODS
    from ..story.pipeline import lengths

    return {
        "moods": [{"id": k, "label": m["label"], "icon": m["icon"]} for k, m in MOODS.items()],
        "lengths": lengths(),
        "visuals": {"videos": "Videos bevorzugt", "images": "KI-Bilder", "gameplay": "Eigene Clips (z. B. Gameplay)"},
        "stock_videos": bool(config.PEXELS_API_KEY or config.PIXABAY_API_KEY),
        "reddit_login": bool(config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET),
        "translation": "Sprachmodell" if llm.available() else "DeepL" if config.DEEPL_API_KEY else "MyMemory (begrenzt)",
        "llm": llm.available(),
    }


@app.post("/api/story/search")
def story_search(req: StorySearch, request: Request):
    _check_token(request)
    from ..story import pipeline

    try:
        return pipeline.search(req.description, req.mood, req.lang, req.length, seed=req.seed)
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/story/prepare")
def story_prepare(req: StoryPrepare, request: Request):
    _check_token(request)
    from ..story import pipeline

    try:
        skeleton, folder = pipeline.prepare(story=req.story, url=req.url, text=req.text, title=req.title,
                                            lang=req.lang, mood=req.mood, length=req.length, visuals=req.visuals,
                                            soften=req.soften)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"folder": folder.name, "skeleton": skeleton}


@app.post("/api/story/render")
def story_render(req: StoryRender, request: Request):
    _check_token(request)
    from ..story import pipeline

    folder = _story_folder(req.folder)
    skeleton = req.skeleton or pipeline.load_skeleton(folder)
    try:
        pipeline.validate_skeleton(skeleton)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _start_story_job(skeleton["title"], skeleton["lang"], pipeline.render, folder=folder.name,
                            folder_path=folder, skeleton=skeleton)


@app.post("/api/story/auto")
def story_auto(req: StoryAuto, request: Request):
    _check_token(request)
    from ..story import pipeline
    from ..story.moods import MOODS

    title = req.description or req.url or f"{MOODS.get(req.mood or 'creepy', MOODS['creepy'])['label']['de']}e Story"
    return _start_story_job(f"Autopilot: {title[:60]}", req.lang, pipeline.autopilot, description=req.description,
                            mood=req.mood, url=req.url, lang=req.lang, length=req.length, visuals=req.visuals,
                            soften=req.soften)


@app.get("/api/check")
def system_check(request: Request):
    """Selbsttest über die Oberfläche (z. B. in der Cloud)."""
    _check_token(request)
    from ..check import run_checks

    rows, ready = run_checks()
    return {"ready": ready, "rows": rows}


@app.get("/files/{folder:path}/{name}")
def files(folder: str, name: str, request: Request):
    _check_token(request)
    base = config.OUTPUT_DIR.resolve()
    path = (base / folder / name).resolve()
    if base not in path.parents or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)
