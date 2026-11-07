"""Tests der Clip-Engine: ohne Netz, ohne Modelle (Spracherkennung per Monkeypatch), mit kleinen ffmpeg-Testvideos."""

import json
import shutil
import subprocess

import numpy as np
import pytest

from cudi_video import config
from cudi_video.clip import ClipError, cuts, highlights, pipeline, reframe, source, subtitles, transcribe

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


# --------------------------------------------------------------------------- Hook-Regeln, Untertitel, Gesichtserkennung

def _gespraech():
    """Einstieg wie im Vorbild-Clip: direkte Frage ans Gegenüber, Widerspruch, dann Reaktion „Nein, nein, nein“;
    später (ab 40 s) eine weitere Frage ohne Anrede und viel ruhiger Text."""
    text = ("Wie recherchierst du überhaupt? Weil ich glaub nicht, dass du einen Bericht liest und dann sagst, "
            "dass es genauso ist. Nein, nein, nein, ich mach's wirklich, das ist auch der Sinn. "
            "Das ist ein bisschen umständlich, aber mit KI wird es einfacher. ")
    text += "Ich lese die News von einem Land und gucke was andere Medien darüber berichten. " * 4
    text += "Stimmt das mit dem überein, was Obama gesagt hat? Ja, im Großen und Ganzen schon. "
    text += "Und deshalb ist das für mich ein ganz normaler Ablauf jeden Tag. " * 3
    ws, t = [], 0.0
    for tok in text.split():
        ws.append(_w(tok, round(t, 3), round(t + 0.34, 3)))
        t += 0.4 + (0.2 if tok[-1] in ".?" else 0)
    return ws


def test_hook_am_beispielanfang_ohne_cold_open():
    ws = _gespraech()
    sats = highlights.saetze_bilden(ws)
    highlights.bewerte(sats, ws, np.ones(int(ws[-1]["e"] * 10) + 20) * 0.05, 0.0, "de")
    f = highlights.fenster_finden(sats, 30, 90)
    hook = highlights.hook_finden(f)
    assert hook is not None and hook.start < 8.0
    assert "recherchierst" in hook.text
    assert not highlights.braucht_teaser(hook, f)
    kand = highlights.hook_kandidaten(f, 5)
    assert kand and kand[0].start == hook.start


def test_claude_hook_nur_mit_handoff(monkeypatch, tmp_path):
    from cudi_video import handoff
    from cudi_video.clip import wahl

    ws = _gespraech()
    sats = highlights.saetze_bilden(ws)
    highlights.bewerte(sats, ws, np.ones(int(ws[-1]["e"] * 10) + 20) * 0.05, 0.0, "de")
    monkeypatch.delenv(handoff.ENV, raising=False)
    assert wahl.claude_waehlen(sats, 90) is None                      # inaktiv -> Regeln
    monkeypatch.setenv(handoff.ENV, "1")
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    with pytest.raises(handoff.WritingNeeded):                        # Aufgabe wird abgelegt
        wahl.claude_waehlen(sats, 90)
    aufgabe = json.loads((tmp_path / "schreiben_clip_hook.json").read_text("utf-8"))
    assert 1 <= len(aufgabe["daten"]["kandidaten"]) <= 5
    aufgabe["antwort"] = {"nr": 2, "begruendung": "test"}
    (tmp_path / "schreiben_clip_hook.json").write_text(json.dumps(aufgabe), "utf-8")
    fe, hk = wahl.claude_waehlen(sats, 90)
    assert fe.start == hk.start and fe.ende - fe.start <= 90


def _ass_zeiten(ass):
    def sek(t):
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    out = []
    for z in ass.splitlines():
        if z.startswith("Dialogue:"):
            teile = z.split(",", 9)
            out.append((sek(teile[1]), sek(teile[2])))
    return out


def test_untertitel_ueberlappen_nie():
    # dichte Sprache, teils sehr kurze Wörter und winzige Lücken
    ws, t = [], 0.0
    for i in range(120):
        d = 0.08 if i % 7 == 0 else 0.3
        ws.append(_w(["ja", "Wahnsinn", "nein,", "der", "Hund.", "krass", "wirklich"][i % 7], round(t, 3), round(t + d, 3)))
        t += d + (0.02 if i % 5 else 0.5)
    ass, n = subtitles.ass_bauen(ws, "de", "Anton", False, t)
    zeiten = _ass_zeiten(ass)
    assert len(zeiten) == n > 10
    for (s1, e1), (s2, _e2) in zip(zeiten, zeiten[1:]):
        assert e1 <= s2 + 1e-6, (e1, s2)
        assert e1 > s1


def test_gesichtsanalyse_mit_detektor_und_ohne(tmp_path, monkeypatch):
    video = tmp_path / "v.mp4"
    _video(video, 320, 240, 4)
    # Detektor-Monkeypatch: liefert immer dasselbe Gesicht (kein Modell nötig)
    monkeypatch.setattr(reframe, "_detektor", lambda fw, fh: (lambda bild: [(fw // 3, fh // 4, fw // 4, fw // 4)]))
    an = reframe.analysiere(video, 0, 3, 320, 240)
    assert an.spuren == 1 and not an.hinweise
    cx, cy, fb = an.mitte(0, 0, 3)
    assert 100 < cx < 220 and fb > 40
    x, y, w, h = reframe.zuschnitt(an, 0, 0, 3, 1.0)
    assert abs(w / h - 9 / 16) < 0.02 and 0 <= x <= 320 - w and 0 <= y <= 240 - h
    # Kein Detektor -> Bildmitte mit Hinweis
    monkeypatch.setattr(reframe, "_detektor", lambda fw, fh: None)
    an2 = reframe.analysiere(video, 0, 3, 320, 240)
    assert an2.spuren == 0 and an2.hinweise
    assert reframe.zuschnitt(an2, 0, 0, 3, 1.0)[2] > 0


def test_yunet_modell_aus_cache(tmp_path, monkeypatch):
    modell = tmp_path / "m.onnx"
    modell.write_bytes(b"x" * 10)
    monkeypatch.setenv("CUDI_YUNET_MODELL", str(modell))
    assert reframe.yunet_modell() == modell
