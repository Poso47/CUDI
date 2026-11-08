"""Fertiges Video in der App bearbeiten und nach Freigabe hochladen (Schritte „bearbeiten“ und „hochladen“)."""

import json

import pytest

from cudi_video import bearbeiten, job
from cudi_video.models import RankItem, Research
from cudi_video.spec import find_preset

PRESETS = {"groesste-seen", "hoechste-gebaeude"}


def _fixture(tmp_path, monkeypatch):
    """Ein fertiges 3-Platz-Ranking als Rendergrundlage (wie capture es sichert) im Ordner einer Cloud-Sitzung."""
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    repo = tmp_path / "CUDI"
    repo.mkdir()
    monkeypatch.chdir(repo)
    spec = find_preset("groesste-seen", 4)
    items = []
    for rank, (qid, de, en, value) in enumerate([("Q1", "Kaspisches Meer", "Caspian Sea", 371000),
                                                  ("Q2", "Oberer See", "Lake Superior", 82100),
                                                  ("Q3", "Victoriasee", "Lake Victoria", 68800),
                                                  ("Q4", "Huronsee", "Lake Huron", 59600)], 1):
        items.append(RankItem(qid=qid, value=value * 1e6, unit="Q25343", rank=rank, labels={"de": de, "en": en},
                              descriptions={"de": f"See in Asien {rank}", "en": "lake"}, image_path="/weg/nicht.jpg",
                              verification={"status": "confirmed", "sources": ["Weltbank"], "viel": "x" * 5000}))
    research = Research(spec_id=spec.id, fetched_at="2026-01-02T00:00:00", items=items)
    segs = {"de": [("intro", None, "Die größten Seen der Welt!"), ("item", 4, "Platz 4: Huronsee."),
                   ("item", 3, "Platz 3: Victoriasee."),
                   ("item", 2, "Platz 2: Oberer See."), ("item", 1, "Platz 1: Kaspisches Meer."),
                   ("outro", None, "Das war das Ranking.")],
            "en": [("intro", None, "The biggest lakes!"), ("item", 4, "Place 4: Lake Huron."),
                   ("item", 3, "Place 3: Lake Victoria."),
                   ("item", 2, "Place 2: Lake Superior."), ("item", 1, "Place 1: Caspian Sea."),
                   ("outro", None, "That was the ranking.")]}
    basis = {"version": 1, "id": "ededed1", "art": "ranking", "stand": "2026-01-02T00:00:00+00:00",
             "spec": spec.to_dict(), "research": research.to_dict(),
             "sprachen": {lang: {"titel": spec.title[lang],
                                 "segmente": [{"art": a, "rang": r, "text": t} for a, r, t in rows]}
                          for lang, rows in segs.items()},
             "stil": {"format": "karte", "design": "neon", "motion": "gleiten", "maskottchen": True, "tempo": 0},
             "optionen": bearbeiten._options()}
    return spec, basis


def _put(tmp_path, collection, folder_name, job_id, doc):
    path = tmp_path / folder_name / collection / f"{job_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), "utf-8")


def _mock_render(monkeypatch, seen):
    from cudi_video import tts
    from cudi_video.render import video

    def voice(script, out_dir, voice=None, rate=None, profile=None):
        seen.setdefault("rates", []).append(rate)
        for seg in script.segments:
            seg.duration, seg.words = 3.0, []
        return script

    def render(spec, research, script, out_dir, progress_cb=None):
        seen.setdefault("scripts", {})[script.lang] = script
        seen["style"] = video.style_for(spec)
        seen["items"] = [i.rank for i in research.items]
        (out_dir / f"{spec.id}_{script.lang}.mp4").write_bytes(b"video")
        return {"video": f"{spec.id}_{script.lang}.mp4", "cover": "", "subtitles": "", "duration": 15.0}

    monkeypatch.setattr(tts, "voice_script", voice)
    monkeypatch.setattr(video, "render_video", render)
    monkeypatch.setattr(bearbeiten, "_enrich", lambda research, langs: None)


# --------------------------------------------------------------------------- Textprüfung

def test_check_text_accepts_rephrasing_and_refuses_inventions():
    pool = "Platz 2: Oberer See. Der Oberer See ist 82100 Quadratkilometer groß. See in Nordamerika"
    old = "Platz 2: Oberer See."
    assert bearbeiten.check_text("Auf Platz 2 liegt der Oberer See.", old, pool, "de", {2}) == ""
    assert "Zahl" in bearbeiten.check_text("Platz 2: Oberer See mit 99000 Quadratkilometern.", old, pool, "de", {2})
    assert "Name" in bearbeiten.check_text("Platz 2: Oberer See, entdeckt von Michael.", old, pool, "de", {2})
    assert "Wort" in bearbeiten.check_text("Platz 2: der Oberer See bei Atlantis.", old, pool, "de", {2})
    assert "länger" in bearbeiten.check_text("wort " * 60, old, pool, "de")
    assert bearbeiten.check_text("  ", old, pool, "de") == "leer"


def test_compact_basis_stays_small_and_loses_local_paths():
    items = [{"qid": f"Q{i}", "value": 1.0, "unit": "Q199", "rank": i, "labels": {"de": "x"}, "image_path": "/tmp/a.jpg",
              "summary": {"de": "Text. " * 3000}, "descriptions": {}, "verification": {"status": "ok", "sources": ["a"], "x": "y" * 9000},
              "clips": [{"path": "/tmp/c.mp4", "credit": "c", "duration": 4, "kind": "video"}]} for i in range(10)]
    basis = {"art": "ranking", "research": {"items": items}, "sprachen": {}}
    small = bearbeiten._shrink(basis)
    assert len(json.dumps(small)) <= bearbeiten.MAX_COMPACT
    first = small["research"]["items"][0]
    assert first["image_path"] is None and "path" not in first["clips"][0] and "x" not in first["verification"]
    assert basis["research"]["items"][0]["image_path"] == "/tmp/a.jpg"          # Original bleibt unberührt


# --------------------------------------------------------------------------- Schritt „bearbeiten“

def test_order_accepts_the_new_steps():
    base = {"id": "abc123", "art": "ranking", "vorlage": "groesste-seen"}
    assert job.parse_order({**base, "schritt": "bearbeiten"}, PRESETS)["schritt"] == "bearbeiten"
    assert "schritt" not in job.parse_order(base, PRESETS)
    with pytest.raises(job.OrderError, match="Hochladen"):
        job.parse_order({**base, "schritt": "hochladen"}, PRESETS)
    wish = job.parse_order({**base, "schritt": "hochladen", "hochladen": {"ziel": "youtube", "freigabe": False}}, PRESETS)
    assert wish["hochladen"] == {"ziel": "youtube", "sichtbarkeit": "privat", "freigabe": False}
    with pytest.raises(job.OrderError, match="Schritt"):
        job.parse_order({**base, "schritt": "skelett"}, PRESETS)
    story = {"id": "abc123", "art": "story", "stimmung": "creepy"}
    assert job.parse_order({**story, "schritt": "bearbeiten"}, PRESETS)["schritt"] == "bearbeiten"


def test_edit_step_rerenders_with_checked_texts_without_new_research(tmp_path, monkeypatch):
    spec, basis = _fixture(tmp_path, monkeypatch)
    neu = {"format": "kreis", "design": "doku", "maskottchen": False, "tempo": 10, "wunsch": "",
           "sprachen": {"de": {"titel": "Die größten Seen!", "segmente": [
               {"art": "intro", "rang": None, "text": "Willkommen bei den größten Seen!"},
               {"art": "item", "rang": 3, "text": "Platz 3: Victoriasee."},
               {"art": "item", "rang": 1, "text": "Platz 1: Kaspisches Meer mit 500000 Quadratkilometern."},   # erfundene Zahl
               {"art": "item", "rang": 2, "text": "Auf Platz 2 liegt der Oberer See."},                          # ok
               {"art": "outro", "rang": None, "text": "Das war das Ranking."}]}}}                               # Platz 4 weggelassen
    _put(tmp_path, "bearbeitungen", "cudi_bearbeitungen", "ededed1", {"basis": basis, "neu": neu})
    seen = {}
    _mock_render(monkeypatch, seen)
    monkeypatch.setattr("cudi_video.pipeline.research_stage", lambda *a, **k: pytest.fail("keine neue Recherche"))
    order = job.parse_order({"id": "ededed1", "art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten",
                             "plaetze": 3}, PRESETS)
    code, data = job.run_order(order, job.job_folder("ededed1"))
    assert code == 0 and data["ok"], data["fehler"]
    de = seen["scripts"]["de"]
    assert [s.text for s in de.segments][0] == "Willkommen bei den größten Seen!"
    assert "Auf Platz 2 liegt der Oberer See." in [s.text for s in de.segments]
    assert "Platz 1: Kaspisches Meer." in [s.text for s in de.segments]                 # abgelehnt: alter Text
    assert not any("500000" in s.text for s in de.segments)
    assert [s.rank for s in de.segments if s.kind == "item"] == [3, 1, 2]              # Platz 4 entfällt, Folge geändert
    assert seen["items"] == [1, 2, 3] and [s.rank for s in seen["scripts"]["en"].segments if s.kind == "item"] == [3, 1, 2]
    assert seen["style"]["format"] == "kreis" and seen["style"]["name"] == "doku"
    assert seen["rates"][0] == "+10%"
    assert any("Platz 1 (DE) abgelehnt" in h and "500000" in h for h in data["hinweise"])
    assert any("Weggelassen: Platz 4" in h for h in data["hinweise"])
    # Das neue Ergebnis trägt wieder eine Bearbeitungsgrundlage mit den neuen Einstellungen
    new = data["bearbeitung"]
    assert new["stil"]["format"] == "kreis" and new["stil"]["design"] == "doku" and new["stil"]["tempo"] == 10
    assert new["stil"]["maskottchen"] is False
    assert [s["rang"] for s in new["sprachen"]["de"]["segmente"] if s["art"] == "item"] == [3, 1, 2]
    doc = job.document(job.job_folder("ededed1"), {})
    assert doc["bearbeitung"]["stand"] and (job.job_folder("ededed1") / "bearbeitung.json").exists()


def test_edit_step_without_file_from_the_app_fails_cleanly(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(job, "RETRY_PAUSE", 0)
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    monkeypatch.setattr(job.time, "time", iter(range(0, 10_000, 100)).__next__)
    order = job.parse_order({"id": "ededed2", "art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten"}, PRESETS)
    code, data = job.run_order(order, job.job_folder("ededed2"))
    assert code == 1 and "nicht angekommen" in data["fehler"]


def test_free_text_wish_goes_through_the_writing_task_and_is_checked(tmp_path, monkeypatch):
    spec, basis = _fixture(tmp_path, monkeypatch)
    neu = {"wunsch": "Mach den Einstieg spannender", "sprachen": {}}
    _put(tmp_path, "bearbeitungen", "cudi_bearbeitungen", "ededed3", {"basis": basis, "neu": neu})
    seen = {}
    _mock_render(monkeypatch, seen)
    monkeypatch.setenv(job.handoff.ENV, "1")

    def answer(task, instructions, data):
        assert task == "bearbeiten" and data["wunsch"] == "Mach den Einstieg spannender"
        assert "platz_3" in data["sprachen"]["de"] and "platz_2" in data["fakten"]
        return {"de": {"intro": "Kennst du die größten Seen der Welt?",                      # ok
                       "platz_1": "Platz 1: Kaspisches Meer, 12345 Meter tief."},            # erfundene Zahl
                "en": {"intro": "The biggest lakes, according to Zoltan."}}                  # erfundener Name

    monkeypatch.setattr(job.handoff, "request", answer)
    order = job.parse_order({"id": "ededed3", "art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten"}, PRESETS)
    code, data = job.run_order(order, job.job_folder("ededed3"))
    assert code == 0
    assert seen["scripts"]["de"].segments[0].text == "Kennst du die größten Seen der Welt?"
    assert seen["scripts"]["en"].segments[0].text == "The biggest lakes!"
    assert not any("12345" in s.text for s in seen["scripts"]["de"].segments)
    assert sum("abgelehnt" in h for h in data["hinweise"]) == 2


def test_free_text_wish_without_any_model_is_reported_not_fatal(tmp_path, monkeypatch):
    spec, basis = _fixture(tmp_path, monkeypatch)
    _put(tmp_path, "bearbeitungen", "cudi_bearbeitungen", "ededed4", {"basis": basis, "neu": {"wunsch": "Lustiger", "tempo": -5}})
    seen = {}
    _mock_render(monkeypatch, seen)
    monkeypatch.delenv(job.handoff.ENV, raising=False)
    monkeypatch.delenv("CUDI_LLM_BASE_URL", raising=False)
    order = job.parse_order({"id": "ededed4", "art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten"}, PRESETS)
    code, data = job.run_order(order, job.job_folder("ededed4"))
    assert code == 0 and seen["rates"][0] == "-5%"
    assert any("Wunsch" in h and "nicht umsetzen" in h for h in data["hinweise"])


def test_too_long_edit_falls_back_to_the_old_texts(tmp_path, monkeypatch):
    from cudi_video import tts

    spec, basis = _fixture(tmp_path, monkeypatch)
    neu = {"sprachen": {"de": {"segmente": [{"art": "item", "rang": 1, "text": "Platz 1: Kaspisches Meer. " * 2}]}}}
    _put(tmp_path, "bearbeitungen", "cudi_bearbeitungen", "ededed5", {"basis": basis, "neu": neu})
    seen = {}
    _mock_render(monkeypatch, seen)
    calls = []

    def voice(script, out_dir, voice=None, rate=None, profile=None):
        calls.append(script.segments[4].text)
        for seg in script.segments:
            seg.duration = 100.0 if "Meer. Platz" in calls[-1] else 3.0
        return script

    monkeypatch.setattr(tts, "voice_script", voice)
    order = job.parse_order({"id": "ededed5", "art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten"}, PRESETS)
    code, data = job.run_order(order, job.job_folder("ededed5"))
    assert code == 0 and seen["scripts"]["de"].segments[4].text == "Platz 1: Kaspisches Meer."
    assert any("zu lang" in h for h in data["hinweise"])


def test_story_edit_checks_scenes_and_renders_again(tmp_path, monkeypatch):
    from cudi_video.story import pipeline

    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    repo = tmp_path / "CUDI"
    repo.mkdir()
    monkeypatch.chdir(repo)
    sk = {"version": 1, "lang": "de", "mood": "creepy", "title": "Der Beobachter", "voice": {"name": "x"}, "visuals": "images",
          "post": {"id": "abc", "text": "Er stand da."}, "notes": [], "rights": [],
          "parts": [{"intro": "Der Beobachter", "outro": "Folge für mehr.", "estimated_seconds": 40,
                     "scenes": [{"text": "Es war dunkel.", "source": "", "query": "forest", "prompt": "forest"},
                                {"text": "Dann kam er näher.", "source": "", "query": "man", "prompt": "man"}]}]}
    basis = {"art": "story", "id": "ststst1", "skelett": sk, "stil": {"maskottchen": True}, "optionen": {}}
    edited = json.loads(json.dumps(sk))
    edited["parts"][0]["scenes"][0].update(text="Es war stockdunkel.", _o=0)           # ok
    edited["parts"][0]["scenes"][1].update(text="Dann kam er näher, es war 3 Uhr, sagte Peter.", _o=1)   # Zahl + Name
    edited["parts"][0]["scenes"].append({"text": "Ein ganz neuer Satz mit Erfindung 77.", "query": "x", "prompt": "x"})
    _put(tmp_path, "bearbeitungen", "cudi_bearbeitungen", "ststst1", {"basis": basis, "neu": {"skelett": edited, "maskottchen": False}})
    seen = {}

    def render(folder, skeleton=None, progress=None):
        seen["texts"] = [s["text"] for p in skeleton["parts"] for s in p["scenes"]]
        return {"output_dir": str(folder), "videos": {}, "warnings": []}

    monkeypatch.setattr(pipeline, "render", render)
    monkeypatch.setattr(pipeline, "new_folder", lambda title: tmp_path / "story")
    (tmp_path / "story").mkdir()
    order = job.parse_order({"id": "ststst1", "art": "story", "stimmung": "creepy", "schritt": "bearbeiten"}, PRESETS)
    code, data = job.run_order(order, job.job_folder("ststst1"))
    assert code == 0, data["fehler"]
    assert seen["texts"] == ["Es war stockdunkel.", "Dann kam er näher."]
    assert len(data["hinweise"]) == 2 and job.os.environ["CUDI_MASCOT"] == "0"


# --------------------------------------------------------------------------- Freigabe und Schritt „hochladen“

def _finished(monkeypatch, tmp_path):
    out = tmp_path / "out" / "v"
    out.mkdir(parents=True)
    (out / "v_de.mp4").write_bytes(b"x" * 100)

    def ranking(order, folder, progress):
        return {"output_dir": str(out), "warnings": [], "videos": {"de": {"video": "v_de.mp4", "cover": "", "duration": 12.0}}}

    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(job, "_ranking", ranking)


def test_upload_wish_waits_for_release_by_default(tmp_path, monkeypatch):
    from cudi_video.upload import cli

    _finished(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(cli, "upload_order", lambda wish, data: calls.append(wish) or [{"ziel": "youtube", "ok": True}])
    base = {"id": "frfrfr1", "art": "ranking", "vorlage": "groesste-seen"}
    order = job.parse_order({**base, "hochladen": {"ziel": "youtube"}}, PRESETS)
    code, data = job.run_order(order, job.job_folder("frfrfr1"))
    assert code == 0 and not calls and "hochgeladen" not in data
    assert data["hochladen_offen"] == {"ziel": "youtube", "sichtbarkeit": "privat"}
    assert any("Veröffentlichen" in h for h in data["hinweise"])
    order = job.parse_order({**base, "id": "frfrfr2", "hochladen": {"ziel": "youtube", "freigabe": False}}, PRESETS)
    code, data = job.run_order(order, job.job_folder("frfrfr2"))
    assert len(calls) == 1 and data["hochgeladen"][0]["ok"] and "hochladen_offen" not in data


def test_upload_step_publishes_the_finished_video_without_rendering(tmp_path, monkeypatch):
    from cudi_video.upload import cli

    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    repo = tmp_path / "CUDI"
    repo.mkdir()
    monkeypatch.chdir(repo)
    a, b = "a" * 32, "b" * 32
    old = {"id": "upupup1", "art": "ranking", "ok": True, "titel": "Seen", "fehler": "", "wiederholbar": True,
           "hinweise": ["Bereit zum Veröffentlichen – tippe …", "Bild fehlt"], "pruefbericht": "# B",
           "hochladen_offen": {"ziel": "youtube", "sichtbarkeit": "privat"}, "bearbeitung": {"stand": "s"},
           "videos": [{"key": "de", "video_url": "", "teile_urls": [f"https://x/{a}", f"https://x/{b}"], "cover_url": "c",
                       "youtube": "Titel\n\nBeschreibung\n#shorts #seen", "tiktok": "Kurztext", "mb": 3}]}
    _put(tmp_path, "results", "cudi_hochladen", "upupup1", old)
    folder = tmp_path / "cudi_hochladen" / "upupup1"
    folder.mkdir(parents=True)
    (folder / f"{a}.mp4").write_bytes(b"AAAA")
    (folder / f"{b}.mp4").write_bytes(b"BB")
    sent = []

    def run_one(material, target, visibility, mode="inbox"):
        sent.append((material.video.read_bytes(), material.title, material.tags, material.caption, target, visibility))
        return {"url": "https://youtube.com/watch?v=1"} if target == "youtube" else {"publish_id": "p"}

    monkeypatch.setattr(cli, "run_one", run_one)
    for name in ("_ranking", "_story", "_clip", "_bearbeiten"):
        monkeypatch.setattr(job, name, lambda *a, **k: pytest.fail("kein Rendern beim Hochladen"))
    order = job.parse_order({"id": "upupup1", "art": "ranking", "vorlage": "groesste-seen", "schritt": "hochladen",
                             "hochladen": {"ziel": "beide", "sichtbarkeit": "privat", "freigabe": False}}, PRESETS)
    code, data = job.run_order(order, job.job_folder("upupup1"))
    assert code == 0 and data["ok"]
    assert sent[0] == (b"AAAABB", "Titel", ["shorts", "seen"], "Kurztext", "youtube", "privat")
    assert [s[4] for s in sent] == ["youtube", "tiktok"]
    doc = job.document(job.job_folder("upupup1"), {})
    assert doc["videos"][0]["teile_urls"] == old["videos"][0]["teile_urls"] and doc["titel"] == "Seen"   # Karte bleibt erhalten
    assert doc["bearbeitung"] == {"stand": "s"} and "hochladen_offen" not in doc
    assert doc["hinweise"][0] == "Bild fehlt" and any("youtube.com/watch?v=1" in h for h in doc["hinweise"])
    assert doc["fertig"] != old.get("fertig")


def test_upload_step_error_keeps_card_and_release_button(tmp_path, monkeypatch):
    from cudi_video.upload import UploadError, cli

    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    repo = tmp_path / "CUDI"
    repo.mkdir()
    monkeypatch.chdir(repo)
    a = "c" * 32
    old = {"id": "upupup2", "art": "story", "ok": True, "titel": "T", "hinweise": [], "videos": [
        {"key": "de", "video_url": f"https://x/{a}", "teile_urls": [], "youtube": "T\n\nB", "tiktok": "t"}]}
    _put(tmp_path, "results", "cudi_hochladen", "upupup2", old)
    (tmp_path / "cudi_hochladen" / "upupup2").mkdir(parents=True)
    (tmp_path / "cudi_hochladen" / "upupup2" / f"{a}.mp4").write_bytes(b"V")

    def run_one(*a, **k):
        raise UploadError("Zugangsdaten fehlen (Umgebungsvariablen): CUDI_YT_CLIENT_ID")

    monkeypatch.setattr(cli, "run_one", run_one)
    order = job.parse_order({"id": "upupup2", "art": "story", "stimmung": "creepy", "schritt": "hochladen",
                             "hochladen": {"ziel": "youtube", "freigabe": False}}, PRESETS)
    code, data = job.run_order(order, job.job_folder("upupup2"))
    doc = job.document(job.job_folder("upupup2"), {})
    assert code == 0 and doc["ok"] and doc["videos"] and doc["hochladen_offen"]["ziel"] == "youtube"
    assert "Hochladen fehlgeschlagen" in doc["hinweise"][-1]
    # fehlt die Videodatei ganz, ist das ein Hinweis – das Dokument bleibt
    (tmp_path / "cudi_hochladen" / "upupup2" / f"{a}.mp4").unlink()
    code, data = job.run_order(order, job.job_folder("upupup2"))
    assert any("nicht angekommen" in h for h in job.document(job.job_folder("upupup2"), {})["hinweise"])
