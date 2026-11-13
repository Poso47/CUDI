"""Schaubild: Stil-Katalog, Auftrag, Belegprüfung, Layout, Render je Stil und Seitenformat – alles ohne Netz."""

import json
import shutil
import wave

import numpy as np
import pytest
from PIL import Image

from cudi_video import handoff, job, schaubild
from cudi_video.schaubild import render as R, sfx

QUELLE = [{"id": "q1", "name": "Wikipedia: Hühnerei", "url": "https://de.wikipedia.org/wiki/H%C3%BChnerei",
           "text": "Die Bildung des Eies dauert etwa 24 Stunden. Im Eileiter wird der Dotter vom Eiklar umgeben. "
                   "In der Schalendrüse verbleibt das Ei rund 20 Stunden, dort wird die Kalkschale gebildet. "
                   "Die Schale besteht überwiegend aus Kalk und wiegt etwa 5 Gramm."}]


def station(**kw):
    base = {"name": "Schalendrüse", "text": "In der Schalendrüse bleibt das Ei rund 20 Stunden, dort entsteht die Schale aus Kalk.",
            "zahl": "20", "einheit": "Stunden", "beleg": "In der Schalendrüse verbleibt das Ei rund 20 Stunden, dort wird die Kalkschale gebildet.",
            "etiketten": ["Schalendrüse", "Kalk", "Erfundenes Teil"], "bild": "egg inside shell gland"}
    return {**base, **kw}


def test_katalog_vollstaendig():
    stile = schaubild.stile()
    assert len(stile) == 22 and "schaubild" in stile and list(stile)[0] == "animation"
    for s in stile.values():
        assert s["modus"] in ("bild", "code", "szene") and len(s["bg"]) == 2 and len(s["ink"]) == 2 and s["schrift"][0] in R.FONTS
        assert s["modus"] != "bild" or "no text" in s["prompt"]
        assert not any(w in s["beschreibung"].lower() for w in ("flüssige bewegung", "läuft", "spricht"))   # nichts versprechen
    assert {k for k, s in stile.items() if s["modus"] == "code"} == {"motiongraphics", "linien", "typografie"}


def test_auftrag_parsen():
    order = job.parse_order({"id": "test-t1", **{"art": "schaubild", "thema": "Wie entsteht ein Ei?", "stil": "comic", "seitenformat": "16:9"}}, set())
    assert (order["art"], order["stil"], order["seitenformat"], order["stationen"]) == ("schaubild", "comic", "16:9", 6)
    assert job.parse_order({"id": "test-t0", "art": "schaubild", "thema": "Wie entsteht ein Ei?"}, set())["stil"] == "animation"
    for bad in ({"stil": "gibtsnicht"}, {"seitenformat": "4:3"}, {"stationen": 12}, {"thema": "x"}):
        with pytest.raises(job.OrderError):
            job.parse_order({"id": "test-t2", **{"art": "schaubild", "thema": "Wie entsteht ein Ei?", **bad}}, set())


def test_station_pruefung():
    ok, why = schaubild.pruefe_station(station(), QUELLE, "de")
    assert ok and ok["zahl"] == "20" and ok["etiketten"] == ["Schalendrüse", "Kalk"]          # erfundenes Etikett fliegt raus
    assert schaubild.pruefe_station(station(beleg="Das Ei bleibt dort genau 20 Stunden und wird hart."), QUELLE, "de")[0] is None
    bad, why = schaubild.pruefe_station(station(text="In der Schalendrüse bleibt das Ei rund 48 Stunden, dort entsteht die Schale."), QUELLE, "de")
    assert bad is None and "Zahl" in why
    ohne, _ = schaubild.pruefe_station(station(zahl="99"), QUELLE, "de")
    assert ohne and ohne["zahl"] == "" and ohne["einheit"] == ""                               # Riesenzahl nur mit Beleg


def test_auto_stil():
    assert schaubild.waehle_stil("auto", "Wie funktioniert das Stromnetz?")["id"] == "isometrisch"
    assert schaubild.waehle_stil("auto", "Wie entsteht ein Ei?")["id"] == "schaubild"


@pytest.mark.parametrize("fmt", schaubild.FORMATE)
def test_etiketten_layout(fmt):
    g = R.geo(fmt)
    stil = schaubild.stile()["schaubild"]
    sizes = [(im.width, im.height) for im in (R.label_image(t, stil, True) for t in ("Schalendrüse", "linker Eierstock", "Kalk"))]
    slots = R.label_slots(g, sizes)
    for s in slots:
        assert g["safe"][0] <= s["x"] and s["x"] + s["w"] <= g["safe"][2] and g["safe"][1] <= s["y"] and s["y"] + s["h"] <= g["safe"][3]
    for a in range(3):
        for b in range(a + 1, 3):
            A, B = slots[a], slots[b]
            assert A["x"] + A["w"] <= B["x"] or B["x"] + B["w"] <= A["x"] or A["y"] + A["h"] <= B["y"] or B["y"] + B["h"] <= A["y"]


def _job(stil, fmt, bild):
    text = "Hier bleibt das Ei etwa 20 Stunden und die Schale entsteht aus Kalk."
    words = [{"text": w, "start": i * .25, "end": i * .25 + .2} for i, w in enumerate(text.split())]
    return {"index": 1, "id": "t", "typ": "station", "lang": "de", "format": fmt, "stil": stil, "text": text, "words": words,
            "lead": .45, "voice_dur": 1.0, "frames": 60, "duration": 2.0, "fps": 30, "voice_path": "",
            "bild": bild if stil["modus"] == "bild" else None, "ki": True, "zahl": "20", "einheit": "Stunden", "kopf": "",
            "wort": "Schale", "etiketten": ["Schale", "Kalk"], "station": 2, "n": 5, "out": ""}


def test_jeder_stil_rendert(tmp_path):
    bild = tmp_path / "p.jpg"
    Image.new("RGB", (576, 1024), (40, 90, 110)).save(bild)
    for sid, stil in schaubild.stile().items():
        frame = R.make_scene(_job(stil, "9:16", str(bild))).frame(1.4)
        assert frame.size == (1080, 1920), sid
        assert np.asarray(frame.convert("L")).std() > 4, sid                                   # nicht leer
    assert R.make_scene(_job(schaubild.stile()["comic"], "16:9", str(bild))).frame(1.0).size == (1920, 1080)


def test_soundeffekte():
    track = np.zeros(48000, dtype=np.float32)
    sfx.place(track, [(0.1, "wusch"), (0.5, "pop"), (0.7, "tick"), (0.0, "stift")], 0.2, 48000)
    assert 0 < np.abs(track).max() <= 0.2 * sfx.GAIN * 1.6 * 1.6
    jobs = [dict(_job(schaubild.stile()["whiteboard"], "9:16", "x.jpg"), index=i) for i in range(2)]
    names = [n for _, n in R.events(jobs)]
    assert names.count("wusch") == 1 and "tick" in names and "pop" in names and "stift" in names


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")
@pytest.mark.parametrize("fmt,size", [("9:16", (1080, 1920)), ("16:9", (1920, 1080))])
def test_lauf_ohne_netz(tmp_path, monkeypatch, fmt, size):
    """Ganzer Auftrag: Quellen und Antwort gestellt, Stimme als Stille – Video, Ablauf und Prüfbericht entstehen."""
    from cudi_video import qa, tts
    from cudi_video.story import visuals

    monkeypatch.setattr(schaubild, "quellen_sammeln", lambda thema, lang: QUELLE)
    monkeypatch.setattr(handoff, "active", lambda: True)
    answer = {"titel": "Wie entsteht ein Ei?", "hook": "Wie entsteht eigentlich ein Ei?", "versprechen": "Eine Reise durch den Eileiter.",
              "schluss": "Jetzt siehst du dein Frühstücksei mit anderen Augen. Es wurde 1999 erfunden.",
              "stationen": [station(),
                            station(name="Eiklar", text="Im Eileiter wird der Dotter langsam vom Eiklar umgeben, Schicht für Schicht.", zahl="",
                                    beleg="Im Eileiter wird der Dotter vom Eiklar umgeben.", etiketten=["Dotter", "Eiklar"]),
                            station(name="Schale", text="Die Schale besteht überwiegend aus Kalk und wiegt am Ende etwa 5 Gramm.", zahl="5", einheit="Gramm",
                                    beleg="Die Schale besteht überwiegend aus Kalk und wiegt etwa 5 Gramm.", etiketten=["Kalk"]),
                            station(name="Erfunden", text="Danach fliegt das Ei genau 300 Kilometer weit durch die Luft davon.",
                                    beleg="Danach fliegt das Ei 300 Kilometer weit.")]}
    monkeypatch.setattr(handoff, "request", lambda task, instructions, data: answer)
    monkeypatch.setattr(visuals, "ai_image", lambda prompt, seed: None)
    monkeypatch.setattr(visuals, "commons_photo", lambda *a, **k: None)
    monkeypatch.setattr(qa, "safe_check", lambda *a, **k: {"ok": True, "befunde": []})

    def voice(texts, out_dir, voice, rate="+0%", pitch="+0Hz", **kw):
        out_dir.mkdir(parents=True, exist_ok=True)
        res = []
        for i, t in enumerate(texts):
            p = out_dir / f"{i}.wav"
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(b"\0\0" * 24000)
            res.append((p, [{"text": x, "start": k * .05, "end": k * .05 + .04} for k, x in enumerate(t.split())], 0.5))
        return res

    monkeypatch.setattr(tts, "voice_texts", voice)
    order = job.parse_order({"id": "test-t3", **{"art": "schaubild", "thema": "Wie entsteht ein Ei?", "stationen": 4, "stil": "motiongraphics",
                                        "seitenformat": fmt}}, set())
    result = schaubild.run(order, tmp_path)
    out = tmp_path / "schaubild"
    files = result["videos"]["de"]
    info = qa.probe(out / files["video"])
    assert (info["breite"], info["hoehe"]) == size
    ablauf = json.loads((out / "ablauf.json").read_text("utf-8"))
    assert ablauf["aufloesung"] == f"{size[0]}x{size[1]}" and len(ablauf["szenen"]) == 5       # Intro + 3 Stationen + Schluss
    assert all(s["beleg"] for s in ablauf["szenen"] if s["typ"] == "station")
    review = (out / "review.md").read_text("utf-8")
    assert "300 Kilometer" in review and "Abgelehnt" in review                                  # Erfundenes steht nur im Bericht
    assert "1999" not in json.dumps(ablauf)                                                     # unbelegte Zahl im Schluss ersetzt


def test_ohne_sprachmodell_ehrlicher_abbruch(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "active", lambda: False)
    order = job.parse_order({"id": "test-t4", **{"art": "schaubild", "thema": "Wie entsteht ein Ei?"}}, set())
    with pytest.raises(schaubild.SchaubildError, match="Erfunden wird nichts"):
        schaubild.run(order, tmp_path)


def test_tiefen_effekt_bewegt_das_motiv(tmp_path, monkeypatch):
    """Tiefen-Effekt: Motiv vorn, Rand hinten; das Bild ändert sich über die Zeit; flache Stile und CUDI_TIEFE=0 bleiben ohne."""
    from PIL import ImageDraw

    bild = tmp_path / "m.jpg"
    im = Image.new("RGB", (576, 1024), (20, 60, 80))
    ImageDraw.Draw(im).ellipse((160, 330, 420, 690), fill=(240, 170, 40))
    im.save(bild)
    stile = schaubild.stile()
    sc = R.make_scene(_job(stile["schaubild"], "9:16", str(bild)))
    n = sc.tiefe.shape[0]
    assert sc.tiefe[n // 2, n // 2] > 0.6 and sc.tiefe[4, 4] < 0.15
    a, b = np.asarray(sc._picture(0.5).convert("L"), dtype=np.int16), np.asarray(sc._picture(1.6).convert("L"), dtype=np.int16)
    assert np.abs(a - b).mean() > 0.5
    assert R.make_scene(_job(stile["comic"], "9:16", str(bild))).tiefe is None
    monkeypatch.setenv("CUDI_TIEFE", "0")
    assert R.make_scene(_job(stile["schaubild"], "9:16", str(bild))).tiefe is None


def test_bildfolge_je_satz_und_guthaben(tmp_path, monkeypatch):
    """Je Satz ein Bild, Wechsel zum Satzbeginn; bei leerem Guthaben (402) wird nicht weiter angefragt und es gibt einen Hinweis."""
    from cudi_video import config, net
    from cudi_video.story import visuals

    st, _ = schaubild.pruefe_station(station(bilder=["hen cutaway with shell gland", "white shell growing around egg", "x", "viertes Bild"]), QUELLE, "de")
    assert st["bilder"] == ["hen cutaway with shell gland", "white shell growing around egg", "viertes Bild"][:schaubild.MAX_BILDER] or len(st["bilder"]) <= schaubild.MAX_BILDER
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    for p, col in ((a, (200, 40, 40)), (b, (40, 40, 200))):
        im = Image.new("RGB", (512, 512), (20, 60, 80))
        im.paste(Image.new("RGB", (200, 200), col), (156, 156))
        im.save(p)
    job_ = _job(schaubild.stile()["schaubild"], "9:16", str(a))
    job_["text"] = "Erst kommt der Dotter. Dann kommt die Schale dazu."
    job_["words"] = [{"text": w, "start": i * .4, "end": i * .4 + .3} for i, w in enumerate(job_["text"].split())]
    job_["bildfolge"] = [{"datei": str(a), "logo": False}, {"datei": str(b), "logo": False}]
    job_["duration"], job_["etiketten"], job_["zahl"] = 5.0, [], ""
    sc = R.make_scene(job_)
    assert len(sc.pics) == 2 and sc.pics[1]["start"] == pytest.approx(.45 + 4 * .4 - .12)
    mitte = lambda t: np.asarray(sc._picture(t).convert("RGB"))[sc.size // 2, sc.size // 2]
    assert mitte(1.0)[0] > mitte(1.0)[2] and mitte(4.0)[2] > mitte(4.0)[0]                    # erst rot, dann blau
    calls = []

    def kaputt(url, **kw):
        calls.append(url)
        raise RuntimeError("HTTP Error 402: Payment Required")

    monkeypatch.setattr(config, "POLLINATIONS_TOKEN", "x")
    monkeypatch.setattr(net, "cached_file", lambda *a, **k: None)
    monkeypatch.setattr(net, "download", kaputt)
    monkeypatch.setattr(visuals, "ai_image", lambda prompt, seed: None)
    monkeypatch.setattr(visuals, "commons_photo", lambda *a, **k: None)
    monkeypatch.setattr(schaubild, "_guthaben_leer", [False])
    skript = schaubild.baue_skript("t", "Titel", "Hook?", "", [dict(st, bilder=["eins", "zwei"])] * 2, "Schluss.", "de",
                                   schaubild.stile()["schaubild"], "9:16")
    notes: list[str] = []
    schaubild.bilder(skript, tmp_path, notes)
    assert len(calls) == 1 and any("Guthaben" in n for n in notes)


SZENE = {"elemente": [{"id": "rohr", "art": "schlauch", "punkte": [[20, 15], [70, 30], [30, 55], [70, 80]], "breite": 14, "farbe": "gold"},
                      {"id": "dotter", "art": "form", "form": "kreis", "farbe": "dotter", "x": 20, "y": 15, "groesse": 13},
                      {"id": "eiklar", "art": "huelle", "um": "dotter", "groesse": 30, "farbe": "eiklar"},
                      {"id": "kaputt", "art": "raumschiff"}, {"id": "ohneziel", "art": "schale", "um": "gibtsnicht"},
                      {"id": "umriss", "art": "form", "pfad": "M 10 10 L 90 10 C 90 60 60 90 50 90 Q 10 90 10 10 Z", "farbe": "#3366cc", "x": 80, "y": 80, "groesse": 20}],
         "schritte": [{"ab": 1, "nach": 0.2, "dauer": 3, "ziel": "dotter", "aktion": "bewege", "entlang": "rohr", "von": 0, "bis": 1},
                      {"ab": 2, "nach": 0.2, "dauer": 2, "ziel": "eiklar", "aktion": "fuelle", "auf": 1},
                      {"ab": 1, "ziel": "dotter", "aktion": "explodiere"}, {"ab": 1, "ziel": "niemand", "aktion": "wachse", "auf": 30}]}


def test_eigene_animation_szene():
    """Szene wird gesäubert (Unbekanntes fliegt raus) und bewegt sich zum Satz: Dotter wandert, Eiklar wächst erst im zweiten Satz."""
    from cudi_video.schaubild import zeichnen as Z

    sz = Z.pruefe_szene(SZENE)
    assert [e["id"] for e in sz["elemente"]] == ["rohr", "dotter", "eiklar", "umriss"] and len(sz["schritte"]) == 2
    assert Z.pruefe_szene({"elemente": [{"art": "raumschiff"}]}) is None and Z.pruefe_szene("unsinn") is None
    assert len(Z.svg_punkte("M 0 0 L 10 0 L 10 10 Z")[0]) == 3
    b = Z.Buehne(sz, 300, [0.5, 4.0], (250, 250, 250), (230, 160, 30))
    anfang, ende = b.zustand(0.6)["dotter"], b.zustand(3.9)["dotter"]
    assert (round(anfang["x"]), round(anfang["y"])) == (20, 15) and (round(ende["x"]), round(ende["y"])) == (70, 80)   # am Ende des Schlauchs
    assert b.zustand(3.0)["eiklar"]["f"] == 0 and b.zustand(6.5)["eiklar"]["f"] == pytest.approx(1)
    a, c = np.asarray(b.bild(1.0), dtype=np.int16), np.asarray(b.bild(6.5), dtype=np.int16)
    assert a.shape == (300, 300, 4) and a[..., 3].max() == 255 and np.abs(a - c).mean() > 1


def test_eigene_animation_im_video(tmp_path):
    """Station mit Szene: das Bild kommt von der Bühne (kein Bild aus dem Netz), Kennzeichnung „Animation“."""
    from cudi_video.schaubild import zeichnen as Z

    stil = schaubild.stile()["animation"]
    job_ = _job(stil, "9:16", "")
    job_.update(text="Der Dotter wandert durch den Eileiter. Dort legt sich das Eiklar um ihn.", szene=Z.pruefe_szene(SZENE), duration=6.0)
    job_["words"] = [{"text": w, "start": i * .3, "end": i * .3 + .25} for i, w in enumerate(job_["text"].split())]
    sc = R.make_scene(job_)
    assert sc.buehne is not None and sc.pic is None
    f1, f2 = np.asarray(sc.frame(1.0).convert("L"), dtype=np.int16), np.asarray(sc.frame(4.5).convert("L"), dtype=np.int16)
    assert np.abs(f1 - f2).mean() > 0.3
    st, _ = schaubild.pruefe_station(station(szene=SZENE), QUELLE, "de")
    assert st["szene"] and len(st["szene"]["elemente"]) == 4
