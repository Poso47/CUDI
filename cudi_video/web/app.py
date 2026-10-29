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


def _spec_from_request(req: JobRequest) -> VideoSpec:
    if req.topic:
        from ..planner import plan

        data = plan(req.topic, req.count)
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
    return {
        "presets": [{"id": s.id, "title": s.title} for s in list_presets()],
        "llm": llm.available(),
    }


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


@app.get("/files/{folder}/{name}")
def files(folder: str, name: str, request: Request):
    _check_token(request)
    base = config.OUTPUT_DIR.resolve()
    path = (base / folder / name).resolve()
    if base not in path.parents or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)
