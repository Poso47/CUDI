"""Animationsstudio: Abteilungen Storyboard → Figuren → Szenenbau → Abnahme, Lehrer, Einbau in die Videoarten."""

import json

from cudi_video import animation, handoff

TEXT = "Der Dotter wandert durch den Eileiter. Dort legt sich das Eiklar um ihn."
SZENE = {"elemente": [{"id": "d", "art": "form", "form": "kreis", "x": 20, "y": 15, "groesse": 13},
                      {"id": "k", "art": "huelle", "um": "d", "groesse": 30},
                      {"id": "rohr", "art": "schlauch", "punkte": [[20, 15], [70, 80]], "breite": 14},
                      {"id": "b1", "art": "beschriftung", "text": "Dotter", "an": "d"},
                      {"id": "b2", "art": "beschriftung", "text": "Eileiter", "an": "rohr"},
                      {"id": "b3", "art": "beschriftung", "text": "Eiklar", "an": "d"}],
         "schritte": [{"bei": "wandert", "ziel": "d", "aktion": "bewege", "entlang": "rohr"},
                      {"bei": "legt", "ziel": "k", "aktion": "fuelle", "auf": 1}]}


def test_studio_abteilungen_nacheinander(monkeypatch, tmp_path):
    """Storyboard liefert das Drehbuch, Figuren prüft Wünsche, Szenenbau bekommt das Drehbuch, Abnahme findet keine Lücke."""
    aufrufe = []

    def request(task, anleitung, daten):
        aufrufe.append((task, anleitung, daten))
        if task.endswith("_storyboard"):
            return {"storyboards": [{"key": "1", "drehbuch": [{"wort": "wandert", "zeigt": "Dotter gleitet durchs Rohr"},
                                                               {"wort": "erfunden", "zeigt": "fliegt raus"}],
                                     "figuren": ["huhn", "kuh"], "figur_wuensche": ["Eileiter-Modell"], "ohne_bild": []}]}
        return {"szenen": [{"key": "1", "szene": SZENE}]}

    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(handoff, "request", request)
    notes: list[str] = []
    szenen, abgleich = animation.szenen_schreiben([{"key": 1, "text": TEXT}], "Ei", "de", notes, "animation_fakten_de")
    assert [a[0] for a in aufrufe] == ["animation_fakten_de_storyboard", "animation_fakten_de"]
    assert "Storyboard-Abteilung" in aufrufe[0][1] and "Szenenbau-Abteilung" in aufrufe[1][1]
    eintrag = aufrufe[1][2]["eintraege"][0]
    assert eintrag["drehbuch"] == [{"wort": "wandert", "zeigt": "Dotter gleitet durchs Rohr"}] and eintrag["figuren"] == ["huhn"]
    assert "1" in szenen and abgleich[0]["maengel"] == []
    assert abgleich[0]["figur_wuensche"] == ["Eileiter-Modell", "kuh"]
    animation.speichern(tmp_path, "fakten", abgleich)
    bericht = animation.bericht(abgleich)
    assert "Storyboard → Figuren → Szenenbau" in bericht and "Figur fehlt noch" in bericht
    assert json.loads((tmp_path / "abgleich.json").read_text("utf-8"))["abschnitte"][0]["key"] == "1"


def test_studio_aus_und_ohne_modell(monkeypatch):
    """CUDI_STUDIO=0 = eine Aufgabe; ohne Sprachmodell bleibt alles leer (bisherige Grafik)."""
    aufrufe = []
    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(handoff, "request", lambda task, *a: aufrufe.append(task) or {"szenen": [{"key": "1", "szene": SZENE}]})
    monkeypatch.setenv("CUDI_STUDIO", "0")
    szenen, _ = animation.szenen_schreiben([{"key": "1", "text": TEXT}], "Ei", "de", [], "animation_erklaer")
    assert aufrufe == ["animation_erklaer"] and "1" in szenen
    monkeypatch.setattr(handoff, "active", lambda: False)
    assert animation.szenen_schreiben([{"key": "1", "text": TEXT}], "Ei", "de", [], "x") == ({}, [])


def test_bild_zeichnet_im_takt():
    words = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate(TEXT.split())]
    from cudi_video.schaubild import zeichnen as Z
    b = animation.Bild(Z.pruefe_szene(SZENE), TEXT, words, 0.2, (20, 20, 20), (200, 150, 80))
    a, z = b.bild(0.1, 300), b.bild(5.0, 300)
    assert a.size == (300, 300) and a.tobytes() != z.tobytes()


def test_bildlehrer_lernt_aus_luecken(monkeypatch, tmp_path):
    from cudi_video.firma import __main__ as firma_main
    from cudi_video.firma import bildlehrer, common

    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    monkeypatch.setattr("cudi_video.config.LLM_BASE_URL", "")
    lauf = {"art": "fakten", "abschnitte": [
        {"key": str(i), "maengel": ["„Eileiter“ wird gesagt, aber nicht gezeigt", "Satz 2 hat keinen eigenen Schritt"],
         "figur_wuensche": ["Kuh"]} for i in range(3)] + [{"key": "9", "maengel": []}]}
    datei = tmp_path / "abgleich_neu.json"
    datei.write_text(json.dumps([lauf]), "utf-8")
    assert firma_main.main(["abgleich", str(datei)]) == 0
    assert len(common.read_json("abgleich.json")["abschnitte"]) == 4
    bildlehrer.run()
    daten = common.read_json("bildregeln.json")
    assert daten["abschnitte"] == 4 and daten["ohne_luecke"] == 1 and daten["figur_wuensche"] == [{"figur": "kuh", "faelle": 3}]
    assert any("eileiter" in r["regel"] for r in daten["regeln"]) and any("Satz" in r["regel"] for r in daten["regeln"])
    monkeypatch.setattr(animation, "REGELN_DATEI", common.DATA_DIR / "bildregeln.json")
    assert "GELERNT AUS FRÜHEREN VIDEOS" in animation.storyboard_anleitung("Ei", "de")


def test_notbetrieb_sammelt_abgleich(monkeypatch, tmp_path):
    import importlib.util
    import pathlib

    from cudi_video import config

    spec = importlib.util.spec_from_file_location("nb", pathlib.Path(__file__).parent.parent / ".github/scripts/notbetrieb.py")
    nb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    (tmp_path / "auftrag-a").mkdir()
    (tmp_path / "auftrag-a" / "abgleich.json").write_text(json.dumps({"art": "erklaer", "abschnitte": [{"key": "1"}]}), "utf-8")
    nb.sammle_abgleich()
    assert json.loads((tmp_path / "abgleich_neu.json").read_text("utf-8"))[0]["art"] == "erklaer"


def test_abgrenzung_satire_nur_politik_und_macht():
    from cudi_video import videoarten as V

    assert V.satire_ziel("Die Bundesregierung kündigt einen Plan an") and V.satire_ziel("CEO announces layoffs")
    assert not V.satire_ziel("Katzen lieben Kartons", "Ein Hund fand einen Ball")
    assert V.erklaer_frage("Wie funktioniert Photosynthese?") and not V.erklaer_frage("Minister verspricht Internet")
    assert set(V.ABGRENZUNG) >= {"ranking", "fakten", "erklaer", "reportage", "satire", "story", "clip"}


def test_buendeln_zwei_sprachen_in_einer_runde(monkeypatch, tmp_path):
    """DE+EN: Storyboards zusammen, Szenenbauten zusammen – danach kommt alles aus den Aufgabendateien."""
    monkeypatch.setattr(handoff, "enabled", lambda: True)
    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(handoff, "task_file", lambda name: tmp_path / f"schreiben_{name}.json")
    monkeypatch.setattr(handoff, "preferences", lambda: {})
    auftraege = [([{"key": "1", "text": TEXT}], "Ei", "de", "animation_fakten_de"),
                 ([{"key": "1", "text": TEXT}], "Ei", "en", "animation_fakten_en")]
    try:
        animation.buendeln(auftraege)
        raise AssertionError("Bündel erwartet")
    except handoff.WritingNeeded as w:
        datei = w.path
    daten = json.loads(datei.read_text("utf-8"))
    assert set(daten["daten"]) == {"animation_fakten_de_storyboard", "animation_fakten_en_storyboard"}
    sb = {"storyboards": [{"key": "1", "drehbuch": [{"wort": "wandert", "zeigt": "x"}]}]}
    daten["antwort"] = {k: sb for k in daten["daten"]}
    datei.write_text(json.dumps(daten), "utf-8")
    try:
        animation.buendeln(auftraege)
        raise AssertionError("zweites Bündel erwartet")
    except handoff.WritingNeeded as w:
        zweite = json.loads(w.path.read_text("utf-8"))
    assert set(zweite["daten"]) == {"animation_fakten_de", "animation_fakten_en"}
    assert zweite["daten"]["animation_fakten_de"]["daten"]["eintraege"][0]["drehbuch"][0]["wort"] == "wandert"
