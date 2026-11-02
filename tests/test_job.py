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
                     "sprachen": ["de", "en"], "plaetze": 7, "streng": True, "nur_skript": False}


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
