"""Animationsstudio: Abteilungen Storyboard → Figuren → Szenenbau → Abnahme, Lehrer, Einbau in die Videoarten."""

import json
from pathlib import Path

from PIL import Image

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


def test_app_lauf_lernt_ueber_lernstand(monkeypatch, tmp_path):
    """App-Lauf: Lücken -> lernstand.json (Sitzung legt sie in „studio/lernstand“ ab); der nächste Lauf liest die Regeln."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("cudi_video.config.LLM_BASE_URL", "")
    monkeypatch.setattr(animation, "REGELN_DATEI", tmp_path / "fehlt.json")
    lauf = tmp_path / "auftrag-x" / "fakten"
    lauf.mkdir(parents=True)
    (lauf / "abgleich.json").write_text(json.dumps({"art": "fakten", "abschnitte": [
        {"key": str(i), "maengel": ["„Eileiter“ wird gesagt, aber nicht gezeigt"]} for i in range(3)]}), "utf-8")
    ziel = animation.lernstand_aktualisieren(tmp_path / "auftrag-x")
    daten = json.loads(ziel.read_text("utf-8"))
    assert daten["abschnitte_n"] == 3 and daten["regeln"]
    ablage = tmp_path / "cudi_studio" / "studio"
    ablage.mkdir(parents=True)
    (ablage / "lernstand.json").write_text(json.dumps({"data": daten}), "utf-8")
    assert any("eileiter" in r for r in animation.gelernte_regeln())
    assert animation.lernstand_aktualisieren(tmp_path / "leer") is None


def test_storyboard_mit_dem_text_spart_eine_runde(monkeypatch):
    """Kommt das Drehbuch schon mit dem Text (Erklär/Reportage), entfällt die eigene Storyboard-Runde."""
    aufrufe = []
    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(handoff, "request", lambda task, *a: aufrufe.append(task) or {"szenen": [{"key": "1", "szene": SZENE}]})
    assert "STORYBOARD-ABTEILUNG" in animation.storyboard_zusatz()
    vorab = {"1": {"drehbuch": [{"wort": "wandert", "zeigt": "Dotter gleitet"}], "figuren": ["huhn"]}}
    szenen, abgleich = animation.szenen_schreiben([{"key": "1", "text": TEXT}], "Ei", "de", [], "animation_erklaer", vorab)
    assert aufrufe == ["animation_erklaer"] and abgleich[0]["drehbuch"][0]["wort"] == "wandert"
    aufrufe.clear()                                                    # zu dünn -> eigene Storyboard-Runde
    animation.szenen_schreiben([{"key": "1", "text": TEXT}], "Ei", "de", [], "animation_erklaer", {"1": {}})
    assert aufrufe[0] == "animation_erklaer_storyboard"
    monkeypatch.setenv("CUDI_STUDIO", "0")
    assert animation.storyboard_zusatz() == ""


def test_erklaer_suchkern_aus_fragen():
    from cudi_video.erklaer import schreiben

    assert schreiben.kernwoerter("Wie Bienen Honig machen") == "Bienen Honig"
    assert schreiben.kernwoerter("Warum ist der Himmel blau?") == "Himmel blau"


def test_storyboard_aufgaben_zum_buendeln(monkeypatch):
    """Fakten: Storyboard-Aufgaben lassen sich mit Titel und Regie in EINE Runde legen."""
    monkeypatch.setattr(handoff, "active", lambda: True)
    aufgaben = animation.storyboard_aufgaben([([{"key": "1", "text": TEXT}], "Ei", "de", "animation_fakten_de"),
                                              ([], "Ei", "en", "animation_fakten_en")])
    assert [a[0] for a in aufgaben] == ["animation_fakten_de_storyboard"] and "Storyboard-Abteilung" in aufgaben[0][1]
    monkeypatch.setattr(handoff, "active", lambda: False)
    assert animation.storyboard_aufgaben([([{"key": "1", "text": TEXT}], "Ei", "de", "x")]) == []


def test_szene_fuellt_das_bild_und_ist_nie_leer():
    from cudi_video.schaubild import zeichnen as Z

    sz = Z.pruefe_szene({"elemente": [{"id": "a", "art": "form", "x": 45, "y": 45, "groesse": 8, "sichtbar": False},
                                      {"id": "b", "art": "form", "x": 55, "y": 55, "groesse": 8, "sichtbar": False}], "schritte": []})
    a, b = sz["elemente"]
    assert a["alpha"] == 1.0 and b["alpha"] == 0.0                     # Grundbild sofort sichtbar
    assert a["groesse"] > 8 and b["x"] - a["x"] > 10                     # um die Mitte vergrößert


def test_figur_biene():
    from cudi_video.schaubild import zeichnen as Z

    info = Z.figuren()["biene"]
    assert {"honigblase", "ruessel", "stachel", "pollen", "fluegel"} <= set(info["anker"])


def test_figur_bluete_und_beschriftungen_entzerrt():
    from cudi_video.schaubild import zeichnen as Z

    assert {"nektar", "pollen", "stempel", "bluetenblatt", "stiel"} <= set(Z.figuren()["bluete"]["anker"])
    text = "Rüssel Nektar Pollen Beinen Blüte Biene"
    sz = Z.beschriftungen_pruefen(Z.pruefe_szene({"elemente": [{"id": "b", "art": "form", "x": 50, "y": 50, "groesse": 20}]
        + [{"id": f"l{i}", "art": "beschriftung", "text": w, "an": "b"} for i, w in enumerate(text.split())], "schritte": []}), text)
    buehne = Z.Buehne(sz, 400, [0.0], (240, 236, 226), (214, 162, 84), 0, lambda w: None)
    belegt = []
    for e in sz["elemente"]:
        if e["art"] == "beschriftung":
            buehne._beschrifte(Image.new("RGBA", (400, 400)), e, {"x": 50, "y": 50, "g": 20, "alpha": 1}, sz["elemente"][0], 1, 1, 0, 0, belegt)
    for i, (ax, ay, aw, ah) in enumerate(belegt):                      # keine zwei Beschriftungen überlappen
        for bx, by, bw, bh in belegt[i + 1:]:
            assert not (ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah)


def test_beschriftungen_nur_an_dingen_und_figurnamen_mit_umlaut():
    from cudi_video.schaubild import zeichnen as Z

    text = "Schon beim Aufnehmen kommen spaltende Enzyme dazu. Die Biene speichert den Nektar."
    sz = Z.beschriftungen_pruefen(Z.pruefe_szene({"elemente": [{"id": "b", "art": "figur", "figur": "Blüte"}]
        + [{"id": f"l{i}", "art": "beschriftung", "text": w, "an": "b"} for i, w in enumerate(
            ["schon", "Aufnehmen", "spaltende", "Enzyme", "Biene", "Nektar"])], "schritte": []}), text)
    assert sz["elemente"][0]["figur"] == "bluete"
    assert [e["text"] for e in sz["elemente"] if e["art"] == "beschriftung"] == ["Aufnehmen", "Enzyme", "Biene", "Nektar"]
    assert Z.figur_name("Blüte") == "bluete" and Z.figur_info("Blüte")


def test_3d_buehne_zustaende_und_rueckfall(monkeypatch):
    """3D: Python liefert Zustände je Bild; ohne Node/3D zeichnet Bild in 2D weiter (nie ein Abbruch)."""
    from cudi_video.schaubild import drei, zeichnen as Z

    sz = Z.pruefe_szene({"elemente": [{"id": "b", "art": "figur", "figur": "biene", "x": 50, "y": 50, "groesse": 60},
                                      {"id": "n", "art": "form", "form": "tropfen", "x": "b.ruessel", "y": "b.ruessel", "groesse": 6}],
                         "schritte": [{"ab": 1, "ziel": "b", "aktion": "flattere", "dauer": 1}]})
    buehne = Z.Buehne(sz, 200, [0.0], (240, 236, 226), (214, 162, 84))
    el = drei.elemente(buehne)
    assert [e["id"] for e in el] == ["b", "n"] and el[0]["figur"] == "biene" and isinstance(el[1]["farbe"], list)
    zs = drei.zustaende(buehne, [0.0, 0.5])
    assert zs[1]["st"]["b"]["flattere"] > 0 and zs[0]["kamera"]["f"] == 1.0
    monkeypatch.setattr(drei, "rendere", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kein Chromium")))
    monkeypatch.setenv("CUDI_3D", "1")
    bild = animation.Bild(sz, TEXT, [], 0.2, (240, 236, 226), (214, 162, 84), dauer=1.0)
    assert bild.bild(0.3, 200).size == (200, 200) and "2D" in bild.hinweis


def test_3d_buehne_rendert_echt(monkeypatch):
    """Echter 3D-Lauf im eingebauten Chromium (übersprungen, wo Node/Playwright fehlen)."""
    import shutil
    import subprocess

    import pytest

    from cudi_video.schaubild import drei, zeichnen as Z
    if not shutil.which("node") or subprocess.run(["node", "-e", "require('playwright')"], capture_output=True).returncode:
        pytest.skip("Node/Playwright fehlt")
    sz = Z.pruefe_szene({"elemente": [{"id": "bl", "art": "figur", "figur": "bluete", "x": 50, "y": 55, "groesse": 70},
                                      {"id": "w", "art": "form", "form": "sechseck", "farbe": "gold", "x": 80, "y": 80, "groesse": 15}],
                         "schritte": []})
    pfade, lagen, arbeit = drei.rendere(Z.Buehne(sz, 200, [0.0], (240, 236, 226), (214, 162, 84)), [0.0, 0.2], 160)
    im = Image.open(pfade[1])
    assert im.size == (160, 160) and im.getchannel("A").getextrema()[1] > 200 and abs(lagen[0]["w"][0] - 80) < 6
    shutil.rmtree(arbeit, ignore_errors=True)


def test_referenz_scout_bewertet_ohne_netz(monkeypatch, tmp_path):
    """Crawler: Quellen einzeln abgesichert, scharfe/passende Vorlagen gewinnen, Doppel fliegen raus."""
    import numpy as np

    from cudi_video import net, referenzen

    scharf = Image.fromarray((np.indices((300, 300)).sum(0) % 2 * 255).astype("uint8")).convert("RGB")
    weich = Image.new("RGB", (300, 300), (120, 110, 90))
    (tmp_path / "a.jpg").parent.mkdir(exist_ok=True)
    scharf.save(tmp_path / "a.jpg"); weich.save(tmp_path / "b.jpg")
    liste = [{"bild": "a", "titel": "honey bee macro", "schlagworte": ["bee"], "breite": 4000, "hoehe": 3000, "quelle": "x", "lizenz": "cc0"},
             {"bild": "b", "titel": "landscape", "schlagworte": [], "breite": 800, "hoehe": 600, "quelle": "y", "lizenz": "cc0"},
             {"bild": "a", "titel": "honey bee macro", "schlagworte": ["bee"], "breite": 4000, "hoehe": 3000, "quelle": "x", "lizenz": "cc0"}]
    monkeypatch.setattr(net, "download", lambda url, **k: tmp_path / f"{url}.jpg")
    beste = referenzen.bewerten("honey bee", liste)
    assert len(beste) == 2 and beste[0]["titel"] == "honey bee macro"
    monkeypatch.setattr(referenzen, "QUELLEN", (lambda b, n: (_ for _ in ()).throw(RuntimeError("weg")), lambda b, n: liste[:1]))
    gefunden, hinweise = referenzen.kandidaten("honey bee")
    assert len(gefunden) == 1 and hinweise


def test_leere_dinge_schritte_und_3d_bausteine():
    from cudi_video.schaubild import zeichnen
    assert {"schritt", "schritten"} <= zeichnen.LEERE_DINGE
    html = (Path(zeichnen.__file__).parent / "drei" / "szene3d.html").read_text("utf-8")
    for teil in ("function wabe()", "function glas(", "function blatttextur()", "function federn("):
        assert teil in html
    assert "sheen" not in html                       # r128: sheen braucht eine Farbe, Zahl bricht WebGL
