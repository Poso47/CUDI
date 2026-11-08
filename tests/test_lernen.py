"""Experimente (Bandit), Lern-Analyst, Vorlieben -> Gewichte und die Videoart „Reportage“ (Quellen gemockt)."""

import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from cudi_video import experimente, handoff, job, reportage
from cudi_video.firma import common, ideen, lernen
from cudi_video.render import theme

ROOT = Path(__file__).resolve().parent.parent
ARMS = ["karte", "vollbild", "kreis", "magazin"]


@pytest.fixture(autouse=True)
def umgebung(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    for name in ("CUDI_EXPERIMENTE", experimente.PREFS_ENV, "CUDI_VARIANTE_MUSIK", "CUDI_FORMAT"):
        monkeypatch.delenv(name, raising=False)
    experimente.begin()
    yield tmp_path / "firma_daten"
    experimente.begin()


def schreibe_lernen(daten, gewichte):
    daten.mkdir(parents=True, exist_ok=True)
    (daten / "lernen.json").write_text(json.dumps({"gewichte": gewichte}), "utf-8")


# --------------------------------------------------------------------------- Bandit

def test_ohne_daten_bleibt_die_alte_wahl_und_ist_reproduzierbar():
    a = theme.pick_style("video-1", "mountain", "numbers", topic="Berge")
    b = theme.pick_style("video-1", "mountain", "numbers", topic="Berge")
    assert a == b

    def h(salt, n):
        return int(hashlib.md5(f"video-1{salt}".encode()).hexdigest(), 16) % n

    assert a["format"] == theme.FORMAT_NAMES[h("format", len(theme.FORMAT_NAMES))]
    assert a["motion"] == list(theme.MOTIONS)[h("motion", len(theme.MOTIONS))]
    assert set(experimente.current()["_grund"].values()) == {"erkundung"}


def test_bandit_bevorzugt_gewinner_aber_erkundet_mindestens_20_prozent(umgebung):
    schreibe_lernen(umgebung, {"format": {"karte": {"gut": 30, "schlecht": 0}, "kreis": {"gut": 0, "schlecht": 30},
                                          "vollbild": {"gut": 0, "schlecht": 30}, "magazin": {"gut": 0, "schlecht": 30}}})
    picks = [experimente.choose(f"id{i}", "format", ARMS) for i in range(600)]
    best = picks.count("karte") / len(picks)
    assert best > 0.7                                   # gelernt
    assert (1 - best) >= 0.10                           # Erkundung bleibt (20 % gleichverteilt, davon ¼ ohnehin „karte“)
    assert picks == [experimente.choose(f"id{i}", "format", ARMS) for i in range(600)]      # gleiche Video-ID -> gleiche Wahl
    reasons = set()
    for i in range(200):
        experimente.choose(f"r{i}", "format", ARMS)
        reasons.add(experimente.CURRENT["format"]["grund"])
    assert reasons == {"bandit", "erkundung"}


def test_fester_wunsch_hat_vorrang_und_zaehlt_nicht_als_experiment(umgebung):
    schreibe_lernen(umgebung, {"format": {"karte": {"gut": 50, "schlecht": 0}}})
    assert experimente.choose("x1", "format", ARMS, fixed="kreis") == "kreis"
    assert experimente.current()["_grund"]["format"] == "wunsch"
    assert theme.pick_style("x1", None, "numbers", wanted="polaroid")["format"] == "polaroid"


def test_experimente_abschaltbar(umgebung, monkeypatch):
    schreibe_lernen(umgebung, {"format": {"karte": {"gut": 50, "schlecht": 0}}})
    monkeypatch.setenv("CUDI_EXPERIMENTE", "0")
    picks = {experimente.choose(f"id{i}", "format", ARMS) for i in range(60)}
    assert len(picks) == len(ARMS)                      # wieder gleichverteilt (alte md5-Wahl)


def test_bewertungen_der_app_verschieben_die_wahl(monkeypatch):
    prefs = {"gut": [{"format": "zahl"}] * 4, "schlecht": [{"format": "karte"}] * 4}
    monkeypatch.setenv(experimente.PREFS_ENV, json.dumps(prefs))
    assert experimente.counts("format", "zahl") == (4 * experimente.PREF_WEIGHT, 0)
    assert experimente.counts("format", "karte") == (0, 4 * experimente.PREF_WEIGHT)
    picks = [experimente.choose(f"v{i}", "format", theme.FORMAT_NAMES) for i in range(500)]
    assert picks.count("zahl") > picks.count("karte") * 2


def test_parse_preferences_nimmt_varianten_nur_bekannter_schrauben():
    out = job.parse_preferences({"gut": ["Ranking: Berge"], "varianten_gut": [{"format": "zahl", "evil": "x", "design": "neon"}],
                                 "varianten_schlecht": [{"format": "Karte; DROP"}, "kaputt"]})
    assert out["gut"] == ["Ranking: Berge"]
    assert out["varianten_gut"] == [{"format": "zahl", "design": "neon"}]
    assert "varianten_schlecht" not in out


def test_run_order_gibt_vorlieben_getrennt_weiter(tmp_path, monkeypatch):
    seen = {}

    def fake_ranking(order, folder, progress):
        seen["prefs"] = json.loads(os.environ.get(handoff.PREFS_ENV, "{}"))
        seen["variants"] = json.loads(os.environ.get(experimente.PREFS_ENV, "{}"))
        seen["cur"] = experimente.current()
        return {"output_dir": str(tmp_path), "videos": {}, "kind": "ranking"}

    monkeypatch.setattr(job, "_ranking", fake_ranking)
    order = job.parse_order({"id": "abcd1234", "art": "ranking", "thema": "die höchsten Berge", "maskottchen": False,
                             "vorlieben": {"gut": ["x"], "varianten_gut": [{"format": "zahl"}]}}, set())
    job.run_order(order, tmp_path / "f")
    assert "varianten_gut" not in seen["prefs"] and seen["prefs"]["gut"] == ["x"]
    assert seen["variants"] == {"gut": [{"format": "zahl"}]}
    assert seen["cur"]["maskottchen"] == "aus" and seen["cur"]["_grund"]["maskottchen"] == "wunsch"
    assert "musik" in seen["cur"]                       # auftragsweite Stellschraube wurde gewählt und erfasst


# --------------------------------------------------------------------------- Lern-Analyst

def eintrag(i, ziel, views, fmt, tage=5, likes=0):
    return {"ziel": ziel, "video_id": f"v{i}", "auftrag": f"a{i}", "views": views, "likes": likes, "comments": 0,
            "varianten": {"format": fmt, "design": "neon"}, "alter_tage": tage, "punkte": views + 25 * likes}


def test_zu_wenig_daten_bleibt_erkundung():
    assert lernen.reason(5, 5, [], [])[0] == "erkundung"


def test_gewichte_und_gewinner_nur_mit_genug_videos():
    rows = [eintrag(i, "youtube", 5000, "zahl") for i in range(5)] + [eintrag(10 + i, "youtube", 100, "karte") for i in range(5)]
    gew = lernen.weights(lernen.classify(rows))
    assert gew["format"]["zahl"]["gut"] == 5 and gew["format"]["karte"]["schlecht"] == 5
    win = lernen.winners(gew)
    assert [(w["stellschraube"], w["variante"]) for w in win] == [("format", "zahl")]
    assert lernen.winners(lernen.weights(lernen.classify(rows[:3] + rows[5:8]))) == []      # je Variante < 4 Videos


def test_run_ohne_uploads_ehrlich(umgebung):
    data = lernen.run()
    assert data["modus"] == "erkundung" and data["gewichte"] == {} and data["gewinner"] == []
    assert any("Noch keine Uploads" in h for h in data["hinweise"])


def test_run_mit_gemockten_zahlen_schreibt_gewichte_die_der_bandit_liest(umgebung, monkeypatch):
    old = common.iso(common.now() - timedelta(days=6))
    rows = [{"ziel": "youtube", "video_id": f"v{i}", "auftrag": f"a{i}", "hochgeladen": old,
             "varianten": {"format": "zahl" if i < 6 else "karte"}} for i in range(12)]
    common.write_json("uploads.json", {"eintraege": rows})
    from cudi_video.upload import youtube
    monkeypatch.setattr(youtube, "video_stats", lambda ids: (
        {i: {"views": 9000 if int(i[1:]) < 6 else 100, "likes": 50, "comments": 2} for i in ids}, []))
    data = lernen.run()
    assert data["modus"] == "lernend" and data["gewinner"][0]["variante"] == "zahl"
    assert experimente.counts("format", "zahl")[0] >= 6                       # Bandit liest lernen.json
    assert experimente.counts("format", "karte")[1] >= 6


def test_youtube_ohne_lese_scope_gibt_klaren_hinweis(monkeypatch):
    from cudi_video.upload import youtube

    class Resp:
        status_code = 403

        def json(self):
            return {}

    monkeypatch.setenv("CUDI_YT_CLIENT_ID", "id")
    monkeypatch.setenv("CUDI_YT_CLIENT_SECRET", "geheim-geheim")
    monkeypatch.delenv("CUDI_YT_API_KEY", raising=False)
    monkeypatch.setattr(youtube, "access_token", lambda: "tok-123456")
    monkeypatch.setattr(youtube, "http", lambda *a, **k: Resp())
    stats, notes = youtube.video_stats(["a", "b"])
    assert stats == {} and any("youtube.readonly" in n for n in notes)


def test_tiktok_ohne_scope_hinweis(monkeypatch):
    from cudi_video.upload import UploadError, tiktok

    class Resp:
        status_code = 403
        text = ""

    monkeypatch.setattr(tiktok, "access_token", lambda: "t")
    monkeypatch.setattr(tiktok, "http", lambda *a, **k: Resp())
    with pytest.raises(UploadError, match="video.list"):
        tiktok.video_list()


def test_uploads_liste_zusammenfuehren_ohne_doppelte(umgebung, tmp_path):
    new = [{"ziel": "youtube", "video_id": "abc", "auftrag": "a1", "varianten": {"format": "zahl"}},
           {"ziel": "tiktok", "publish_id": "p1", "auftrag": "a1"}, {"ziel": "mail", "auftrag": "x"}]
    f = tmp_path / "neu.json"
    f.write_text(json.dumps(new), "utf-8")
    assert lernen.merge_uploads(f) == 2 and lernen.merge_uploads(f) == 0
    assert len(common.read_json("uploads.json")["eintraege"]) == 2


def test_upload_records_nur_erfolgreiche_mit_varianten():
    order = {"id": "abcd1234", "art": "ranking"}
    data = {"varianten": {"format": "zahl", "_grund": {"format": "bandit"}},
            "videos": [{"key": "de", "youtube": "Titel\nText", "tiktok": "Kurz"}],
            "hochgeladen": [{"ziel": "youtube", "sprache": "de", "ok": True, "id": "yt1", "url": "u"},
                            {"ziel": "tiktok", "sprache": "de", "ok": False}]}
    recs = job.upload_records(order, data)
    assert len(recs) == 1 and recs[0]["video_id"] == "yt1" and recs[0]["varianten"] == {"format": "zahl"}
    assert recs[0]["text"] == "Titel"


def test_workflows_yaml():
    wf = yaml.safe_load((ROOT / ".github/workflows/notbetrieb.yml").read_text("utf-8"))
    liste = wf["jobs"]["liste"]
    assert liste["permissions"]["contents"] == "write" and liste["needs"] == "render"
    assert any("firma_commit.sh" in s.get("run", "") for s in liste["steps"])
    assert any("cudi_video.firma uploads" in s.get("run", "") for s in liste["steps"])
    assert wf["permissions"]["contents"] == "read"
    wf2 = yaml.safe_load((ROOT / ".github/workflows/firma-lernen.yml").read_text("utf-8"))
    assert wf2["jobs"]["lernen"]["steps"][-1]["run"].startswith("bash scripts/firma_commit.sh")


# --------------------------------------------------------------------------- Reportage

BASIS = {"id": "rep00001", "art": "reportage", "thema": "Der Mondlandung-Jahrestag 1969"}


def test_reportage_auftrag_validierung():
    ok = job.parse_order({**BASIS, "links": ["https://www.nasa.gov/a"], "sprache": "en"}, set())
    assert ok["art"] == "reportage" and ok["sprache"] == "en" and ok["links"] == ["https://www.nasa.gov/a"]
    for bad, msg in (({"thema": "kurz"}, "Thema"), ({"sprache": "fr"}, "Sprache"), ({"links": ["ftp://x.de/a"]}, "Link"),
                     ({"links": ["http://localhost/a"]}, "lokale"), ({"links": ["https://a.de/x"] * 6}, "höchstens 5"),
                     ({"schritt": "bearbeiten"}, "Schritt")):
        with pytest.raises(job.OrderError, match=msg):
            job.parse_order({**BASIS, **bad}, set())
    assert job.parse_order({**BASIS, "schritt": "hochladen", "hochladen": {"ziel": "youtube"}}, set())["schritt"] == "hochladen"


def quellen():
    return [
        {"id": "Q1", "name": "Wikipedia", "titel": "Apollo 11", "link": "https://de.wikipedia.org/wiki/Apollo_11",
         "betreiber": "wikipedia", "art": "wikipedia",
         "text": "Apollo 11 war die erste bemannte Mondlandung. Die Landefähre setzte am 20. Juli 1969 auf dem Mond auf."},
        {"id": "Q2", "name": "NASA", "titel": "Apollo 11 Mission", "link": "https://www.nasa.gov/apollo11", "betreiber": "nasa",
         "art": "seite", "text": "Am 20. Juli 1969 landeten die Astronauten Neil Armstrong und Buzz Aldrin mit Apollo 11 auf dem Mond."},
        {"id": "Q3", "name": "Tagesschau", "titel": "Mondlandung vor Jahren", "link": "https://tagesschau.de/x",
         "betreiber": "tagesschau", "art": "news", "text": "Die Mondlandung von Apollo 11 gilt als Meilenstein der Raumfahrt. Am 20. Juli 1969 setzte die Landefähre "
         "von Apollo 11 auf dem Mond auf. Apollo 11 war die erste bemannte Mondlandung der Geschichte."},
    ]


def satz(text, *belege):
    return {"text": text, "belege": [{"quelle": q, "zitat": z} for q, z in belege]}


Z1 = ("Q1", "setzte am 20. Juli 1969 auf dem Mond auf")
Z2 = ("Q2", "Am 20. Juli 1969 landeten die Astronauten Neil Armstrong und Buzz Aldrin mit Apollo 11 auf dem Mond")
GUT = satz("Am 20. Juli 1969 landete die Landefähre von Apollo 11 auf dem Mond.", Z1, Z2)


def test_pruefung_akzeptiert_nur_woertliche_belege_aus_zwei_betreibern():
    q = {x["id"]: x for x in quellen()}
    ok, _ = reportage.pruefe_satz(GUT, q, "de")
    assert ok and {b["name"] for b in ok["belege"]} == {"Wikipedia", "NASA"}
    faelle = [
        (satz("Apollo 11 landete.", Z1), "nur 1"),
        (satz("Apollo 11 landete.", ("Q1", "erfundene Textstelle ohne Quelle"), Z2), "nur 1"),
        (satz("Die Landung kostete 25 Milliarden Dollar.", Z1, Z2), "Zahl ohne Beleg"),
        (satz("Die Landung war eine Sensation.", Z1, Z2), "reißerisches"),
        (satz("Das war vermutlich 1969.", Z1, Z2), "Spekulation"),
        (satz("Michael landete 1969.", Z1, Z2), "Name"),
        (satz("Die Landung war unglaublich.", Z1, Z2), "Clickbait"),
        (satz("Apollo 11 landete.", Z1, ("Q1", "erste bemannte Mondlandung")), "nur 1"),
    ]
    for item, why in faelle:
        bad, grund = reportage.pruefe_satz(item, q, "de")
        assert bad is None and why in grund, (item["text"], grund)


def test_regelweg_nimmt_nur_von_zwei_quellen_gestuetzte_saetze():
    saetze = reportage.regel_saetze(quellen())
    assert any("20. Juli 1969" in s["text"] for s in saetze)
    assert all(len({b["quelle"] for b in s["belege"]}) == 2 for s in saetze)
    ok, rej, _ = reportage.pruefe_antwort({"saetze": saetze}, quellen(), "de")
    assert ok


def run_reportage(tmp_path, monkeypatch, answer, srcs=None):
    rendered = {}
    monkeypatch.setattr(reportage, "sammle", lambda t, l, lang: (srcs if srcs is not None else quellen(), []))
    monkeypatch.setattr(handoff, "request", lambda task, instr, data: answer)

    def fake_render(script, out_dir, progress=None, musik=True):
        rendered.update(script=script, musik=musik)
        (out_dir / "reportage.mp4").write_bytes(b"x")
        (out_dir / "reportage_cover.jpg").write_bytes(b"x")
        return {"video": "reportage.mp4", "cover": "reportage_cover.jpg", "duration": 40.0, "qa": None}

    monkeypatch.setattr("cudi_video.erklaer.render_erklaerung", fake_render)
    order = job.parse_order(BASIS, set())
    return reportage.run(order, tmp_path / "f", lambda s, f: None), rendered


def test_reportage_pipeline_mit_schreibaufgabe_prueft_streng(tmp_path, monkeypatch):
    answer = {"titel": "Apollo 11: Die erste Mondlandung",
              "saetze": [GUT,
                         satz("Apollo 11 war die erste bemannte Mondlandung.", ("Q1", "erste bemannte Mondlandung"),
                              ("Q3", "Die Mondlandung von Apollo 11")),
                         satz("Die Mission gilt als Meilenstein der Raumfahrt.", ("Q3", "gilt als Meilenstein der Raumfahrt"),
                              ("Q2", "Astronauten Neil Armstrong und Buzz Aldrin")),
                         satz("Die Landung kostete 25 Milliarden Dollar.", ("Q1", "erste bemannte Mondlandung"), Z2)]}
    result, rendered = run_reportage(tmp_path, monkeypatch, answer)
    assert rendered["musik"] is False                                    # keine Musik
    texte = [sz["text"] for sz in rendered["script"]["szenen"]]
    assert len(texte) == 3 + 2 and not any("Milliarden" in t for t in texte)     # erfundene Zahl fliegt raus
    assert "Quellen:" in texte[-1] and "Stand:" in texte[-1] and "Wikipedia" in texte[-1]
    out = Path(result["output_dir"])
    review = (out / "review.md").read_text("utf-8")
    assert "Zahl ohne Beleg" in review and "Endabnahme: bestanden" in review
    assert "https://www.nasa.gov/apollo11" in (out / "youtube.txt").read_text("utf-8")
    assert result["videos"]["de"]["abnahme"]["ok"] and result["kind"] == "reportage"


def test_reportage_ohne_antwort_nutzt_regelweg_und_bricht_ehrlich_ab(tmp_path, monkeypatch):
    result, _ = run_reportage(tmp_path, monkeypatch, None)
    assert "Regelweg" in (Path(result["output_dir"]) / "review.md").read_text("utf-8")
    with pytest.raises(reportage.ReportageError, match="zwei unabhängige Quellen") as exc:
        run_reportage(tmp_path / "zwei", monkeypatch, None, [quellen()[0]])
    assert exc.value.wiederholbar is False
    unrelated = [quellen()[0], {**quellen()[1], "text": "Ein ganz anderer Text über Gartenarbeit im Frühling und Gemüse."}]
    with pytest.raises(reportage.ReportageError, match="bestätigt"):
        run_reportage(tmp_path / "drei", monkeypatch, {"saetze": []}, unrelated)


def test_reportage_titel_ohne_clickbait_und_zahlen():
    s = [{"text": "Am 20. Juli 1969 landete es.", "belege": []}]
    assert reportage.waehle_titel("Unglaublich: Du wirst es nicht glauben", "Mondlandung 1969", s) == "Mondlandung 1969"
    assert reportage.waehle_titel("Die Mondlandung 1969", "xxxxx", s) == "Die Mondlandung 1969"
    assert reportage.waehle_titel("Die 7 Wunder", "Mondlandung", s) == "Mondlandung"


def test_ideen_reportage_hat_startbaren_auftrag():
    order = ideen.build_order("reportage", {"thema": "Sachliche Reportage: Erdbeben in Japan"}, {})
    assert order == {"art": "reportage", "thema": "Erdbeben in Japan", "sprache": "de"}
    assert ideen.validate_order(order, {}) == ""
