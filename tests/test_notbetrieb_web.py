"""Web-App als Notbetrieb: Auftragsweg (Ranking, freies Thema, Story, Format, Hochladen) ohne Claude-Sitzung."""

import json

from fastapi.testclient import TestClient

from cudi_video import config, job as jobmod
from cudi_video.web import app as webapp


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WEB_TOKEN", "")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(webapp._executor, "submit", lambda fn, *a, **k: None)     # nicht wirklich rendern
    return TestClient(webapp.app)


def test_info_lists_formats_and_upload_state(monkeypatch, tmp_path):
    for name in ("CUDI_YT_CLIENT_SECRET", "CUDI_YT_REFRESH_TOKEN", "CUDI_TIKTOK_ACCESS_TOKEN",
                 "CUDI_TIKTOK_CLIENT_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CUDI_YT_CLIENT_ID", "geheim-id")
    client = _client(monkeypatch, tmp_path)
    response = client.get("/api/info")
    info = response.json()
    assert "karte" in info["formats"] and "manuskript" in info["formats"]
    assert info["upload"] == {"youtube": False, "tiktok": False}
    assert "geheim" not in response.text


def test_order_validates_and_queues(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.post("/api/auftrag", json={"art": "clip"}).status_code == 400
    assert client.post("/api/auftrag", json={"art": "ranking", "thema": "x", "format": "gibtsnicht"}).status_code == 400
    ok = client.post("/api/auftrag", json={"art": "ranking", "thema": "die höchsten Wasserfälle", "plaetze": 5,
                                           "sprachen": ["de"], "format": "karte",
                                           "hochladen": {"ziel": "youtube", "sichtbarkeit": "privat"}})
    assert ok.status_code == 200 and ok.json()["status"] == "wartet"
    story = client.post("/api/auftrag", json={"art": "story", "wunsch": "gruselige Story", "stimmung": "creepy"})
    assert story.status_code == 200 and story.json()["title"].startswith("Story:")


def test_order_job_result_and_nested_files(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    out = tmp_path / "auftrag-abc12345" / "video"
    out.mkdir(parents=True)
    (out / "result.json").write_text(json.dumps({"output_dir": str(out), "warnings": [], "videos": {}}), "utf-8")
    (out / "v.mp4").write_bytes(b"x")
    seen = {}

    def fake_run(order, folder, via_claude=True, on_progress=None):
        seen["via_claude"] = via_claude
        on_progress("Rendern", 0.5)
        return 0, {"ok": True, "ordner": str(out), "hinweise": ["Hinweis"], "fehler": "",
                   "hochgeladen": [{"ziel": "youtube", "sprache": "de", "ok": True}]}

    monkeypatch.setattr(jobmod, "run_order", fake_run)
    webapp._jobs["abc12345"] = {"id": "abc12345", "title": "t", "status": "wartet", "created": "x"}
    webapp._run_order_job("abc12345", {"id": "abc12345"})
    job = webapp._jobs["abc12345"]
    assert seen["via_claude"] is False and job["status"] == "fertig" and job["folder"] == "auftrag-abc12345/video"
    assert job["result"]["hochgeladen"][0]["ok"] and job["result"]["warnings"] == ["Hinweis"]
    assert client.get("/files/auftrag-abc12345/video/v.mp4").content == b"x"
    assert client.get("/files/auftrag-abc12345/video/nichtda.mp4").status_code == 404


def test_order_error_is_reported_without_secrets(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    monkeypatch.setenv("CUDI_YT_REFRESH_TOKEN", "supergeheimertoken")

    def boom(order, folder, **kw):
        raise RuntimeError("Fehler mit supergeheimertoken")

    monkeypatch.setattr(jobmod, "run_order", boom)
    webapp._jobs["fehl1234"] = {"id": "fehl1234", "title": "t", "status": "wartet", "created": "x"}
    webapp._run_order_job("fehl1234", {"id": "fehl1234"})
    job = webapp._jobs["fehl1234"]
    assert job["status"] == "fehler" and "supergeheimertoken" not in json.dumps(job)
