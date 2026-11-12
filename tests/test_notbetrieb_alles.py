"""Notbetrieb komplett: Erklärvideo, Bearbeiten/Hochladen per Issue (Verweis auf früheres Ergebnis), Wiederholung bei
Modellausfall – ohne Netz, ohne echtes Sprachmodell."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from cudi_video import handoff, job
from cudi_video.erklaer import schreiben
from cudi_video.upload import cli as upload_cli

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("notbetrieb_script", SCRIPTS / "notbetrieb.py")
nb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nb)
import auftrag  # noqa: E402

PRESETS = {"groesste-seen"}
ARTICLE = ("Der Goldene Schnitt ist ein Verhältnis zweier Größen. Teilt man eine Strecke so, dass sich das Ganze zum größeren Teil "
           "verhält wie der größere zum kleineren, entsteht dieses Verhältnis. Der Wert beträgt etwa 1,618. "
           "Schon Euklid beschrieb die Teilung in stetiger Proportion in seinen Elementen. " * 4)
BELEG1 = "Teilt man eine Strecke so, dass sich das Ganze zum größeren Teil verhält wie der größere zum kleineren, entsteht dieses Verhältnis."
BELEG2 = "Der Wert beträgt etwa 1,618."
BELEG3 = "Schon Euklid beschrieb die Teilung in stetiger Proportion in seinen Elementen."


def _scene(text, beleg, **extra):
    return {"text": text, "beleg": beleg, "betont": [], "visual": {"typ": "beschriftung", "label": "Verhältnis"}, **extra}


def _good_scenes():
    return [_scene("Teilt man eine Strecke im richtigen Verhältnis, entsteht eine besondere Beziehung zwischen Teil und Ganzem.", BELEG1),
            _scene("Der Wert beträgt etwa 1,618 und zeigt, wie das Ganze zum größeren Teil steht.", BELEG2),
            _scene("Schon Euklid beschrieb diese Teilung in stetiger Proportion in seinen Elementen und machte sie bekannt.", BELEG3),
            _scene("Das Ganze verhält sich zum größeren Teil wie der größere Teil zum kleineren Teil dieser Strecke.", BELEG1)]


# --------------------------------------------------------------------------- Erklärvideo

def test_erklaer_order_parsed_and_allowed_in_notbetrieb():
    o = nb.prepare_order({"id": "gh0001", "art": "erklaer", "thema": "Goldener Schnitt"}, PRESETS)
    assert o["art"] == "erklaer" and o["sprache"] == "de" and o["maskottchen"] is False
    for bad in ({"thema": "ab"}, {"thema": "Goldener Schnitt", "sprache": "fr"}):
        with pytest.raises(job.OrderError):
            job.parse_order({"id": "gh0002", "art": "erklaer", **bad}, PRESETS)
    assert auftrag.build_json_order({"art": "erklaer", "thema": "Goldener Schnitt"}, 5, PRESETS)["id"] == "gh0005"


def test_write_script_accepts_only_checked_scenes(monkeypatch):
    monkeypatch.setattr(handoff, "active", lambda: True)
    bad = [_scene("Der Goldene Schnitt ist ungefähr 1,7 und damit unglaublich schön für alle Menschen auf der Welt.", BELEG2),
           _scene("Diese Teilung erklärte schon früh Einstein in vielen Büchern und Vorträgen für ein großes Publikum.", BELEG3),
           _scene("Der Beleg steht nirgends im Artikel, deshalb muss die ganze Szene wieder verworfen werden, ehrlich.", "Das steht nicht im Artikel.")]
    answers = {"erklaer": {"titel": "Der Goldene Schnitt", "szenen": _good_scenes() + bad}}
    monkeypatch.setattr(handoff, "request", lambda task, instr, data: answers.get(task))
    script, report = schreiben.write_script("Goldener Schnitt", "de", article=("Goldener Schnitt", ARTICLE, "https://de.wikipedia.org/wiki/Goldener_Schnitt"))
    assert len(script["szenen"]) == 4 and script["titel"] == "Der Goldene Schnitt"
    assert all(p["beleg"] in ARTICLE for p in report["beleg"])
    assert len([h for h in report["hinweise"] if "verworfen" in h]) == 3
    assert any("1,7" in h or "Zahlen ohne Beleg" in h for h in report["hinweise"])


def test_write_script_correction_round_then_honest_abort(monkeypatch):
    monkeypatch.setattr(handoff, "active", lambda: True)
    art = ("Goldener Schnitt", ARTICLE, "u")
    calls = []

    def req(task, instr, data):
        calls.append(task)
        if task == "erklaer":
            return {"titel": "T", "szenen": _good_scenes()[:2] + [_scene("Zu kurz.", BELEG2)]}
        return {"szenen": _good_scenes()[2:]}

    monkeypatch.setattr(handoff, "request", req)
    script, _ = schreiben.write_script("Goldener Schnitt", "de", article=art)
    assert calls == ["erklaer", "erklaer_korrektur"] and len(script["szenen"]) == 4
    monkeypatch.setattr(handoff, "request", lambda *a: {"titel": "T", "szenen": _good_scenes()[:2]})
    with pytest.raises(ValueError, match="Erfunden wird nichts"):
        schreiben.write_script("Goldener Schnitt", "de", article=art)
    monkeypatch.setattr(handoff, "request", lambda *a: None)
    with pytest.raises(handoff.ModelUnavailable):
        schreiben.write_script("Goldener Schnitt", "de", article=art)
    monkeypatch.setattr(handoff, "active", lambda: False)
    with pytest.raises(handoff.ModelUnavailable, match="Sprachmodell"):
        schreiben.write_script("Goldener Schnitt", "de", article=art)


def test_clean_visual_replaces_unbacked_numbers_and_quotes():
    scene = _scene("x", BELEG2, visual={"typ": "zahl_zaehler", "wert": "1,6180339887...", "label": "Der Wert"})
    assert schreiben.clean_visual(scene, ARTICLE, "de")[0]["typ"] == "beschriftung"          # 1,6180339887 steht nicht im Beleg
    ok = _scene("x", BELEG2, visual={"typ": "zahl_zaehler", "wert": "1,618", "label": "Der Wert"})
    assert schreiben.clean_visual(ok, ARTICLE, "de") == (ok["visual"], "")
    quote = _scene("x", BELEG3, visual={"typ": "zitatkarte", "zitat": "Das hat Euklid nie gesagt"})
    assert schreiben.clean_visual(quote, ARTICLE, "de")[0]["typ"] == "beschriftung"


def test_erklaer_job_writes_report_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(schreiben, "find_article", lambda t, l: ("Goldener Schnitt", ARTICLE, "https://de.wikipedia.org/wiki/Goldener_Schnitt"))
    monkeypatch.setattr(handoff, "request", lambda task, i, d: {"titel": "Der Goldene Schnitt", "szenen": _good_scenes()})

    def fake_render(script, out_dir=None, progress=None, musik=True):
        (out_dir / f"{script['id']}.mp4").write_bytes(b"x" * 50)
        (out_dir / f"{script['id']}_cover.jpg").write_bytes(b"j")
        progress(1.0)
        return {"video": f"{script['id']}.mp4", "cover": f"{script['id']}_cover.jpg", "duration": 60.0, "qa": None}

    monkeypatch.setattr("cudi_video.erklaer.render_erklaerung", fake_render)
    monkeypatch.setattr(job, "app_version", lambda src, dst, budget=0: src)
    order = nb.prepare_order({"id": "gh0007", "art": "erklaer", "thema": "Goldener Schnitt"}, PRESETS)
    code, data = job.run_order(order, job.job_folder("gh0007"), via_claude=False)
    assert code == 0 and data["ok"], data["fehler"]
    assert data["titel"] == "Der Goldene Schnitt" and data["videos"][0]["key"] == "de"
    assert "Beleg:" in data["pruefbericht"] and "wikipedia" in data["pruefbericht"].lower()
    assert "Goldene" in data["videos"][0]["youtube"]
    text = nb.comment_text(data, "https://run")
    assert "Fertig: Der Goldene Schnitt" in text


# --------------------------------------------------------------------------- Bearbeiten / Hochladen per Issue

def _earlier_result(tmp_path, with_video=True, art="ranking", rid="gh0012"):
    """Ordner eines früheren Notbetrieb-Laufs, wie ihn das Artefakt liefert."""
    src = tmp_path / "artefakt" / f"auftrag-{rid}"
    (src / "video" / "v").mkdir(parents=True)
    if with_video:
        (src / "video" / "v" / "v_de.mp4").write_bytes(b"VIDEO")
    sk = {"version": 1, "lang": "de", "mood": "creepy", "title": "Der Beobachter", "voice": {"name": "x"}, "visuals": "images",
          "post": {"id": "abc", "text": "Er stand da."}, "notes": [], "rights": [],
          "parts": [{"intro": "Der Beobachter", "outro": "Folge für mehr.", "estimated_seconds": 40,
                     "scenes": [{"text": "Es war dunkel.", "source": "", "query": "forest", "prompt": "forest"},
                                {"text": "Dann kam er näher.", "source": "", "query": "man", "prompt": "man"}]}]}
    (src / "bearbeitung.json").write_text(json.dumps({"art": "story", "id": rid, "skelett": sk, "stil": {"maskottchen": True},
                                                      "optionen": {}}), "utf-8")
    (src / "ergebnis.json").write_text(json.dumps({
        "id": rid, "art": art, "ok": True, "titel": "Seen", "hinweise": [],
        "videos": [{"key": "de", "video": str(Path("/weg") / "v_de_app.mp4"), "youtube": "Titel\n\nText\n#shorts #seen",
                    "tiktok": "Kurztext"}]}), "utf-8")
    return src


def _fake_gh(artifact_root, name="cudi-notbetrieb-12-3", expired=False):
    def run(*args, check=True):
        if args[0] == "api":
            body = {"artifacts": [{"name": name, "expired": expired, "created_at": "2026-01-01", "workflow_run": {"id": 99}},
                                  {"name": "uploads-neu-12-3", "expired": False, "workflow_run": {"id": 99}}]}
            return SimpleNamespace(returncode=0, stdout=json.dumps(body), stderr="")
        target = Path(args[args.index("-D") + 1])
        shutil.copytree(artifact_root, target, dirs_exist_ok=True)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


def test_pick_artifact_takes_newest_unexpired_with_matching_name():
    listing = [{"name": "cudi-notbetrieb-12-3", "created_at": "2026-01-01"}, {"name": "cudi-notbetrieb-12-9", "created_at": "2026-02-01"},
               {"name": "cudi-notbetrieb-12-11", "created_at": "2026-03-01", "expired": True}, {"name": "cudi-notbetrieb-120-1", "created_at": "2026-04-01"}]
    assert nb.pick_artifact(listing, 12)["name"] == "cudi-notbetrieb-12-9"
    assert nb.pick_artifact(listing, 12, 3)["name"] == "cudi-notbetrieb-12-3"
    assert nb.pick_artifact(listing, 7) is None


def test_edit_order_roundtrip_via_issue_and_artifact(tmp_path, monkeypatch):
    from cudi_video.story import pipeline

    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    _earlier_result(tmp_path)
    raw = {"art": "story", "stimmung": "creepy", "schritt": "bearbeiten", "bezug": {"issue": 12},
           "aenderungen": {"skelett": None, "maskottchen": False, "wunsch": ""}}
    body = "cudi-auftrag\n```json\n" + json.dumps(raw) + "\n```"
    order = auftrag.build_json_order(auftrag.extract_json(body), 20, PRESETS)
    assert order["id"] == "gh0020" and order["bezug"] == {"id": "gh0012"} and order["schritt"] == "bearbeiten"
    assert "bearbeiten (früheres Ergebnis gh0012)" in auftrag.summary_line("notbetrieb.yml", {"auftrag": json.dumps(order)})
    nb.restore_earlier(order, "o/r", runner=_fake_gh(tmp_path / "artefakt"))
    seen = {}

    def render(folder, skeleton=None, progress=None):
        seen["texts"] = [s["text"] for p in skeleton["parts"] for s in p["scenes"]]
        return {"output_dir": str(folder), "videos": {}, "warnings": []}

    monkeypatch.setattr(pipeline, "render", render)
    monkeypatch.setattr(pipeline, "new_folder", lambda title: tmp_path / "story")
    (tmp_path / "story").mkdir()
    code, data = job.run_order(order, job.job_folder("gh0020"), via_claude=False)
    assert code == 0 and seen["texts"] == ["Es war dunkel.", "Dann kam er näher."]
    assert data["art_schritt"] == "bearbeiten" and job.os.environ["CUDI_MASCOT"] == "0"


def test_steps_need_reference_and_allowed_art():
    with pytest.raises(job.OrderError, match="Verweis"):
        nb.prepare_order({"id": "gh0003", "art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten"}, PRESETS)
    with pytest.raises(job.OrderError, match="Schritt"):
        nb.prepare_order({"id": "gh0003", "art": "reportage", "schritt": "bearbeiten", "bezug": {"issue": 4}}, PRESETS)
    with pytest.raises(job.OrderError):
        nb.prepare_order({"id": "gh0003", "art": "ranking", "schritt": "hochladen", "bezug": {"issue": "x"},
                          "hochladen": {"ziel": "youtube"}}, PRESETS)
    up = nb.prepare_order({"id": "gh0003", "art": "clip", "schritt": "hochladen", "bezug": "gh0004",
                           "hochladen": {"ziel": "alle"}}, PRESETS)
    assert up["bezug"] == {"id": "gh0004"} and up["hochladen"]["freigabe"] is False


def test_restore_reports_expired_artifact_honestly(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    order = nb.prepare_order({"id": "gh0003", "art": "ranking", "schritt": "hochladen", "bezug": {"issue": 12},
                              "hochladen": {"ziel": "youtube"}}, PRESETS)
    with pytest.raises(RuntimeError, match="14 Tage"):
        nb.restore_earlier(order, "o/r", runner=_fake_gh(tmp_path, expired=True))
    with pytest.raises(RuntimeError, match="nicht mehr da"):
        job._earlier_document(order)


def test_upload_roundtrip_uses_video_from_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    _earlier_result(tmp_path)
    order = nb.prepare_order({"id": "gh0021", "art": "ranking", "schritt": "hochladen", "bezug": {"issue": 12},
                              "hochladen": {"ziel": "beide", "sichtbarkeit": "privat"}}, PRESETS)
    nb.restore_earlier(order, "o/r", runner=_fake_gh(tmp_path / "artefakt"))
    sent = []

    def run_one(material, target, visibility, mode="inbox"):
        sent.append((material.video.read_bytes(), material.title, material.tags, material.caption, target))
        return {"url": "https://youtube.com/watch?v=1"} if target == "youtube" else {"publish_id": "p"}

    monkeypatch.setattr(upload_cli, "run_one", run_one)
    code, data = job.run_order(order, job.job_folder("gh0021"), via_claude=False)
    assert code == 0 and data["ok"] and data["art_schritt"] == "hochladen"
    assert sent[0] == (b"VIDEO", "Titel", ["shorts", "seen"], "Kurztext", "youtube") and [s[4] for s in sent] == ["youtube", "tiktok"]
    assert "Hochgeladen" in nb.comment_text(data, "https://run") and "youtube.com/watch?v=1" in nb.comment_text(data, "https://run")


def test_upload_without_credentials_names_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    for name in ("CUDI_YT_CLIENT_ID", "CUDI_YT_CLIENT_SECRET", "CUDI_YT_REFRESH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    _earlier_result(tmp_path)
    order = nb.prepare_order({"id": "gh0022", "art": "ranking", "schritt": "hochladen", "bezug": {"issue": 12},
                              "hochladen": {"ziel": "youtube"}}, PRESETS)
    nb.restore_earlier(order, "o/r", runner=_fake_gh(tmp_path / "artefakt"))
    code, data = job.run_order(order, job.job_folder("gh0022"), via_claude=False)
    assert code == 1 and not data["ok"]
    assert "CUDI_YT_CLIENT_ID" in data["fehler"] and "Zugangsdaten fehlen" in data["fehler"]
    assert "Hat leider nicht geklappt" in nb.comment_text(data, "https://run")


def test_upload_of_missing_video_file_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    _earlier_result(tmp_path, with_video=False)
    order = nb.prepare_order({"id": "gh0023", "art": "ranking", "schritt": "hochladen", "bezug": {"issue": 12},
                              "hochladen": {"ziel": "youtube"}}, PRESETS)
    nb.restore_earlier(order, "o/r", runner=_fake_gh(tmp_path / "artefakt"))
    code, data = job.run_order(order, job.job_folder("gh0023"), via_claude=False)
    assert not data["ok"] and "nicht angekommen" in data["fehler"]


# --------------------------------------------------------------------------- Wiederholung bei Modellausfall

def _outage(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(job, "RETRY_PAUSE", 0)
    monkeypatch.setattr(handoff, "active", lambda: False)
    return nb.prepare_order({"id": "gh0030", "art": "fakten", "thema": "Haie"}, PRESETS)


def test_model_outage_retries_once_after_wait_then_reports(tmp_path, monkeypatch):
    order = _outage(tmp_path, monkeypatch)
    waits = []
    code, data = nb.run_with_retry(order, sleep=waits.append)
    assert waits == [600] and code == 1 and data["modell_ausfall"] and "Zweiter Versuch" in data["fehler"]
    assert json.loads((job.job_folder("gh0030") / "ergebnis.json").read_text("utf-8"))["modell_ausfall"] is True
    assert "zweiten Versuch" in nb.comment_text(data, "https://run")


def test_model_outage_second_try_can_succeed(tmp_path, monkeypatch):
    order = _outage(tmp_path, monkeypatch)
    results = iter([(1, {"ok": False, "modell_ausfall": True, "fehler": "x"}), (0, {"ok": True, "videos": []})])
    waits = []
    code, data = nb.run_with_retry(order, run=lambda *a, **k: next(results), sleep=waits.append, wait=5)
    assert code == 0 and data["ok"] and waits == [5]


def test_other_errors_are_not_retried(tmp_path, monkeypatch):
    order = _outage(tmp_path, monkeypatch)
    waits = []
    code, data = nb.run_with_retry(order, run=lambda *a, **k: (1, {"ok": False, "fehler": "Quellen fehlen"}), sleep=waits.append)
    assert waits == [] and code == 1

