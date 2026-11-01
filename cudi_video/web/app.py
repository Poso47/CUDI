"""Web-Oberfläche (FastAPI). Läuft am PC und in der Cloud; fürs Handy optimiert."""

from __future__ import annotations

import hmac
import json
import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .. import config, llm
from ..spec import VideoSpec, list_presets, preset_raw

log = logging.getLogger(__name__)
app = FastAPI(title="CUDI Video")

_executor = ThreadPoolExecutor(max_workers=1)   # Rendern ist rechenintensiv -> nacheinander
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _check_token(request: Request) -> None:
    if not config.WEB_TOKEN:
        return
    given = request.headers.get("X-Token") or request.query_params.get("token") or ""
    if not hmac.compare_digest(given, config.WEB_TOKEN):
        raise HTTPException(401, "Zugangscode fehlt oder ist falsch")


class JobRequest(BaseModel):
    preset: str | None = None
    yaml_spec: str | None = None
    topic: str | None = None
    langs: list[str] = ["de", "en"]
    count: int = 10
    only_script: bool = False
    strict: bool = False


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
        from ..planner import plan

        log.info("Stichwort-Planer: %s – versuche Sprachmodell", exc)
        return plan(topic, count)


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
    return _jobs[job_id]


def _finished_from_disk() -> list[dict]:
    """Fertige Ergebnisse früherer Läufe (z. B. nach Neustart) anzeigen."""
    items = []
    if not config.OUTPUT_DIR.exists():
        return items
    known = {j.get("folder") for j in _jobs.values()}
    for folder in sorted(config.OUTPUT_DIR.iterdir(), reverse=True)[:30]:
        res = folder / "result.json"
        if folder.name in known or not res.exists():
            continue
        spec = json.loads((folder / "spec.json").read_text("utf-8"))
        items.append({
            "id": "disk-" + folder.name, "folder": folder.name, "status": "fertig", "progress": 1.0,
            "title": spec["title"].get("de") or next(iter(spec["title"].values())),
            "stage": "Fertig", "result": json.loads(res.read_text("utf-8")), "created": folder.name[:15],
        })
    return items


@app.get("/api/jobs")
def jobs(request: Request):
    _check_token(request)
    with _lock:
        live = sorted(_jobs.values(), key=lambda j: j["created"], reverse=True)
    return [*live, *_finished_from_disk()]


@app.get("/review/{folder}", response_class=HTMLResponse)
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
    return _jobs[job_id]


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


@app.get("/files/{folder}/{name}")
def files(folder: str, name: str, request: Request):
    _check_token(request)
    base = config.OUTPUT_DIR.resolve()
    path = (base / folder / name).resolve()
    if base not in path.parents or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)
