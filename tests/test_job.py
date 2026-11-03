"""Aufträge der CUDI-App (Claude-Cloud-Sitzung): prüfen, übersetzen lassen, App-Fassung, Dokument."""

import json
import subprocess
import types

import pytest

from cudi_video import job

PRESETS = {"hoechste-gebaeude", "groesste-laender"}


def test_ranking_order_is_normalised():
    order = job.parse_order({"id": "abc123", "art": "ranking", "vorlage": "hoechste-gebaeude", "thema": "",
                             "sprachen": ["en", "de", "fr"], "plaetze": "7", "streng": True}, PRESETS)
    assert order == {"id": "abc123", "art": "ranking", "thema": "", "vorlage": "hoechste-gebaeude",
                     "sprachen": ["de", "en"], "plaetze": 7, "streng": True, "nur_skript": False, "laenge": ""}


def test_story_order_cleans_text_and_keeps_defaults():
    order = job.parse_order({"id": "s-1_x", "art": "story", "wunsch": "Stalker\n im\x00 Wald", "stimmung": "creepy"},
                            PRESETS)
    assert order["wunsch"] == "Stalker im Wald"
    assert (order["sprache"], order["laenge"], order["bilder"], order["entschaerfen"]) == ("de", "3min", "videos", True)


@pytest.mark.parametrize("raw, reason", [
    ({"id": "x", "art": "story", "stimmung": "creepy"}, "Kennung"),
    ({"id": "abcd", "art": "ranking", "vorlage": "gibt-es-nicht"}, "Vorlage"),
    ({"id": "abcd", "art": "ranking", "vorlage": "hoechste-gebaeude", "plaetze": 50}, "3 bis 20"),
    ({"id": "abcd", "art": "ranking", "vorlage": "hoechste-gebaeude", "sprachen": ["fr"]}, "Sprache"),
    ({"id": "abcd", "art": "story", "stimmung": "auto"}, "Stimmung wählen"),
    ({"id": "abcd", "art": "story", "stimmung": "traurig"}, "Unbekannte Stimmung"),
    ({"id": "abcd", "art": "story", "stimmung": "funny", "laenge": "ewig"}, "ungültig"),
    ({"id": "abcd", "art": "kochen"}, "Unbekannte Art"),
])
def test_invalid_orders_are_refused(raw, reason):
    with pytest.raises(job.OrderError, match=reason):
        job.parse_order(raw, PRESETS)


def test_claude_translation_handoff(tmp_path, monkeypatch):
    from cudi_video.story import translate as tr

    path = tmp_path / "uebersetzen.json"
    monkeypatch.setenv(tr.CLAUDE_FILE_ENV, str(path))
    monkeypatch.setattr(tr.llm, "available", lambda: False)
    monkeypatch.setattr(tr.config, "DEEPL_API_KEY", "")
    monkeypatch.setattr(tr, "_mymemory", lambda *a: pytest.fail("im Auftragsmodus kein Gratis-Dienst"))
    with pytest.raises(tr.TranslationNeeded) as need:
        tr.translate(["Hello.", "It was dark."], "de", "en")
    assert need.value.texts == ["Hello.", "It was dark."]
    path.write_text(json.dumps({"texte": ["Hello.", "It was dark."], "uebersetzt": ["Hallo.", "Es war dunkel."]}))
    assert tr.translate(["Hello.", "It was dark."], "de", "en") == (["Hallo.", "Es war dunkel."], "Claude")
    path.write_text(json.dumps({"texte": ["Hello.", "It was dark."], "uebersetzt": ["Hallo."]}))  # unvollständig
    with pytest.raises(tr.TranslationNeeded):
        tr.translate(["Hello.", "It was dark."], "de", "en")


def test_without_job_mode_translation_still_uses_free_service(monkeypatch):
    from cudi_video.story import translate as tr

    monkeypatch.delenv(tr.CLAUDE_FILE_ENV, raising=False)
    monkeypatch.setattr(tr.llm, "available", lambda: False)
    monkeypatch.setattr(tr.config, "DEEPL_API_KEY", "")
    monkeypatch.setattr(tr, "_mymemory", lambda texts, target, source: ["Hallo."])
    assert tr.translate(["Hello."], "de", "en") == (["Hallo."], "MyMemory")


def test_app_version_fits_budget(tmp_path):
    src = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=300", "-t", "4", "-c:v", "libx264", "-crf", "10",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)
    budget = 1_200_000
    assert src.stat().st_size > budget
    out = job.app_version(src, tmp_path / "v_app.mp4", budget=budget)
    assert out.stat().st_size <= budget
    small = job.app_version(out, tmp_path / "copy.mp4", budget=budget)        # passt schon: nur kopieren
    assert small.read_bytes() == out.read_bytes()


def test_document_maps_uploads_and_reports_missing_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path)
    folder = job.job_folder("abc123")
    folder.mkdir()
    (folder / "ergebnis.json").write_text(json.dumps({
        "id": "abc123", "art": "story", "ok": True, "titel": "Das Spiegelbild", "fehler": "", "hinweise": ["Rechte"],
        "pruefbericht": "# Bericht", "videos": [{"key": "de", "video": "/x/story_de_app.mp4", "cover": "/x/story_de_cover.jpg",
                                                  "dauer": 48.4, "mb": 18.0, "youtube": "YT", "tiktok": "TT"}]}))
    doc = job.document(folder, {"/x/story_de_app.mp4": "https://a/1", "story_de_cover.jpg": "https://a/2"})
    assert doc["ok"] and doc["videos"][0]["video_url"] == "https://a/1" and doc["videos"][0]["cover_url"] == "https://a/2"
    assert doc["videos"][0]["datei"] == "story_de.mp4" and doc["titel"] == "Das Spiegelbild"
    doc = job.document(folder, {})                                             # Upload fehlgeschlagen
    assert not doc["ok"] and "nicht in die App laden" in doc["fehler"]


def test_document_without_result_explains_abort(tmp_path, monkeypatch):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path)
    folder = job.job_folder("zz99")
    folder.mkdir()
    (folder / "auftrag.log").write_text("ModuleNotFoundError: No module named 'edge_tts'\n")
    doc = job.document(folder, {})
    assert doc["id"] == "zz99" and not doc["ok"] and "edge_tts" in doc["fehler"]


def test_main_prints_lines_for_the_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path)
    data = {"id": "abc123", "art": "ranking", "ok": True, "fehler": "", "videos": [
        {"key": "de", "video": "/x/a_app.mp4", "cover": "/x/a.jpg"}, {"key": "en", "video": "/x/b_app.mp4", "cover": None}]}
    monkeypatch.setattr(job, "run_order", lambda order, folder: (0, data))
    args = types.SimpleNamespace(dokument=None, weiter=None, adressen=None,
                                 auftrag=json.dumps({"id": "abc123", "art": "ranking", "vorlage": "hoechste-gebaeude"}))
    assert job.main(args) == 0
    out = capsys.readouterr().out
    assert 'DATEIEN: ["/x/a_app.mp4", "/x/a.jpg", "/x/b_app.mp4"]' in out and "ERGEBNIS:" in out


def test_transient_failure_is_retried_once_but_input_errors_are_not(tmp_path, monkeypatch):
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(order, folder, progress):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("Dienst kurz weg")
        return {"output_dir": str(tmp_path), "videos": {}, "warnings": []}

    monkeypatch.setattr(job, "_ranking", flaky)
    order = {"id": "rt1", "art": "ranking"}
    code, data = job.run_order(order, tmp_path / "a")
    assert code == 0 and data["ok"] and calls["n"] == 2

    def bad(order, folder, progress):
        calls["n"] += 1
        raise ValueError("Die Story wurde gelöscht oder hat keinen Text (nur Bild/Link).")

    calls["n"] = 0
    monkeypatch.setattr(job, "_ranking", bad)
    code, data = job.run_order(order, tmp_path / "b")
    assert code == 1 and calls["n"] == 1 and "gelöscht" in data["fehler"]


def test_result_says_whether_an_error_is_worth_repeating(tmp_path, monkeypatch):
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path)

    def bad(order, folder, progress):
        raise ValueError("Das sieht nicht nach einem Reddit-Link aus.")

    def down(order, folder, progress):
        raise ConnectionError("weg")

    for fn, expected in ((bad, False), (down, True)):
        monkeypatch.setattr(job, "_ranking", fn)
        folder = job.job_folder("w" + str(expected))
        code, data = job.run_order({"id": "w" + str(expected), "art": "ranking"}, folder)
        assert code == 1 and data["wiederholbar"] is expected
        assert job.document(folder, {})["wiederholbar"] is expected


SKELETON = {"version": 1, "lang": "de", "mood": "creepy", "title": "Der Beobachter", "voice": None, "visuals": "images",
            "post": {"id": "abc", "text": "I (25F) saw him."}, "notes": [], "rights": ["Rechte-Hinweis"],
            "parts": [{"intro": "Der Beobachter", "outro": "Folge für mehr.", "estimated_seconds": 40,
                       "scenes": [{"text": "Es war dunkel.", "source": "", "query": "dark forest", "prompt": "dark forest"}]}]}


def test_story_order_accepts_the_two_steps():
    base = {"id": "step1", "art": "story", "stimmung": "creepy"}
    assert job.parse_order(base, PRESETS)["schritt"] == ""
    assert job.parse_order({**base, "schritt": "skelett"}, PRESETS)["schritt"] == "skelett"
    assert job.parse_order({**base, "schritt": "video"}, PRESETS)["schritt"] == "video"
    with pytest.raises(job.OrderError, match="Schritt"):
        job.parse_order({**base, "schritt": "rendern"}, PRESETS)


def test_skeleton_step_returns_the_skeleton_for_the_app(tmp_path, monkeypatch):
    from cudi_video.story import pipeline

    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path)
    story_dir = tmp_path / "story"
    story_dir.mkdir()
    (story_dir / "spec.json").write_text(json.dumps({"title": {"de": "Der Beobachter"}}))
    monkeypatch.setattr(pipeline, "search", lambda *a, **k: {"stories": [{"id": "abc"}], "plan": {"mood": "creepy"},
                                                               "notes": []})
    monkeypatch.setattr(pipeline, "prepare", lambda **k: (SKELETON, story_dir))
    monkeypatch.setattr(pipeline, "render", lambda *a, **k: pytest.fail("Schritt 1 rendert nicht"))
    order = job.parse_order({"id": "skel1", "art": "story", "stimmung": "creepy", "schritt": "skelett"}, PRESETS)
    folder = job.job_folder("skel1")
    code, data = job.run_order(order, folder)
    assert code == 0 and data["ok"] and data["schritt"] == "skelett" and data["skelett"]["title"] == "Der Beobachter"
    assert job.uploads(data) == [] and "Rechte-Hinweis" in data["hinweise"]
    doc = job.document(folder, {})
    assert doc["ok"] and doc["schritt"] == "skelett" and doc["skelett"]["parts"][0]["scenes"][0]["text"] == "Es war dunkel."


def test_video_step_renders_the_skeleton_edited_in_the_app(tmp_path, monkeypatch):
    from cudi_video.story import pipeline

    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    repo = tmp_path / "CUDI"
    repo.mkdir()
    monkeypatch.chdir(repo)
    edited = json.loads(json.dumps(SKELETON))
    edited["parts"][0]["scenes"][0]["text"] = "Vom Nutzer geändert."
    (tmp_path / "cudi_skelette" / "skelette").mkdir(parents=True)
    (tmp_path / "cudi_skelette" / "skelette" / "vid1.json").write_text(json.dumps(edited), "utf-8")
    seen = {}

    def render(folder, skeleton=None, progress=None):
        seen["text"] = skeleton["parts"][0]["scenes"][0]["text"]
        return {"output_dir": str(folder), "videos": {}, "warnings": []}

    monkeypatch.setattr(pipeline, "render", render)
    monkeypatch.setattr(pipeline, "search", lambda *a, **k: pytest.fail("Schritt 2 sucht nicht neu"))
    order = job.parse_order({"id": "vid1", "art": "story", "stimmung": "creepy", "schritt": "video"}, PRESETS)
    code, data = job.run_order(order, job.job_folder("vid1"))
    assert code == 0 and seen["text"] == "Vom Nutzer geändert."
    (tmp_path / "cudi_skelette" / "skelette" / "vid1.json").unlink()
    with pytest.raises(RuntimeError, match="nicht angekommen"):
        job.app_skeleton("vid1", wait=0)


def test_fit_parts_keeps_every_part_short_and_numbers_them():
    from cudi_video.story.editor import OUTRO_NEXT

    long_text = " ".join(["Ein ziemlich langer Satz mit genau zehn Wörtern hier drin."] * 60)   # ~600 Wörter
    sk = json.loads(json.dumps(SKELETON))
    sk["title"] = "Neuer Titel"
    sk["parts"] = [{"intro": "Teil 2. Alter Titel", "outro": OUTRO_NEXT["de"].format(n=3), "estimated_seconds": 50,
                    "scenes": [{"text": long_text, "source": "", "query": "q", "prompt": "q"}]}]
    notes = job.fit_parts(sk)
    assert len(sk["parts"]) >= 2 and notes
    assert sk["parts"][0]["intro"] == "Neuer Titel" and sk["parts"][1]["intro"] == "Teil 2. Neuer Titel"
    assert sk["parts"][0]["outro"] == OUTRO_NEXT["de"].format(n=2)
    assert "kommt bald" not in sk["parts"][-1]["outro"]                     # Schluss statt Ankündigung
    assert all(p["estimated_seconds"] <= job.config.STORY_MAX_SECONDS for p in sk["parts"])

    short = json.loads(json.dumps(SKELETON))
    short["title"] = "Anderer Titel"
    assert job.fit_parts(short) == [] and short["parts"][0]["intro"] == "Anderer Titel"
    assert short["parts"][0]["outro"] == "Folge für mehr."


def test_long_videos_more_places_and_files_in_pieces(tmp_path, monkeypatch):
    base = {"id": "lang1", "art": "ranking", "vorlage": "hoechste-gebaeude"}
    assert job.parse_order({**base, "laenge": "lang", "plaetze": 30}, PRESETS)["plaetze"] == 30
    with pytest.raises(job.OrderError, match="3 bis 20"):
        job.parse_order({**base, "plaetze": 25}, PRESETS)
    assert job.parse_order({"id": "lang2", "art": "story", "stimmung": "creepy", "laenge": "lang"}, PRESETS)["laenge"] == "lang"

    big = tmp_path / "v_app.mp4"
    big.write_bytes(bytes(range(256)) * 400)                      # 102 400 Bytes
    chunks = job.split_for_app(big, size=40_000)
    assert [c.name for c in chunks] == ["v_app_stueck01.mp4", "v_app_stueck02.mp4", "v_app_stueck03.mp4"]
    assert b"".join(c.read_bytes() for c in chunks) == big.read_bytes()       # wieder zusammengesetzt = Original
    assert job.split_for_app(chunks[2], size=40_000) == [chunks[2]]

    data = {"videos": [{"key": "de", "video": str(big), "cover": "/x/c.jpg", "teile": [str(c) for c in chunks]}]}
    assert job.uploads(data) == [str(c) for c in chunks] + ["/x/c.jpg"]
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path)
    folder = job.job_folder("lang1")
    folder.mkdir()
    (folder / "ergebnis.json").write_text(json.dumps({"id": "lang1", "art": "ranking", "ok": True, "fehler": "",
                                                      **data}))
    doc = job.document(folder, {str(c): f"/_blob/{i}" for i, c in enumerate(chunks)} | {"/x/c.jpg": "/_blob/c"})
    assert doc["ok"] and doc["videos"][0]["teile_urls"] == ["/_blob/0", "/_blob/1", "/_blob/2"]
    assert doc["videos"][0]["video_url"] == ""
    doc = job.document(folder, {str(chunks[0]): "/_blob/0"})                 # ein Stück fehlt
    assert not doc["ok"]


def test_long_story_parts_may_run_ten_minutes():
    text = " ".join(["Ein ziemlich langer Satz mit genau zehn Wörtern hier drin."] * 60)   # ~600 Wörter
    sk = json.loads(json.dumps(SKELETON))
    sk["length"] = "lang"
    sk["parts"][0]["scenes"][0]["text"] = text
    assert job.fit_parts(sk) == [] and len(sk["parts"]) == 1                 # passt am Stück (≤ 10 Min.)


def test_long_ranking_supports_up_to_30_places():
    """Langmodus: 21–30 Plätze laden sich über Vorlage und freies Thema (nicht still auf 20 gekürzt)."""
    from cudi_video.__main__ import _load
    from cudi_video.topics import plan_from_text

    assert _load("hoechste-gebaeude", 25).count == 25
    assert plan_from_text("die höchsten Berge der Welt", 30)["count"] == 30
    assert plan_from_text("die 25 höchsten Berge der Welt")["count"] == 20      # ohne Langmodus höchstens 20


def test_factbook_region_cache_is_thread_safe(tmp_path, monkeypatch):
    import threading

    from cudi_video import config
    from cudi_video.verify.checkers import FactbookChecker

    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    threads = [threading.Thread(target=FactbookChecker._remember, args=(f"c{i}", "europe")) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(FactbookChecker._regions()) == 20                 # kein Eintrag verloren, gültiges JSON
