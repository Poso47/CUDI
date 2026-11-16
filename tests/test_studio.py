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
    assert schreiben.kernwoerter("Woher kommt die Milch?") == "Milch"          # Probelauf 16.11.: landete bei „Galactose“


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
    pfade, lagen, arbeit = drei.rendere(Z.Buehne(sz, 200, [0.0], (240, 236, 226), (214, 162, 84)), [0.0, 0.2, 4.0], 160)
    im = Image.open(pfade[1])
    assert im.size == (160, 160) and im.getchannel("A").getextrema()[1] > 200
    assert abs(lagen[2]["w"][0] - 80) < 8                      # nach dem Einflug steht die Kamera wieder mittig
    assert abs(lagen[0]["w"][0] - lagen[2]["w"][0]) > 1         # Einflug: die Kamera bewegt sich wirklich
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


def test_glas_fuellstand_aus_prozent_und_kaestchen_weg():
    from cudi_video.schaubild import zeichnen as Z
    roh = {"elemente": [{"id": "g", "art": "form", "form": "quadrat", "streckung": 1.8, "x": 40, "y": 60, "groesse": 20},
                        {"id": "k1", "art": "form", "form": "quadrat", "x": 70, "y": 50, "groesse": 8},
                        {"id": "k2", "art": "form", "form": "quadrat", "x": 70, "y": 70, "groesse": 8},
                        {"id": "l", "art": "beschriftung", "text": "Wassergehalt", "an": "k2"}],
           "schritte": [{"ziel": "k1", "aktion": "erscheine", "ab": 1}]}
    text = "Am Ende liegt der Wassergehalt unter 20 Prozent, meist bei 18 Prozent."
    sz = Z.beschriftungen_pruefen(Z.pruefe_szene(roh), text)
    ids = [e["id"] for e in sz["elemente"]]
    assert "k1" not in ids and "k2" not in ids and sz["schritte"] == []
    glas = next(e for e in sz["elemente"] if e["id"] == "g")
    assert abs(glas["prozent"] - .18) < 1e-9
    assert next(e for e in sz["elemente"] if e["art"] == "beschriftung")["an"] == "g"
    ohne = Z.beschriftungen_pruefen(Z.pruefe_szene(roh), "Der Honig wird dicker und die Bienen trocknen ihn.")
    g2 = [e for e in ohne["elemente"] if e["id"] == "g"]       # ohne genannte Zahl kein Messglas (nichts erfinden):
    assert all("prozent" not in e and not Z.ist_glas(e) for e in g2)   # schlichte Säule oder – ohne passendes Ding – weg


def test_zoom_bleibt_im_bild():
    from cudi_video.schaubild import zeichnen as Z
    sz = Z.pruefe_szene({"elemente": [{"id": "w", "art": "form", "form": "sechseck", "x": 85, "y": 80, "groesse": 60}],
                         "schritte": [{"ziel": "kamera", "aktion": "zoom", "zu": "w", "auf": 3, "ab": 1}]})
    assert sz["schritte"][0]["auf"] <= 80 / 60 + 1e-9
    b = Z.Buehne(sz, 400, [0.0], (240, 236, 226), (214, 162, 84), 0, None)
    k = b.zustand(30)[Z.KAMERA]
    rand = 50 / k["f"]
    assert rand - 1e-6 <= k["x"] <= 100 - rand + 1e-6 and rand - 1e-6 <= k["y"] <= 100 - rand + 1e-6


def test_szene_ohne_animation_zeigt_nachbarbild():
    from cudi_video import animation
    voll = {"elemente": [{"id": "b", "art": "figur", "figur": "biene", "x": 50, "y": 50, "groesse": 40, "alpha": 0.0},
                         {"id": "l", "art": "beschriftung", "text": "Biene", "an": "b", "alpha": 0.0}],
            "schritte": [{"ziel": "b", "aktion": "erscheine"}]}
    szenen = [{"text": "Die Biene fliegt.", "animation": voll}, {"text": "Für Imker ist das ein Zeichen.", "animation": None}]
    notes = []
    animation._luecken_fuellen(szenen, notes)
    neu = szenen[1]["animation"]
    assert neu["schritte"] == [] and all(e["alpha"] == 1.0 for e in neu["elemente"])
    assert not any(e["art"] == "beschriftung" for e in neu["elemente"])      # „Biene“ wird hier nicht gesprochen
    assert voll["schritte"] and notes


def test_grosse_kaesten_werden_dinge_oder_fallen_weg():
    from cudi_video.schaubild import zeichnen as Z
    roh = {"elemente": [{"id": "k", "art": "form", "form": "quadrat", "x": 30, "y": 50, "groesse": 40},
                        {"id": "b", "art": "form", "form": "quadrat", "x": 70, "y": 50, "groesse": 30},
                        {"id": "l", "art": "beschriftung", "text": "Brotaufstrich", "an": "b"}], "schritte": []}
    sz = Z.beschriftungen_pruefen(Z.pruefe_szene(roh), "Honig ist ein beliebter Brotaufstrich.")
    objekte = {e["id"]: e.get("objekt") for e in sz["elemente"] if e["art"] == "form"}
    assert objekte == {"b": "brot"}                           # „k“ ohne passendes Wort fällt weg
    sz2 = Z.beschriftungen_pruefen(Z.pruefe_szene({"elemente": roh["elemente"][:1], "schritte": []}),
                                   "Woher kommt eigentlich der Honig im Glas?")
    assert sz2["elemente"][0]["objekt"] == "honigglas"


def test_satzanfang_adjektiv_ist_kein_hauptwort():
    from cudi_video.schaubild import hauptwoerter
    w = hauptwoerter("Bestimmte Arbeiterbienen sammeln Nektar. Bienen fliegen weit.")
    assert "bestimmte" not in w and {"arbeiterbienen", "nektar", "bienen"} <= set(w)


def test_flacher_kasten_mit_prozent_wird_glas_und_schon_keine_beschriftung():
    from cudi_video.schaubild import hauptwoerter, zeichnen as Z
    sz = Z.beschriftungen_pruefen(Z.pruefe_szene({"elemente": [{"id": "k", "art": "form", "form": "quadrat", "x": 50, "y": 60,
                                                                 "groesse": 40}], "schritte": []}),
                                  "Am Ende liegt der Wassergehalt unter 20 %, meist bei 18 %.")
    k = sz["elemente"][0]
    assert Z.ist_glas(k) and abs(k["prozent"] - .18) < 1e-9
    assert "schon" not in hauptwoerter("Schon bei der Aufnahme kommen Enzyme dazu.")
    html = (Path(Z.__file__).parent / "drei" / "szene3d.html").read_text("utf-8")
    assert "LatheGeometry(pts.reverse()" in html


def test_zitatkarte_ohne_quelle_weicht_der_animation():
    from cudi_video.render import formats
    anim = {"elemente": [{"id": "b", "art": "figur", "figur": "biene", "x": 50, "y": 50, "groesse": 40, "alpha": 1.0, "f": 0,
                          "farbe": (200, 160, 60), "rot": 0}], "schritte": []}
    def job(visual):
        return {"szene": {"text": "Imker nennen das Verdeckeln.", "visual": visual, "animation": anim},
                "words": [], "lead": 0.2, "voice_dur": 2.0, "duration": 3.0, "index": 0}
    ohne = formats.ErklaerScene(job({"typ": "zitatkarte", "zitat": "Imker nennen das Verdeckeln."}))
    assert ohne.quote is None and ohne.anim is not None
    mit = formats.ErklaerScene(job({"typ": "zitatkarte", "zitat": "Ein Zitat", "quelle": "Buch, S. 3"}))
    assert mit.quote is not None                             # echtes Zitat mit Quelle bleibt


def test_kleiner_kasten_mit_schild_wird_honigglas():
    from cudi_video.schaubild import zeichnen as Z
    sz = Z.beschriftungen_pruefen(Z.pruefe_szene({"elemente": [
        {"id": "b", "art": "figur", "figur": "biene", "x": 60, "y": 40, "groesse": 40},
        {"id": "k", "art": "form", "form": "quadrat", "x": 15, "y": 80, "groesse": 8},
        {"id": "l", "art": "beschriftung", "text": "Glas Honig", "an": "k"}], "schritte": []}),
        "Wie wird aus einer Blüte ein Glas Honig?")
    k = next(e for e in sz["elemente"] if e["id"] == "k")
    assert k["objekt"] == "honigglas"


def _imker():
    return {"name": "Gaertner", "teile": [
        {"form": "kapsel", "x": 50, "y": 52, "b": 26, "h": 36, "t": 18, "farbe": "#f1ede2"},
        {"form": "kugel", "x": 50, "y": 24, "b": 17, "h": 18, "t": 17, "farbe": "#e2b48c"},
        {"form": "zylinder", "x": 50, "y": 15, "b": 36, "h": 3, "t": 36, "farbe": "#d9c48a"},
        {"form": "kapsel", "x": 43, "y": 80, "b": 10, "h": 28, "t": 10, "farbe": "#ece7da", "gruppe": "bein"},
        {"form": "kapsel", "x": 57, "y": 80, "b": 10, "h": 28, "t": 10, "farbe": "#ece7da", "gruppe": "bein2"},
        {"form": "kapsel", "x": 31, "y": 52, "b": 8, "h": 28, "t": 8, "farbe": "#f1ede2", "gruppe": "arm"},
        {"form": "kapsel", "x": 70, "y": 50, "b": 8, "h": 26, "t": 8, "farbe": "#f1ede2", "gruppe": "ARM2"},
        {"form": "zylinder", "x": 50, "y": 25, "b": 25, "h": 17, "t": 25, "farbe": "#3a3a36", "gruppe": "kopf"},
        {"form": "kugel", "x": 26, "y": 67, "b": 9, "h": 9, "t": 9, "farbe": "#c9a45c", "gruppe": "tentakel"},
        {"form": "torus", "x": 1, "y": 1}], "anker": {"Hut": [50, 11], "kaputt": "x"}}


def test_werkstatt_baut_nur_nach_crawler_vorlage(tmp_path, monkeypatch):
    from PIL import Image
    from cudi_video import animation, config, handoff
    from cudi_video.schaubild import werkstatt, zeichnen as Z
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(werkstatt, "_neu", [])
    monkeypatch.setenv("CUDI_EIGENBAU", "1")
    monkeypatch.setenv("CUDI_WERKSTATT", "1")
    assert Z.figur_info("gaertner") is None
    assert werkstatt.wunsch("Gaertner (gardener)") == ("gaertner", "Gaertner", "gardener")
    assert werkstatt.pruefe_bauplan({"name": "x", "teile": [{"form": "kugel"}]}) is None      # zu wenige Teile
    bild = tmp_path / "v.jpg"
    Image.new("RGB", (200, 200), (240, 236, 220)).save(bild)
    gesucht = []
    def suche(begriff):
        gesucht.append(begriff)
        return None if begriff == "unicorn" else {"datei": str(bild), "seite": "https://example.org/foto", "quelle": "pexels",
                                                    "lizenz": "Pexels", "urheber": "A", "titel": "gardener", "begriff": begriff,
                                                    "farben": werkstatt.farben(bild)}
    monkeypatch.setattr(werkstatt, "vorlage_suchen", suche)
    monkeypatch.setattr(handoff, "active", lambda: True)
    gestellt = {}
    def request(task, anleitung, daten):
        gestellt.update(task=task, anleitung=anleitung, daten=daten)
        return {"figuren": [_imker(), {"name": "einhorn", "teile": _imker()["teile"]}, {"name": "biene", "teile": _imker()["teile"]}]}
    monkeypatch.setattr(handoff, "request", request)
    monkeypatch.setattr(handoff, "task_file", lambda t: tmp_path / (t + ".json"))
    notes = []
    fertig = werkstatt.bauen(["Gaertner (gardener)", "Einhorn (unicorn)", "Biene (bee)"], "a_figuren", notes)
    assert fertig == ["gaertner"] and gesucht == ["gardener", "unicorn"]                  # Biene gibt es schon: keine Suche
    assert Z.figur_info("einhorn") is None                                             # ohne Fund keine Figur – auch wenn eine geliefert wird
    assert gestellt["daten"]["figuren"][0]["vorlage"] == str(bild) and gestellt["daten"]["figuren"][0]["farben"]
    assert "SIEH SIE DIR ZUERST AN" in gestellt["anleitung"]
    info = Z.figur_info("gaertner")
    assert len(info["bauplan"]) == 9 and set(info["anker"]) == {"hut", "mitte"}       # unbekannte Form/kaputter Anker fliegen raus
    assert [t.get("gruppe") for t in info["bauplan"]][3:] == ["bein", "bein2", "arm", "arm2", "kopf", None]   # nur bekannte Glieder
    assert werkstatt.bauplan("gaertner")["vorlage"]["seite"] == "https://example.org/foto"
    assert Z.figur_info("biene").get("bauplan") is None                                # handgebaute Figur wird nie überschrieben
    assert any("keine Vorlage" in n for n in notes) and any("example.org" in n for n in notes)
    plan = animation.plan_aus([{"key": "1", "text": "Der Gaertner erntet den Honig."}],
                              {"1": {"drehbuch": [{"wort": "Gaertner", "zeigt": "Gaertner"}], "figur_wuensche": ["Gaertner (gardener)", "Kuh (cow)"]}})
    assert plan["1"]["figuren"] == ["gaertner"] and plan["1"]["figur_wuensche"] == ["Kuh (cow)"]
    sz = Z.pruefe_szene({"elemente": [{"id": "i", "art": "figur", "figur": "gaertner", "x": 50, "y": 50, "groesse": 50}], "schritte": []})
    from cudi_video.schaubild import drei
    assert drei.elemente(Z.Buehne(sz, 200, [0.0], (240, 236, 226), (214, 162, 84), 0, None))[0]["bauplan"]
    assert werkstatt.zeichne(info["bauplan"], 64, 1.0).getbbox() is not None
    assert werkstatt.aufnehmen([_imker()], set()) == []                                # ohne Vorlagen-Angabe nichts aufnehmen


def test_werkstatt_figuren_bleiben_im_lernstand(tmp_path, monkeypatch):
    from cudi_video import animation, config
    from cudi_video.schaubild import werkstatt, zeichnen as Z
    monkeypatch.setenv("CUDI_EIGENBAU", "1")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "a")
    werkstatt.aufnehmen([_imker()], set(), {"gaertner": {"seite": "https://example.org/f", "quelle": "pexels"}})
    stand = {"figuren": werkstatt.alle()}
    assert stand["figuren"]["gaertner"]["vorlage"]["quelle"] == "pexels"
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "b")                           # neuer Lauf, leere Ablage
    assert Z.figur_info("gaertner") is None
    datei = tmp_path / "lernstand.json"
    datei.write_text(__import__("json").dumps(stand), "utf-8")
    monkeypatch.setattr(animation, "lernstand_datei", lambda: datei)
    assert Z.figur_info("gaertner")["bauplan"] and "gaertner" in Z.figuren()
    assert "deutsch (englisch)" in animation.storyboard_anleitung("Bienen") and "{figur_bau}" not in animation.storyboard_anleitung("Bienen")


def test_3d_abnahme_meldet_flache_szenen(tmp_path, monkeypatch):
    from cudi_video import config
    from cudi_video.schaubild import drei
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    assert drei.abnahme() == []
    drei.protokoll(True); drei.protokoll(True)
    assert drei.abnahme() == ["3D-Abnahme: alle 2 animierten Szenen in echtem 3D."] and drei.abnahme() == []
    drei.protokoll(True); drei.protokoll(False, "Chromium abgestürzt")
    h = drei.abnahme()
    assert "NICHT vollständig" in h[0] and "1 von 2" in h[0] and "Chromium" in h[0]
    html = (drei.ORDNER / "szene3d.html").read_text("utf-8")
    assert "glieder" in html and 'gl.art === "arm"' in html


def test_schreibaufgabe_kaputte_antwort_wird_einmal_neu_gestellt(tmp_path, monkeypatch):
    import json as _json
    import pytest
    from cudi_video import handoff
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    monkeypatch.setattr(handoff, "enabled", lambda: True)
    monkeypatch.setattr(handoff, "preferences", lambda: None)
    with pytest.raises(handoff.WritingNeeded):
        handoff.request("probe", "Schreibe.", {"a": 1})
    datei = handoff.task_file("probe")
    datei.write_text('{"aufgabe": "probe", "antwort": {"text": "er sagte "hallo""}}', "utf-8")     # ungültiges JSON
    with pytest.raises(handoff.WritingNeeded):
        handoff.request("probe", "Schreibe.", {"a": 1})
    neu = _json.loads(datei.read_text("utf-8"))
    assert "ZWEITER VERSUCH" in neu["anleitung"] and neu["daten"] == {"a": 1} and neu["antwort"] is None
    datei.write_text("kaputt", "utf-8")
    assert handoff.request("probe", "Schreibe.", {"a": 1}) is None                                 # nur EIN zweiter Versuch
    neu["antwort"] = '{"szenen": [1]}'                                                              # Antwort als JSON-Text
    datei.write_text(_json.dumps(neu), "utf-8")
    assert handoff.request("probe", "Schreibe.", {"a": 1}) == {"szenen": [1]}


def test_kamera_regie_bibliotheken_und_weiche_blende():
    from cudi_video.render import manuskript as M
    from cudi_video.schaubild import drei
    three = drei.THREE.parent
    assert (three / "camera-controls.js").read_text("utf-8").rstrip().endswith("window.CameraControls=exports.default;})();")
    assert "Easing" in (three / "tween.umd.js").read_text("utf-8")
    html = (drei.ORDNER / "szene3d.html").read_text("utf-8")
    assert "regie.setLookAt" in html and "TWEEN.Easing" in html and "camera-controls.js" in html
    assert M.fade_in_out(0, 5) == 0 and M.fade_in_out(2.5, 5) == 1
    assert M.fade_in_out(.125, 5, .5, .5) < .25                 # weich: langsamer Anlauf als linear


def test_erklaer_szenen_gehen_mit_uebergang_ineinander(tmp_path, monkeypatch):
    import shutil
    import subprocess

    import pytest

    from cudi_video.erklaer import render as R
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg fehlt")
    assert R.UEBERGANG < R.LEAD and R.UEBERGANG < R.TAIL          # Stimmen zweier Szenen überlappen nie
    jobs = []
    for i, farbe in enumerate(("red", "green", "blue")):
        out = tmp_path / f"part_{i:02d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color={farbe}:s=108x192:r=30:d=2", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(out)], check=True)
        jobs.append({"out": str(out), "duration": 2.0, "fps": 30, "uebergang": True, "lead": R.LEAD})
    assert R.start_zeiten(jobs) == [0.0, 1.5, 3.0]
    assert R.verbinden(jobs, tmp_path / "film.mp4", tmp_path) == "xfade"
    laenge = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                   str(tmp_path / "film.mp4")], capture_output=True, text=True).stdout)
    assert abs(laenge - 5.0) < .15                                # 3 × 2 s minus 2 Übergänge
    monkeypatch.setenv("CUDI_UEBERGAENGE", "0")
    assert not R.uebergaenge_aktiv(5)
    for j in jobs:
        j["uebergang"] = False
    assert R.start_zeiten(jobs) == [0.0, 2.0, 4.0] and R.verbinden(jobs, tmp_path / "hart.mp4", tmp_path) == "schnitt"


def test_modell_scout_fertiges_modell_vor_eigenbau(tmp_path, monkeypatch):
    from cudi_video import config, handoff, job
    from cudi_video.schaubild import drei, modelle, werkstatt, zeichnen as Z
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(werkstatt, "_neu", [])
    monkeypatch.setenv("CUDI_WERKSTATT", "1")
    monkeypatch.setenv("CUDI_MODELLE", "1")
    kats = {"cow": 1, "chicken_(animal)": 1, "jar": 1}
    assert modelle.kategorie("cows", kats) == "cow" and modelle.kategorie("Chicken", kats) == "chicken_(animal)"
    assert modelle.kategorie("gardener", kats) is None
    glb = tmp_path / "kuh.glb"
    glb.write_bytes(b"glTF" + b"0" * 2000)
    fund = {"datei": str(glb), "url": modelle.BASIS + "/glbs/000-001/abc.glb", "lizenz": "CC BY 4.0", "urheber": "erika",
            "titel": "Cow", "seite": "https://sketchfab.com/3d-models/abc", "quelle": "objaverse/sketchfab", "begriff": "cow"}
    monkeypatch.setattr(modelle, "kandidaten", lambda b, anzahl=4: [dict(fund, titel="Falsch"), fund] if b == "cow" else [])
    monkeypatch.setattr(modelle, "sichtpruefung", lambda k: None if k["titel"] == "Falsch" else dict(k, dreh=90, skala=.8, sicher=.9))
    monkeypatch.setattr(werkstatt, "vorlage_suchen", lambda b: None)
    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(handoff, "task_file", lambda t: tmp_path / (t + ".json"))
    notes = []
    assert werkstatt.bauen(["Kuh (cow)", "Gaertner (gardener)"], "a_figuren", notes) == ["kuh"]   # keine Schreibaufgabe nötig
    info = Z.figur_info("kuh")
    assert info["modell"] == str(glb) and info["dreh"] == 90 and info["skala"] == .8
    assert any("fertiges freies 3D-Modell" in n and "erika" in n for n in notes)
    sz = Z.pruefe_szene({"elemente": [{"id": "k", "art": "figur", "figur": "kuh", "x": 50, "y": 50, "groesse": 50}], "schritte": []})
    el = drei.elemente(Z.Buehne(sz, 200, [0.0], (240, 236, 226), (214, 162, 84), 0, None))[0]
    assert el["modell"] == str(glb) and el["modell_dreh"] == 90
    assert werkstatt.alle()["kuh"]["modell_url"].endswith("abc.glb") and "modell" not in werkstatt.alle()["kuh"]
    text = job._mit_nennung("Titel\\n\\nBeschreibung")
    assert "3D-Modell „Cow“ von erika (CC BY 4.0)" in text and job._mit_nennung(text) == text
    html = (drei.ORDNER / "szene3d.html").read_text("utf-8")
    assert "GLTFLoader" in html and "ausModell" in html and (drei.THREE.parent / "GLTFLoader.js").exists()


def test_kein_gepuzzelter_eigenbau_im_lauf(tmp_path, monkeypatch):
    from cudi_video import config, handoff
    from cudi_video.schaubild import werkstatt, zeichnen as Z
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("CUDI_WERKSTATT", "1")
    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(handoff, "task_file", lambda t: tmp_path / (t + ".json"))
    monkeypatch.setattr(handoff, "request", lambda *a: (_ for _ in ()).throw(AssertionError("keine Bau-Aufgabe erwartet")))
    monkeypatch.setattr(werkstatt, "vorlage_suchen", lambda b: (_ for _ in ()).throw(AssertionError("keine Suche erwartet")))
    notes = []
    assert not werkstatt.eigenbau_aktiv()
    assert werkstatt.bauen(["Gaertner (gardener)"], "a_figuren", notes) == [] and Z.figur_info("gaertner") is None
    werkstatt.ordner().mkdir(parents=True, exist_ok=True)       # früher gepuzzelte Figur (z. B. aus dem Lernstand) zählt nicht mehr
    (werkstatt.ordner() / "gaertner.json").write_text(__import__("json").dumps(dict(_imker(), name="gaertner")), "utf-8")
    assert Z.figur_info("gaertner") is None and "gaertner" not in Z.figuren()
    assert any("Wunschliste" in n and "Gaertner" in n for n in notes)


def test_imker_ist_handgebaute_detailfigur():
    from cudi_video.schaubild import drei, werkstatt, zeichnen as Z
    info = Z.figur_info("imker")
    assert info and not info.get("bauplan") and {"schleier", "wabenrahmen", "handschuhe"} <= set(info["anker"])
    html = (drei.ORDNER / "szene3d.html").read_text("utf-8")
    assert "imker() {" in html and "gaze()" in html and "wabenbild()" in html
    assert not werkstatt.modelle_aktiv()                         # fremde Modelle nur als Vorlage, nie im Video
    sz = Z.pruefe_szene({"elemente": [{"id": "i", "art": "figur", "figur": "Imker", "x": 50, "y": 50, "groesse": 60},
                                      {"id": "l", "art": "beschriftung", "text": "Schleier", "an": "i"}], "schritte": []})
    assert sz and Z.Buehne(sz, 120, [0.0], (240, 236, 226), (214, 162, 84), 0, None).bild(1.0).size == (120, 120)


def test_erklaer_nur_bis_zur_skizze_und_freigabe(tmp_path, monkeypatch):
    from cudi_video import animation, handoff, job
    from cudi_video.schaubild import zeichnen as Z
    o = job.parse_order({"art": "erklaer", "id": "pskizze01", "thema": "Bienen", "schritt": "skizze", "feedback": "Szene 2 näher zeigen"}, {})
    assert o["schritt"] == "skizze" and o["feedback"] == "Szene 2 näher zeigen"
    assert job.parse_order({"art": "erklaer", "id": "pskizze01", "thema": "Bienen", "schritt": "video"}, {})["schritt"] == "video"
    sz = Z.pruefe_szene({"elemente": [{"id": "b", "art": "figur", "figur": "biene", "x": 50, "y": 50, "groesse": 50}], "schritte": []})
    skript = {"titel": "Bienen", "szenen": [{"text": "Die Biene fliegt los.", "animation": sz}, {"text": "Ohne Bild.", "animation": None}]}
    bogen = animation.skizzenbogen(skript, tmp_path / "skizze.jpg")
    with Image.open(bogen) as im:
        assert im.size == (1080, 60 + 510)
    daten = {"id": "t1", "art": "erklaer", "ok": True, "videos": [], "schritt": "skizze",
             "skizze": {"bild": str(bogen), "titel": "Bienen", "antworten": {"erklaer": {"szenen": [1]}}, "fehlende_figuren": ["Imker"],
                        "szenen": [{"nr": 1, "text": "x", "mit_bild": True}]}}
    assert job.uploads(daten) == [str(bogen)]
    (tmp_path / "ergebnis.json").write_text(__import__("json").dumps(daten), "utf-8")
    doc = job.document(tmp_path, {str(bogen): "/_blob/" + "a" * 32})
    assert doc["schritt"] == "skizze" and doc["skizze"]["bild_url"].endswith("a" * 32) and "bild" not in doc["skizze"]
    assert doc["skizze"]["antworten"] == {"erklaer": {"szenen": [1]}} and doc["ok"]
    assert "rueckmeldung_zur_skizze" in handoff.PREFS_NOTE
    app = (Path(job.__file__).resolve().parent.parent / "docs" / "cudi-app-artefakt.html").read_text("utf-8")
    assert "function skizzeKarte" in app and 'schritt: "skizze"' in app


def test_bienenstock_und_honigglas_sind_detailfiguren():
    from cudi_video.schaubild import drei, zeichnen as Z
    html = (drei.ORDNER / "szene3d.html").read_text("utf-8")
    for name, anker in (("bienenstock", {"flugloch", "honigraum", "deckel"}), ("honigglas", {"deckel", "etikett", "loeffel"})):
        info = Z.figur_info(name)
        assert info and not info.get("bauplan") and anker <= set(info["anker"])
        assert f"  {name}() {{" in html
    assert "kleineBiene()" in html and "o.teile.schwarm" in html


PILZ = """const g = new T.Group(), teile = {};
const hut = kugel(.2, mat([196, 30, 28]), 200, 210, 0, 1, .7, 1); g.add(hut); teile.kopf = hut;
g.add(kugel(.09, mat([236, 226, 200], { map: fell("#ece2c8") }), 200, 290, 0, 1, 2, 1));
return { g, teile, glieder: [] };"""


def test_figurenbau_pruefung_ablage_und_laden(tmp_path, monkeypatch):
    from cudi_video import config
    from cudi_video.schaubild import drei, figurenbau as F, zeichnen as Z
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(animation, "lernstand_datei", lambda: tmp_path / "alt.json")
    (tmp_path / "alt.json").write_text(json.dumps({"regeln": [{"regel": "r", "faelle": 2}]}), "utf-8")
    assert F.pruefe_code(PILZ) is None
    assert "fetch" in F.pruefe_code(PILZ + "\nfetch('x');")
    assert "return" in F.pruefe_code("const g = 1;")
    assert F.pruefe_anker({"hut": [200, 200], "stiel": [200, 290]})[1]
    assert not F.pruefe_anker({"hut": [200, 200], "stiel": [200, 290], "rand": [300, 230]})[1]
    assert F.pruefe_anker({"a": [500, 1], "b": [1, 1], "c": [2, 2]})[1]          # außerhalb 0–400 zählt nicht
    assert Z.figur_info("Pilz") is None
    ziel = F.ablegen("Pilz", PILZ, {"hut": [200, 200], "stiel": [200, 290], "rand": [300, 230]}, "Pilz", pruefen=False)
    daten = json.loads(ziel.read_text("utf-8"))
    assert daten["regeln"] and "pilz" in daten["figuren_code"]                    # alter Lernstand bleibt erhalten
    info = Z.figur_info("Pilz")
    assert info["code"] == PILZ and info["nur3d"] and set(info["anker"]) == {"hut", "stiel", "rand"}
    assert "pilz" in Z.figuren()

    class B:
        order = ["p"]
        el = {"p": {"art": "figur", "figur": "pilz", "farbe": (1, 2, 3), "f": 0}}
    assert drei.elemente(B())[0]["figur_code"] == PILZ
    html = (drei.ORDNER / "szene3d.html").read_text("utf-8")
    assert "function ausCode" in html and "new Function(code)" in html
    doc = json.loads(F.bericht("t1", {}, ["Zwerg: keine Vorlage"]).read_text("utf-8"))
    assert doc["gebaut"][0]["name"] == "pilz" and not doc["ok"] and doc["offen"]
    # ein Video-Lauf gibt die gebauten Figuren beim Zurückschreiben weiter
    (tmp_path / "lauf").mkdir()
    (tmp_path / "lauf" / "abgleich.json").write_text(json.dumps({"art": "erklaer", "abschnitte": [{"maengel": []}]}), "utf-8")
    neu = animation.lernstand_aktualisieren(tmp_path / "lauf")
    assert "pilz" in json.loads(neu.read_text("utf-8"))["figuren_code"]
    app = (Path(animation.__file__).resolve().parent.parent / "docs" / "cudi-app-artefakt.html").read_text("utf-8")
    assert "figurPruefen" in app and "figurAufgabe" in app and 'id="figurPrompt"' in app


def test_figurenbau_probe_rendert_und_meldet_fehler(tmp_path, monkeypatch):
    import shutil
    import pytest
    from cudi_video import config
    from cudi_video.schaubild import figurenbau as F
    if not shutil.which("node"):
        pytest.skip("ohne node kein 3D")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    try:
        bild = F.probe("pilz", PILZ, {"hut": [200, 200], "stiel": [200, 290], "rand": [300, 230]}, size=160)
    except RuntimeError as err:
        if "Cannot find module" in str(err) or "Executable" in str(err):
            pytest.skip("ohne Playwright/Chromium kein 3D")
        raise
    with Image.open(bild) as im:
        assert im.size == (800, 160 * 2 + 34)                                        # 7 Ansichten inkl. Nahaufnahme Kopf
    stand = F.probe_stand("pilz")
    assert stand["runden"] == 1 and stand["stats"]["teile"] >= 2 and stand["maengel"]   # Pilz ist viel zu einfach
    anker = {"hut": [200, 200], "stiel": [200, 290], "rand": [300, 230]}
    with pytest.raises(ValueError, match="Probe-Runde"):
        F.ablegen("pilz", PILZ, anker)
    with pytest.raises(ValueError, match="geprobt"):
        F.ablegen("pilz", PILZ + "\n// geändert", anker)
    stand.update(runden=3)
    (tmp_path / "figurenbau" / "proben" / "pilz.json").write_text(json.dumps(stand), "utf-8")
    with pytest.raises(ValueError, match="Detailgrad"):
        F.ablegen("pilz", PILZ, anker)
    html = (Path(F.__file__).parent / "drei" / "szene3d.html").read_text("utf-8")
    assert all(f"function {h}(" in html for h in ("organ", "koerper", "fellmat", "hautmat", "auge"))
    with pytest.raises(RuntimeError, match="nichtDa"):
        F.probe("kaputt", "nichtDa(); const g = new T.Group(); return { g };", size=120)


def test_profi_modell_als_figur_mit_anker_und_nennung(tmp_path, monkeypatch):
    from cudi_video import config
    from cudi_video.schaubild import drei, figurenbau as F, werkstatt, zeichnen as Z
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(animation, "lernstand_datei", lambda: tmp_path / "alt.json")
    glb = tmp_path / "kuh.glb"
    glb.write_bytes(b"glTF" + b"\0" * 2000)
    (tmp_path / "alt.json").write_text(json.dumps({"figuren_code": {"kuh": {"code": PILZ, "anker": {}}}}), "utf-8")
    (tmp_path / "figurenbau" / "modelle").mkdir(parents=True)
    (tmp_path / "figurenbau" / "modelle" / "kuh.json").write_text(json.dumps({"anzeige": "Kuh", "modelle": [
        {"nr": 1, "datei": str(glb), "url": "https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/x/kuh.glb",
         "lizenz": "CC BY 4.0", "urheber": "jemand", "titel": "Cow", "seite": "https://sketchfab.com/3d-models/x", "skala": 1.2}]}), "utf-8")
    anker = {"kopf": [330, 150], "euter": [200, 250], "schwanz": [85, 175]}
    import pytest
    with pytest.raises(ValueError, match="probe"):
        F.modell_ablegen("Kuh", 1, anker, dreh=90)
    (tmp_path / "figurenbau" / "proben").mkdir(parents=True)
    (tmp_path / "figurenbau" / "proben" / "kuh.json").write_text(json.dumps({"runden": 1}), "utf-8")
    ziel = F.modell_ablegen("Kuh", 1, anker, dreh=90, boden_weg=True)
    daten = json.loads(ziel.read_text("utf-8"))
    assert "kuh" in daten["figuren"] and "kuh" not in daten.get("figuren_code", {})        # Profi-Modell ersetzt den Eigenbau
    info = Z.figur_info("Kuh")
    assert info["modell"] == str(glb) and info["boden_weg"] and info["dreh"] == 90
    assert info["anker"]["kopf"] == [330.0, 150.0]                                          # 0–100 gespeichert, 0–400 zurück
    werkstatt._genutzt.clear()

    class B:
        order = ["k"]
        el = {"k": {"art": "figur", "figur": "kuh", "farbe": (1, 2, 3), "f": 0}}
    d = drei.elemente(B())[0]
    assert d["modell_boden_weg"] and d["modell_dreh"] == 90
    assert any("jemand" in n and "CC BY" in n for n in werkstatt.nennungen())
    assert F.gebaut() == ["kuh"]
    html = (drei.ORDNER / "szene3d.html").read_text("utf-8")
    assert "function huelle" in html and "function bodenWeg" in html and "boneTransform" in html


def test_schritt_auf_entferntes_element_zerstoert_die_szene_nicht():
    """Probelauf 16.11.: Beschriftung beim Anker-Auflösen entfernt, ihr Schritt blieb -> KeyError, 6 von 7 Skizzen-Szenen leer."""
    from cudi_video.schaubild import zeichnen as Z
    sz = Z.pruefe_szene({"elemente": [{"id": "k", "art": "form", "form": "kreis", "x": 50, "y": 50, "groesse": 30}],
                         "schritte": [{"aktion": "erscheine", "ziel": "k", "dauer": 1}]})
    ok = dict(sz["schritte"][0])
    sz["schritte"] = [dict(ok, ziel="weg"), dict(ok, aktion="bewege", zu="auch_weg"), ok]
    b = Z.Buehne(sz, 120, [0.0], (236, 228, 210), (214, 162, 84))
    assert [s["ziel"] for s in b.schritte] == ["k"]
    assert b.bild(2.0).size == (120, 120)
