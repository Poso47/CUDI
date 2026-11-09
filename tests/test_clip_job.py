"""Clip-Engine im Auftragsfluss (job.py): Prüfung, Lauf mit Schreibaufgabe „clip_hook“, Texte, Fehler; plus Feinheiten."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from cudi_video import config
from cudi_video.clip import ClipError, erlaubnis, reframe, source, subtitles, transcribe

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")


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


@pytest.fixture(autouse=True)
def _erlaubnis_ohne_netz(tmp_path, monkeypatch):
    monkeypatch.setenv("CUDI_FIRMA_DATEN", str(tmp_path / "firma_daten"))
    monkeypatch.setattr(erlaubnis, "meta_holen", lambda url: {})


def _auftrag(**kw):
    raw = {"id": "clip1234", "art": "clip", "quelle": "https://example.org/watch?v=abc", "bestaetigt_erlaubnis": True}
    raw.update(kw)
    return raw


def test_tausenderzahlen_bleiben_ganz():
    ws = [_w("were", 0, .3), _w("200", .3, .6), _w(",000", .6, .9), _w("euros", .9, 1.2), _w("and", 1.2, 1.4),
          _w("100,", 1.4, 1.7), _w("000", 1.7, 2.0)]
    ws = transcribe.zahlen_zusammenfuehren(ws)
    assert [w["w"] for w in ws] == ["were", "200,000", "euros", "and", "100,000"]
    assert (ws[1]["s"], ws[1]["e"]) == (.3, .9)
    ass, _n = subtitles.ass_bauen(ws, "en", "Anton", False, 3.0)
    assert "200,000" in ass and ">000" not in ass and " 000 " not in ass


def test_augenlinie_nie_unter_45_prozent():
    # Gesicht sehr tief im Bild: der Zoom wird zurückgenommen, damit die Augenlinie nicht unter ~45 % rutscht
    pos = np.full((1, 12, 3), np.nan)
    pos[0, :] = (180.0, 190.0, 70.0)
    an = reframe.Analyse(360, 240, 0.0, pos, np.zeros(12, dtype=int), 1)
    _x, y, _w_, h = reframe.zuschnitt(an, 0, 0, 2, reframe.ZOOM_NAH)
    augen = 190.0 - 0.12 * 70.0
    assert (augen - y) / h <= 0.48 or h >= 238            # bei Zoom 1.0 ist nichts mehr zu verschieben
    # ein einzelner Ausreißer wird geglättet
    p2 = np.full((1, 9, 3), 100.0)
    p2[0, 4] = (100.0, 400.0, 100.0)
    assert reframe._glaetten(p2)[0, 4, 1] == 100.0


def test_clip_auftrag_pruefung():
    from cudi_video import job

    ok = job.parse_order(_auftrag(start="1:30", ende=150, sprache="en", laenge="60"), set())
    assert (ok["start"], ok["ende"], ok["sprache"], ok["laenge"], ok["art"]) == (90.0, 150.0, "en", 60, "clip")
    assert job.parse_order(_auftrag(), set())["start"] is None
    for bad, teil in [({"quelle": ""}, "Link"), ({"quelle": "ftp://example.org/x"}, "Link"),
                      ({"quelle": "http://localhost/x.mp4"}, "lokale"), ({"quelle": "http://192.168.1.5/x"}, "lokale"),
                      ({"start": 50, "ende": 20}, "Ende"), ({"start": 0, "ende": 400}, "175"),
                      ({"sprache": "fr"}, "Sprache"), ({"laenge": 5}, "Länge"), ({"start": "abc"}, "Start")]:
        with pytest.raises(job.OrderError, match=teil):
            job.parse_order(_auftrag(**bad), set())


@needs_ffmpeg
def test_clip_auftrag_lauf_schreiben_und_weiter(tmp_path, monkeypatch):
    from cudi_video import handoff, job

    video = tmp_path / "quelle.mp4"
    _video(video, 320, 240, 20)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(transcribe, "erkenne", lambda audio, sprache: [dict(x) for x in _skript()])
    monkeypatch.setattr(source, "beschaffen", lambda q, a: video)
    monkeypatch.setattr(source, "metadaten", lambda a: {"titel": "Test-Podcast", "kanal": "Kanal X", "url": "", "lizenz": ""})
    monkeypatch.setenv(handoff.ENV, "1")
    order = job.parse_order(_auftrag(), set())
    folder = tmp_path / "auftrag"
    code, data = job.run_order(order, folder)
    assert code == job.EXIT_WRITE and data is None                       # Claude soll den Hook wählen
    aufgabe = (folder / "schreiben_offen.txt").read_text("utf-8")
    assert aufgabe.endswith("schreiben_clip_hook.json")
    f = json.loads(Path(aufgabe).read_text("utf-8"))
    assert f["aufgabe"] == "clip_hook" and f["daten"]["kandidaten"]
    f["antwort"] = {"nr": 1, "begruendung": "stärkste Frage"}
    Path(aufgabe).write_text(json.dumps(f), "utf-8")
    code, data = job.run_order(order, folder)
    assert code == job.EXIT_WRITE and data is None                       # danach das Inhaltsurteil „clip_urteil“
    aufgabe = (folder / "schreiben_offen.txt").read_text("utf-8")
    f = json.loads(Path(aufgabe).read_text("utf-8"))
    assert f["aufgabe"] == "clip_urteil" and f["daten"]["saetze"]
    f["antwort"] = {"punkte": 8, "pointe": True, "verstaendlich": True, "titel": "Warum glaubst du das nicht", "grund": "klarer Streit"}
    Path(aufgabe).write_text(json.dumps(f), "utf-8")
    code, data = job.run_order(order, folder)
    assert code == 0 and data["ok"] and data["art"] == "clip"
    v = data["videos"][0]
    assert v["dauer"] <= 179 and v["mb"] <= 19 and Path(v["video"]).exists()
    assert "#shorts" in v["youtube"]
    assert "Clip aus: Test-Podcast / Kanal X – Quelle: https://example.org/watch?v=abc" in v["youtube"]
    assert "Quelle: https://example.org" in v["tiktok"]
    assert data["titel"] and "Hook" in data["pruefbericht"] and "Erlaubnis" in data["pruefbericht"]
    assert "von Claude gewählt" in data["pruefbericht"] and "Inhaltsurteil (Claude): 8/10" in data["pruefbericht"]
    doc = job.document(folder, {v["video"]: "https://x/clip.mp4"})
    assert doc["ok"] and doc["videos"][0]["video_url"] == "https://x/clip.mp4"


def test_clip_download_gesperrt_meldet_hinweis(tmp_path, monkeypatch):
    from cudi_video import job

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(job.config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    aufrufe = []

    def gesperrt(q, a):
        aufrufe.append(1)
        raise ClipError("Download fehlgeschlagen (Sign in). Hinweis: später erneut versuchen – oder am eigenen PC.",
                        wiederholbar=True)

    monkeypatch.setattr(source, "beschaffen", gesperrt)
    code, data = job.run_order(job.parse_order(_auftrag(), set()), tmp_path / "a")
    assert code == 1 and not data["ok"] and "später" in data["fehler"] and data["wiederholbar"] is True
    assert len(aufrufe) == 2                                             # ein zweiter Versuch nach Pause

    def fehlt(q, a):
        raise ClipError("Datei nicht gefunden")

    monkeypatch.setattr(source, "beschaffen", fehlt)
    code, data = job.run_order(job.parse_order(_auftrag(id="clip5678"), set()), tmp_path / "b")
    assert not data["ok"] and data["wiederholbar"] is False
