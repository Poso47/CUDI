"""Tests der Clip-Engine: ohne Netz, ohne Modelle (Spracherkennung per Monkeypatch), mit kleinen ffmpeg-Testvideos."""

import json
import shutil
import subprocess

import numpy as np
import pytest

from cudi_video import config
from cudi_video.clip import ClipError, cuts, highlights, pipeline, source, subtitles, transcribe

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")


def _w(text, s, e):
    return {"w": text, "s": s, "e": e, "p": 0.9}


def _skript():
    """Gesprächsskript (Wörter mit Zeiten): Einstieg ruhig, bei 8–11 s die provokante Frage, danach Reaktion."""
    teile = [
        ("Heute", 0.5), ("reden", 0.4), ("wir", 0.3), ("über", 0.3), ("Nachrichten.", 0.6),
        (None, 0.9),  # Pause
        ("Also", 0.3), ("ich", 0.2), ("lese", 0.3), ("jeden", 0.3), ("Morgen", 0.4), ("alles.", 0.5),
        (None, 0.5),
        ("Warum", 0.4), ("glaubst", 0.5), ("du", 0.3), ("das", 0.3), ("nicht", 0.5), ("überhaupt?", 0.7),
        (None, 0.4),
        ("Nein,", 0.4), ("nein,", 0.4), ("nein,", 0.4), ("das", 0.3), ("stimmt", 0.5), ("niemals!", 0.7),
        (None, 0.6),
        ("Ich", 0.2), ("habe", 0.3), ("2024", 0.6), ("Länder", 0.5), ("verglichen.", 0.8),
    ]
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


def _probe(pfad):
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,r_frame_rate",
                          "-show_entries", "format=duration", "-of", "json", str(pfad)], capture_output=True, text=True)
    return json.loads(res.stdout)


# --------------------------------------------------------------------------- reine Logik

def test_pausen_werden_geschnitten_und_zeiten_verschoben():
    ws = [_w("a", 0.0, 0.4), _w("b", 0.5, 0.9), _w("c", 2.0, 2.4), _w("d", 2.5, 3.0)]
    iv = cuts.pausen_intervalle(ws)
    assert len(iv) == 2                               # Lücke 1,1 s > 0,35 s -> Schnitt
    assert iv[0][1] < 1.1 and iv[1][0] > 1.8          # Pause bis auf Luft entfernt
    ab = cuts.Abschnitt("main", iv)
    assert ab.dauer < 3.0 - 0.7
    assert ab.mappe(2.0) < 2.0 - 0.8                  # spätere Wörter rücken vor
    assert ab.mappe(0.5) == pytest.approx(0.5, abs=0.1)


def test_kleine_luecken_bleiben():
    ws = [_w("a", 0.0, 0.4), _w("b", 0.6, 1.0)]
    assert len(cuts.pausen_intervalle(ws)) == 1


def test_saetze_hook_und_teaser():
    ws = _skript()
    sats = highlights.saetze_bilden(ws)
    assert any(s.text.endswith("überhaupt?") for s in sats)
    rms = np.ones(300) * 0.05
    highlights.bewerte(sats, ws, rms, 0.0, "de")
    fenster = highlights.fenster_finden(sats, 30, 90)
    assert fenster.start == sats[0].start             # kurzes Material -> alles
    hook = highlights.hook_finden(fenster)
    assert hook is not None and "überhaupt?" in hook.text
    assert 1.5 <= hook.dauer <= 7.0
    assert highlights.braucht_teaser(hook, fenster)   # Frage steht nicht am Anfang -> Cold Open


def test_kein_teaser_wenn_hook_am_anfang():
    ws = [_w("Warum", 0.0, 0.4), _w("machst", 0.5, 0.9), _w("du", 1.0, 1.2), _w("das", 1.3, 1.6), _w("nicht?", 1.7, 2.4),
          _w("Weil", 3.0, 3.3), _w("ich", 3.4, 3.6), _w("nicht", 3.7, 4.0), _w("will.", 4.1, 4.5)]
    sats = highlights.saetze_bilden(ws)
    highlights.bewerte(sats, ws, np.ones(60) * 0.05, 0.0, "de")
    f = highlights.fenster_finden(sats)
    hook = highlights.hook_finden(f)
    assert hook and not highlights.braucht_teaser(hook, f)


def test_fenster_laenge_30_bis_90():
    # 300 s Material: alle 4 s ein Satz, einer davon mit viel Emotion bei 150 s
    ws = []
    for k in range(75):
        t = k * 4.0
        text = ["Nein,", "das", "stimmt", "niemals!"] if k == 37 else ["Das", "ist", "ein", "ruhiger", "Satz."]
        for j, x in enumerate(text):
            ws.append(_w(x, round(t + j * 0.6, 2), round(t + j * 0.6 + 0.5, 2)))
    sats = highlights.saetze_bilden(ws)
    highlights.bewerte(sats, ws, np.ones(3000) * 0.05, 0.0, "de")
    f = highlights.fenster_finden(sats, 30, 90)
    assert 30 <= f.ende - f.start <= 90
    assert f.start <= 150 <= f.ende
    forced = highlights.fenster_erzwingen(sats, 10, 50)
    assert (forced.start, forced.ende) == (10, 50)


def test_untertitel_gruppen_grossbuchstaben_gelb():
    ws = [_w("Ich", 0.0, 0.2), _w("glaube", 0.25, 0.6), _w("nicht,", 0.65, 1.0), _w("dass", 1.05, 1.3), _w("du", 1.35, 1.5),
          _w("2024", 1.55, 2.0), _w("recherchierst.", 2.05, 2.8)]
    gr = subtitles.gruppen_bilden(ws, "de")
    assert all(1 <= len(g) <= 3 for g in gr)
    assert sum(len(g) for g in gr) == len(ws)
    assert subtitles.schluesselwort([_w("im", 0, 1), _w("2024", 1, 2), _w("Jahr", 2, 3)]) == 1   # Zahl
    assert subtitles.schluesselwort([_w("der", 0, 1), _w("Wahnsinn", 1, 2)]) == 1                # längstes Inhaltswort
    ass, n = subtitles.ass_bauen(ws, "de", "Anton", False, 4.0)
    assert n == len(gr)
    assert "RECHERCHIERST" in ass and "recherchierst" not in ass
    assert "&H00D4FF&" in ass                          # #FFD400
    assert "\\pos(540,1209)" in ass                    # 63 % von 1920
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass


def test_schrift_findet_etwas():
    datei, familie, _fett = subtitles.schrift_finden()
    assert familie
    if datei is not None:
        assert datei.exists()


def test_quelle_fehler(tmp_path, monkeypatch):
    with pytest.raises(ClipError, match="nicht gefunden"):
        source.beschaffen(str(tmp_path / "gibtsnicht.mp4"), tmp_path)
    monkeypatch.setattr(source.shutil, "which", lambda n: "/usr/bin/yt-dlp")

    class R:
        returncode, stdout, stderr = 1, "", "ERROR: Sign in to confirm you're not a bot"

    monkeypatch.setattr(source.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(ClipError, match="Cloud"):
        source.beschaffen("https://example.org/v", tmp_path)


def test_cli_meldet_fehler_sauber(capsys):
    from cudi_video.__main__ import main

    assert main(["clip", "/nicht/da.mp4"]) == 1
    assert "Fehler" in capsys.readouterr().err


# --------------------------------------------------------------------------- Ende-zu-Ende (kleines Testvideo)

@needs_ffmpeg
@pytest.mark.parametrize("w,h", [(320, 240), (180, 320)])
def test_clip_ende_zu_ende(tmp_path, monkeypatch, w, h):
    video = tmp_path / f"quelle_{w}x{h}.mp4"
    _video(video, w, h, 20)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(transcribe, "erkenne", lambda audio, sprache: [dict(x) for x in _skript()])
    info = pipeline.make_clip(str(video), sprache="de")
    clip = tmp_path / "out" / "clips" / video.stem / "clip.mp4"
    assert clip.exists() and (clip.parent / "clip.json").exists()
    p = _probe(clip)
    v = next(s for s in p["streams"] if "width" in s)
    assert (v["width"], v["height"]) == (1080, 1920) and v["r_frame_rate"] == "30/1"
    assert v["codec_name"] == "h264" and any(s["codec_name"] == "aac" for s in p["streams"])
    assert 5 < float(p["format"]["duration"]) <= 179
    assert info["hook"] and info["hook"]["teaser_vorangestellt"]
    arten = [s["art"] for s in info["schnitte"]]
    assert arten[0] == "teaser" and "blitz" in arten and arten.count("main") >= 1
    assert info["pausen_entfernt_s"] > 0.5
    gespeichert = json.loads((clip.parent / "clip.json").read_text("utf-8"))
    assert gespeichert["untertitel"]["gruppen"] > 3 and gespeichert["transkript"].startswith("Heute")
    assert list((tmp_path / "out" / "_work").rglob("woerter_*.json"))   # Transkript zwischengespeichert


@needs_ffmpeg
def test_erzwungenes_fenster_und_cache(tmp_path, monkeypatch):
    video = tmp_path / "v.mp4"
    _video(video, 320, 240, 20)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    aufrufe = []

    def fake(audio, sprache):
        aufrufe.append(len(audio))
        return [dict(x) for x in _skript() if x["s"] < 8 and x["e"] < 7.5][:12]

    monkeypatch.setattr(transcribe, "erkenne", fake)
    info = pipeline.make_clip(str(video), start=0.0, ende=8.0)
    assert info["fenster"]["erzwungen"] and info["fenster"]["start"] >= 0
    pipeline.make_clip(str(video), start=0.0, ende=8.0)
    assert len(aufrufe) == 1                           # zweiter Lauf nutzt das JSON-Zwischenergebnis
    with pytest.raises(ClipError):
        pipeline.make_clip(str(video), start=5.0, ende=2.0)
