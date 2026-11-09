"""Clip-Kern: Erlaubnis, Auswahl mit Bildschnitten, Inhaltsurteil, Kalibrierung, Stil „vollbild“, Twitch-Ranking,
Instagram – alles ohne Netz."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cudi_video import config
from cudi_video.clip import ClipError, erlaubnis, highlights, kalibrierung, source, transcribe, twitch, urteil, vollbild
from cudi_video.clip.highlights import Fenster, Satz

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")


@pytest.fixture(autouse=True)
def daten(tmp_path, monkeypatch):
    d = tmp_path / "firma_daten"
    d.mkdir()
    monkeypatch.setenv("CUDI_FIRMA_DATEN", str(d))
    monkeypatch.setattr(erlaubnis, "meta_holen", lambda url: {})
    return d


def _erlaubnis(daten, creators):
    (daten / "clip_erlaubnis.json").write_text(json.dumps({"erzeugt": "2026-11-01", "creators": creators}), "utf-8")


BELEG = {"url": "https://example.org/regeln", "zitat": "Clips sind ausdrücklich erlaubt.", "datum": "2026-11-01",
         "art": "beschreibung"}


# ------------------------------------------------------------------ Erlaubnis

def test_kanal_aus_url():
    assert erlaubnis.kanal_aus_url("https://www.twitch.tv/BeispielKanal/clips") == [("twitch", "beispielkanal")]
    assert erlaubnis.kanal_aus_url("https://www.youtube.com/@Beispiel") == [("youtube", "beispiel")]
    assert erlaubnis.kanal_aus_url("https://www.youtube.com/channel/UCabc123") == [("youtube", "ucabc123")]
    assert erlaubnis.kanal_aus_url("https://www.tiktok.com/@jemand/video/1") == [("tiktok", "jemand")]
    assert erlaubnis.kanal_aus_url("https://www.youtube.com/watch?v=abc") == []


def test_erlaubt_nur_mit_beleg(daten):
    _erlaubnis(daten, [{"name": "A", "kanaele": {"twitch": ["kanala"]}, "status": "erlaubt", "belege": [BELEG]},
                       {"name": "B", "kanaele": {"twitch": ["kanalb"]}, "status": "erlaubt", "belege": []}])
    r = erlaubnis.pruefe("https://www.twitch.tv/kanala")
    assert r["erlaubt"] is True and r["status"] == "erlaubt" and r["belege"][0]["url"] == BELEG["url"]
    b = erlaubnis.pruefe("https://www.twitch.tv/kanalb")
    assert b["erlaubt"] is False and b["status"] == "unklar" and "ohne wörtlichen Beleg" in b["grund"]


def test_sperre_geht_vor(daten):
    _erlaubnis(daten, [{"name": "A", "kanaele": {"youtube": ["ucabc"]}, "status": "erlaubt", "belege": [BELEG]}])
    (daten / "clip_creators.json").write_text(json.dumps(
        {"creators": [{"name": "A", "youtube": ["UCabc"], "gesperrt": True}]}), "utf-8")
    r = erlaubnis.pruefe("https://www.youtube.com/channel/UCabc")
    assert r["status"] == "gesperrt" and not r["erlaubt"] and "Sperrliste" in r["grund"]
    with pytest.raises(ClipError, match="abgebrochen"):
        erlaubnis.pruefe_auftrag("https://www.youtube.com/channel/UCabc", True)       # auch mit Bestätigung


def test_gesperrt_laut_scout_und_meta(daten):
    _erlaubnis(daten, [{"name": "C", "kanaele": {"youtube": ["UCxyz"]}, "status": "gesperrt",
                        "belege": [{**BELEG, "zitat": "Keine Clips ohne Anfrage."}]}])
    meta = {"extractor_key": "Youtube", "channel_id": "UCxyz", "uploader_id": "@c"}
    r = erlaubnis.pruefe("https://www.youtube.com/watch?v=1", meta)
    assert r["status"] == "gesperrt" and "Keine Clips ohne Anfrage" in r["grund"]


def test_unklar_nur_mit_bestaetigung(daten):
    url = "https://www.twitch.tv/unbekannt"
    r = erlaubnis.pruefe(url)
    assert r["status"] == "unklar" and not r["erlaubt"]
    with pytest.raises(ClipError, match="bestaetigt_erlaubnis"):
        erlaubnis.pruefe_auftrag(url, False)
    ok = erlaubnis.pruefe_auftrag(url, True)
    assert "UNKLAR" in ok["vermerk"]
    ohne_kanal = erlaubnis.pruefe("https://example.org/watch?v=1")
    assert ohne_kanal["status"] == "unklar" and "konnte nicht bestimmt" in ohne_kanal["grund"]


# ------------------------------------------------------------------ Auswahl

def _saetze(n=40, dauer=4.0, text="Das ist ein Satz."):
    out = []
    for i in range(n):
        s = Satz(i * 3, i * 3 + 2, i * dauer, i * dauer + dauer - 0.2, f"{text} {i}.", wert=1.0)
        out.append(s)
    return out


def test_fenster_beginnt_an_der_szene_und_kreuzt_keine():
    sa = _saetze(60)
    # Hook-Satz mitten im Video; ohne Schnitte wird er wegen des Einstiegs bevorzugt
    sa[20].hook_wert = 6.0
    ohne = highlights.fenster_finden(sa, 30, 60)
    assert abs(ohne.start - sa[20].start) < 0.01
    # Schnitte bei 90 s und 150 s: das Fenster liegt in EINER Episode und beginnt am Schnitt
    mit = highlights.fenster_finden(sa, 30, 60, schnitte=[90.0, 150.0])
    assert not any(mit.start + 1.5 < c < mit.ende - 1.0 for c in (90.0, 150.0))
    assert mit.signale["kreuzt_schnitt"] is False


def test_offenes_ende_wird_vermieden():
    assert highlights.offenes_ende("Und dann habe ich") is True
    assert highlights.offenes_ende("Das war alles.") is False
    assert highlights.offenes_ende("Wir sehen uns,") is True
    sa = _saetze(40)
    sa[29].text = "Und das war weil"          # Ende dort wäre offen
    sa[29].wert = 4.0
    f = highlights.fenster_finden(sa, 30, 120)
    assert f.saetze[-1] is not sa[29]


def test_titel_treffer_und_rueckbezug():
    assert highlights.titel_treffer("Der Mond ist weit entfernt", "Warum der Mond wirklich leuchtet") == 1
    assert highlights.rueckbezug_start("Und dann kam er") is True
    assert highlights.rueckbezug_start("Heute zeige ich dir") is False


def test_gewichte_aendern_die_rangliste():
    sa = _saetze(60)
    sa[10].hook_wert = 5.0
    sa[40].wert = 1.0
    basis = highlights.fenster_finden(sa, 30, 60)
    stark = highlights.fenster_finden(sa, 30, 60, gewichte={"einstieg": 1.5, "laenge": 0.5})
    assert isinstance(basis, Fenster) and isinstance(stark, Fenster)


# ------------------------------------------------------------------ Kalibrierung

def test_kalibrierung_erst_ab_20_je_seite(daten):
    zeilen = [{"urteil": "gut", "signale": {"einstieg": 6.0, "offen": 0.0}} for _ in range(19)]
    zeilen += [{"urteil": "schlecht", "signale": {"einstieg": 1.0, "offen": -3.0}} for _ in range(25)]
    doc = kalibrierung.schreibe(zeilen)
    assert doc["belastbar"] is False and kalibrierung.gewichte() == kalibrierung.STANDARD
    zeilen.append({"urteil": "gut", "signale": {"einstieg": 6.0, "offen": 0.0}})
    doc = kalibrierung.schreibe(zeilen)
    assert doc["belastbar"] is True
    g = kalibrierung.gewichte()
    assert g["einstieg"] > 1.0 and 0.5 <= g["offen"] <= 1.5


# ------------------------------------------------------------------ Inhaltsurteil

def test_titelpruefungen_aus_dem_clipper():
    text = "Wir haben 3000 Euro gespart und das Auto verkauft."
    assert urteil.erfindet_zahlen("5000 Euro gespart", text) is True
    assert urteil.erfindet_zahlen("3.000 Euro gespart", text) is False
    assert urteil.kopiert_titel("Warum der Mond leuchtet wirklich", "Warum der Mond wirklich leuchtet") is True
    assert urteil.unbelegt("Vermutlich in Berlin", text) is True
    assert urteil.unbelegt("Das Auto verkauft", text) is False
    assert urteil.unbelegt("Besuch in Paris", text) is True
    assert urteil.titel_pruefen("Das Auto verkauft", text, "Podcast 12") == []


def _fenster(texte, hook_wert=0.0):
    sa = [Satz(i, i, i * 5.0, i * 5.0 + 4.0, t, wert=1.0, hook_wert=hook_wert) for i, t in enumerate(texte)]
    return Fenster(sa[0].start, sa[-1].ende, 5.0, sa), sa


def test_regel_urteil():
    f, sa = _fenster(["Heute geht es um Autos.", "Wir haben eines verkauft.", "Das war die beste Entscheidung."], 4.0)
    u = urteil.regel_urteil(f, sa[0])
    assert u["quelle"] == "Regeln" and u["pointe"] and u["verstaendlich"] and urteil.angenommen(u)
    f2, sa2 = _fenster(["Und dann haben wir", "weil"])
    u2 = urteil.regel_urteil(f2, None)
    assert not urteil.angenommen(u2) and "Rückbezug" in u2["grund"] and "mitten im Gedanken" in u2["grund"]


def test_claude_urteil_prueft_den_titel(monkeypatch):
    from cudi_video import handoff

    f, sa = _fenster(["Heute geht es um Autos.", "Wir haben 3000 Euro gespart."], 4.0)
    words = [{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4}
             for i, w in enumerate("Heute geht es um Autos Wir haben 3000 Euro gespart".split())]
    monkeypatch.setattr(handoff, "active", lambda: True)
    antworten = {"punkte": 8, "pointe": True, "verstaendlich": True, "titel": "Warum 9000 Euro nicht reichen", "grund": "klar"}
    monkeypatch.setattr(handoff, "request", lambda *a, **k: antworten)
    u = urteil.urteilen(f, sa[0], words, {"titel": "Podcast Folge 3", "kanal": "Kanal"})
    assert u["quelle"] == "Claude" and u["punkte"] == 8 and u["titel"] == "" and u["befunde"]
    antworten["titel"] = "Wie spart man 3000 Euro"
    u = urteil.urteilen(f, sa[0], words, {"titel": "Podcast Folge 3", "kanal": "Kanal"})
    assert u["titel"] == "Wie spart man 3000 Euro" and not u["befunde"]
    monkeypatch.setattr(handoff, "request", lambda *a, **k: None)
    assert urteil.urteilen(f, sa[0], words)["quelle"] == "Regeln"


# ------------------------------------------------------------------ Vollbild-Bausteine

def test_vollbild_ass_titel_oben_woerter_unten():
    ws = [{"w": "Hallo", "s": 0.1, "e": 0.4}, {"w": "2024", "s": 0.5, "e": 0.9}, {"w": "Welt.", "s": 1.0, "e": 1.3}]
    ass, n = vollbild.ass_bauen(ws, "Ein sehr langer Titel " * 6, "DejaVu Sans", True, 2.0)
    assert n == 3 and "Style: Titel" in ass and "Style: Wort" in ass
    titel = [z for z in ass.splitlines() if ",Titel,," in z][0]
    assert len(vollbild.titel_text("Ein sehr langer Titel " * 6)) <= vollbild.TITEL_MAX + 1 and "…" in titel
    wort = [z for z in ass.splitlines() if z.startswith("Dialogue: 1")]
    assert len(wort) == 3 and "HALLO" in wort[0] and vollbild.GELB in wort[1]


# ------------------------------------------------------------------ Hilfen für Läufe

def _w(text, s, e):
    return {"w": text, "s": s, "e": e, "p": 0.9}


def _skript():
    teile = [("Heute", .5), ("reden", .4), ("wir", .3), ("über", .3), ("Nachrichten.", .6), (None, .9),
             ("Also", .3), ("ich", .2), ("lese", .3), ("jeden", .3), ("Morgen", .4), ("alles.", .5), (None, .5),
             ("Warum", .4), ("glaubst", .5), ("du", .3), ("das", .3), ("nicht", .5), ("überhaupt?", .7), (None, .4),
             ("Nein,", .4), ("nein,", .4), ("nein,", .4), ("das", .3), ("stimmt", .5), ("niemals!", .7), (None, .6),
             ("Ich", .2), ("habe", .3), ("2024", .6), ("Länder", .5), ("verglichen.", .8)]
    out, t = [], 0.5
    for text, d in teile:
        if text is None:
            t += d
            continue
        out.append(_w(text, round(t, 3), round(t + d * 0.85, 3)))
        t += d
    return out


def _video(pfad, w=320, h=240, dauer=20):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30:duration={dauer}",
                    "-f", "lavfi", "-i", f"sine=frequency=330:duration={dauer}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(pfad)], check=True)


def _auftrag(**kw):
    raw = {"id": "clipkern1", "art": "clip", "quelle": "https://www.youtube.com/@kanala/watch", "sprache": "de"}
    raw.update(kw)
    return raw


def _lauf_vorbereiten(tmp_path, monkeypatch):
    from cudi_video import job

    video = tmp_path / "quelle.mp4"
    _video(video, 320, 240, 20)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    monkeypatch.setattr(transcribe, "erkenne", lambda audio, sprache: [dict(x) for x in _skript()])
    monkeypatch.setattr(source, "beschaffen", lambda q, a: video)
    monkeypatch.setattr(source, "metadaten", lambda a: {"titel": "Test-Podcast", "kanal": "Kanal A", "url": "", "lizenz": ""})
    monkeypatch.delenv("CUDI_SCHREIBEN", raising=False)
    return job


# ------------------------------------------------------------------ App-Auftrag clip: erlaubt / gesperrt / unklar

def test_auftrag_parse_ohne_bestaetigung_und_stil():
    from cudi_video import job

    o = job.parse_order(_auftrag(), set())
    assert o["bestaetigt_erlaubnis"] is False and o["clip_stil"] == "vollbild"
    assert job.parse_order(_auftrag(clip_stil="zuschnitt"), set())["clip_stil"] == "zuschnitt"
    with pytest.raises(job.OrderError, match="Stil"):
        job.parse_order(_auftrag(clip_stil="kino"), set())
    t = job.parse_order({"id": "tw10", "art": "clip", "twitch_kanal": "@BeispielKanal", "zeitraum": "30d"}, set())
    assert t["twitch_kanal"] == "beispielkanal" and t["zeitraum"] == "30d" and t["quelle"] == ""
    for bad, teil in [({"twitch_kanal": "a b"}, "Twitch"), ({"twitch_kanal": "abcd", "zeitraum": "1y"}, "Zeitraum")]:
        with pytest.raises(job.OrderError, match=teil):
            job.parse_order({"id": "tw20", "art": "clip", **bad}, set())


def test_auftrag_gesperrt_bricht_ab(tmp_path, monkeypatch, daten):
    job = _lauf_vorbereiten(tmp_path, monkeypatch)
    (daten / "clip_creators.json").write_text(json.dumps({"creators": [{"name": "A", "youtube": ["kanala"], "gesperrt": True}]}), "utf-8")
    code, data = job.run_order(job.parse_order(_auftrag(bestaetigt_erlaubnis=True), set()), tmp_path / "a")
    assert code == 1 and not data["ok"] and "Sperrliste" in data["fehler"] and data["wiederholbar"] is False


def test_auftrag_unklar_ohne_bestaetigung_bricht_ab(tmp_path, monkeypatch):
    job = _lauf_vorbereiten(tmp_path, monkeypatch)
    code, data = job.run_order(job.parse_order(_auftrag(), set()), tmp_path / "a")
    assert code == 1 and not data["ok"] and "bestaetigt_erlaubnis" in data["fehler"]


@needs_ffmpeg
def test_auftrag_unklar_mit_bestaetigung_laeuft_mit_vermerk(tmp_path, monkeypatch):
    job = _lauf_vorbereiten(tmp_path, monkeypatch)
    code, data = job.run_order(job.parse_order(_auftrag(bestaetigt_erlaubnis=True), set()), tmp_path / "a")
    assert code == 0 and data["ok"]
    assert "Erlaubnis UNKLAR" in data["pruefbericht"] and "Stil: vollbild" in data["pruefbericht"]
    assert "Inhaltsurteil (Regeln)" in data["pruefbericht"]


@needs_ffmpeg
def test_auftrag_erlaubt_laeuft_ohne_bestaetigung_und_zeigt_beleg(tmp_path, monkeypatch, daten):
    job = _lauf_vorbereiten(tmp_path, monkeypatch)
    _erlaubnis(daten, [{"name": "Kanal A", "kanaele": {"youtube": ["@kanala"]}, "status": "erlaubt", "belege": [BELEG],
                        "monetarisierung": "ja", "bedingungen": ["Quelle nennen"]}])
    code, data = job.run_order(job.parse_order(_auftrag(), set()), tmp_path / "a")
    assert code == 0 and data["ok"]
    b = data["pruefbericht"]
    assert "Erlaubnis geprüft" in b and BELEG["zitat"] in b and BELEG["url"] in b and "Quelle nennen" in b
    v = data["videos"][0]
    assert v["dauer"] <= 179 and Path(v["video"]).exists()


@needs_ffmpeg
def test_stil_zuschnitt_funktioniert_weiter(tmp_path, monkeypatch, daten):
    job = _lauf_vorbereiten(tmp_path, monkeypatch)
    code, data = job.run_order(job.parse_order(_auftrag(bestaetigt_erlaubnis=True, clip_stil="zuschnitt"), set()), tmp_path / "a")
    assert code == 0 and "Stil: zuschnitt" in data["pruefbericht"]


# ------------------------------------------------------------------ Twitch-Ranking

def _twitch_fake(monkeypatch, tmp_path, n=5, dauer=14):
    video = tmp_path / "twitch.mp4"
    _video(video, 320, 240, dauer)
    eintraege = [{"id": f"Clip{i}", "title": f"Moment {i}", "view_count": 1000 - i * 100, "duration": dauer,
                  "timestamp": 1_700_000_000 + i * 1000, "url": f"https://clips.twitch.tv/Clip{i}"} for i in range(n)]
    eintraege.append({**eintraege[0], "id": "Doppelt", "view_count": 5, "timestamp": 1_700_000_030, "url": "https://clips.twitch.tv/Doppelt"})
    monkeypatch.setattr(twitch, "_liste_holen", lambda login, zeitraum, limit: {"entries": eintraege})

    def laden(url, ordner):
        ordner.mkdir(parents=True, exist_ok=True)
        ziel = ordner / "clip.mp4"
        shutil.copy(video, ziel)
        return ziel

    monkeypatch.setattr(twitch, "_herunterladen", laden)
    monkeypatch.setattr(transcribe, "erkenne", lambda audio, sprache: [dict(x) for x in _skript()[:12]])


def test_twitch_hilfen():
    clips = [{"id": "a", "zeit": 1000, "aufrufe": 9}, {"id": "b", "zeit": 1050, "aufrufe": 8}, {"id": "c", "zeit": 5000, "aufrufe": 7}]
    assert [c["id"] for c in twitch.unterschiedlich(clips)] == ["a", "c"]
    teile = [{"dauer": 20.0}] * 4
    assert len(twitch.teile_waehlen(teile)) == 4                        # 80 s >= 65 s
    assert twitch.teile_waehlen([{"dauer": 10.0}] * 3) == []             # zu kurz für TikTok


@needs_ffmpeg
def test_twitch_ranking_countdown_mit_erlaubnis(tmp_path, monkeypatch, daten):
    _twitch_fake(monkeypatch, tmp_path)
    monkeypatch.setattr(twitch, "MIN_TOTAL", 12.0)
    _erlaubnis(daten, [{"name": "Beispiel", "kanaele": {"twitch": ["beispielkanal"]}, "status": "erlaubt", "belege": [BELEG]}])
    info = twitch.ranking("beispielkanal", "7d", "de", tmp_path / "aus", tmp_path / "arbeit")
    assert Path(info["datei"]).exists() and 12 <= info["dauer"] <= 175
    plaetze = [t["platz"] for t in info["teile"]]
    assert plaetze == sorted(plaetze) and plaetze[0] == 1 and len(plaetze) >= 3
    assert info["teile"][0]["aufrufe"] >= info["teile"][-1]["aufrufe"]                 # Platz 1 = meistgesehen
    assert all("Doppelt" not in t["url"] for t in info["teile"])                        # gleicher Moment nur einmal
    from cudi_video.clip import texte

    v = texte.schreibe_ranking(tmp_path / "aus", info)
    assert v["clip"]["video"] == "clip.mp4"
    bericht = (tmp_path / "aus" / "review.md").read_text("utf-8")
    assert "Erlaubnis geprüft" in bericht and "Aufrufe laut Twitch" in bericht and BELEG["url"] in bericht
    assert "https://clips.twitch.tv/Clip0" in (tmp_path / "aus" / "youtube.txt").read_text("utf-8")


def test_twitch_ranking_gesperrt_und_unklar(tmp_path, monkeypatch, daten):
    _twitch_fake(monkeypatch, tmp_path)
    (daten / "clip_creators.json").write_text(json.dumps({"creators": [{"name": "X", "twitch": ["gesperrtkanal"], "gesperrt": True}]}), "utf-8")
    with pytest.raises(ClipError, match="Sperrliste"):
        twitch.ranking("gesperrtkanal", "7d", "de", tmp_path / "a", tmp_path / "w")
    with pytest.raises(ClipError, match="bestaetigt_erlaubnis"):
        twitch.ranking("unbekanntkanal", "7d", "de", tmp_path / "a", tmp_path / "w")
    with pytest.raises(ClipError, match="Anmeldename"):
        twitch.ranking("a b", "7d", "de", tmp_path / "a", tmp_path / "w", True)


def test_twitch_zu_wenige_clips(tmp_path, monkeypatch):
    monkeypatch.setattr(twitch, "_liste_holen", lambda *a: {"entries": []})
    with pytest.raises(ClipError, match="zu wenige"):
        twitch.ranking("beispielkanal", "7d", "de", tmp_path / "a", tmp_path / "w", True)


@needs_ffmpeg
def test_twitch_auftrag_ueber_job(tmp_path, monkeypatch, daten):
    from cudi_video import job

    _twitch_fake(monkeypatch, tmp_path)
    monkeypatch.setattr(twitch, "MIN_TOTAL", 12.0)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    order = job.parse_order({"id": "tw90", "art": "clip", "twitch_kanal": "beispielkanal", "bestaetigt_erlaubnis": True}, set())
    code, data = job.run_order(order, tmp_path / "auftrag")
    assert code == 0 and data["ok"] and "Erlaubnis UNKLAR" in data["pruefbericht"]


# ------------------------------------------------------------------ Instagram

class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body, self.text = status, body or {}, json.dumps(body or {})
        self.headers = {}

    def json(self):
        return self._body


def test_instagram_upload_ablauf_und_geheimnisse(tmp_path, monkeypatch):
    from cudi_video import upload
    from cudi_video.upload import Material, instagram

    token = "EAAGeheimerToken12345"
    monkeypatch.setenv("CUDI_IG_USER_ID", "1784000")
    monkeypatch.setenv("CUDI_IG_ACCESS_TOKEN", token)
    monkeypatch.setattr(instagram, "POLL_EVERY", 0.0)
    monkeypatch.setattr(upload, "PAUSE", 0.0)
    v = tmp_path / "r.mp4"
    v.write_bytes(b"x" * 100)
    antworten = [_Resp(200, {"id": "C1", "uri": "https://rupload.facebook.com/ig-api-upload/v25.0/C1"}),
                 _Resp(200, {"success": True}), _Resp(200, {"status_code": "IN_PROGRESS"}),
                 _Resp(200, {"status_code": "FINISHED"}), _Resp(200, {"id": "M99"})]
    gesehen = []

    def http(method, url, **kw):
        gesehen.append((method, url, kw))
        return antworten.pop(0)

    monkeypatch.setattr(instagram, "http", http)
    m = Material(video=v, title="Titel", caption="Text " + " ".join(f"#t{i}" for i in range(40)))
    r = instagram.upload(m, "oeffentlich")
    assert r["id"] == "M99" and not antworten
    assert gesehen[0][2]["data"]["media_type"] == "REELS" and gesehen[1][2]["headers"]["file_size"] == "100"
    assert gesehen[0][2]["data"]["caption"].count("#") == instagram.HASHTAGS_MAX
    assert token not in json.dumps(r) and token not in json.dumps(instagram.plan(m))
    assert token not in upload.redact(f"fehler access_token={token} OAuth {token}")
    assert upload.redact(f"x {token} y") == "x *** y"


def test_instagram_fehler_geschwaerzt_und_nie_versehentlich_oeffentlich(tmp_path, monkeypatch):
    from cudi_video import upload
    from cudi_video.upload import Material, UploadError, instagram

    token = "EAAGeheimerToken12345"
    monkeypatch.setenv("CUDI_IG_USER_ID", "1784000")
    monkeypatch.setenv("CUDI_IG_ACCESS_TOKEN", token)
    monkeypatch.setattr(upload, "PAUSE", 0.0)
    v = tmp_path / "r.mp4"
    v.write_bytes(b"x")
    with pytest.raises(UploadError, match="kein privat"):
        instagram.upload(Material(video=v, title="t"), "privat")
    monkeypatch.setattr(instagram, "http", lambda *a, **k: _Resp(400, {"error": {"message": f"bad token {token}"}}))
    with pytest.raises(UploadError) as e:
        instagram.upload(Material(video=v, title="t"), "oeffentlich")
    assert token not in str(e.value)
    monkeypatch.delenv("CUDI_IG_ACCESS_TOKEN")
    with pytest.raises(UploadError, match="CUDI_IG_ACCESS_TOKEN"):
        instagram.upload(Material(video=v, title="t"), "oeffentlich")


def test_hochladen_ziel_instagram_im_auftrag(tmp_path, monkeypatch):
    from cudi_video import job
    from cudi_video.upload import cli

    assert job._upload_wish("instagram") == {"ziel": "instagram", "sichtbarkeit": "privat"}
    assert job._upload_wish({"ziel": "alle", "sichtbarkeit": "oeffentlich"})["ziel"] == "alle"
    assert cli._targets("alle") == ["youtube", "tiktok", "instagram"] and cli._targets("beide") == ["youtube", "tiktok"]
    v = tmp_path / "a.mp4"
    v.write_bytes(b"x")
    monkeypatch.setenv("CUDI_IG_ACCESS_TOKEN", "EAAGeheimerToken12345")
    r = cli.upload_order({"ziel": "instagram", "sichtbarkeit": "privat"}, {"videos": [{"video": str(v), "key": "de"}]})
    assert r[0]["ok"] is False and "EAAGeheimer" not in json.dumps(r) and "privat" in r[0]["fehler"]
