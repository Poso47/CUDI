"""Satire (ohne Netz, ohne Stimme): Kennzeichnung, Zitat-Sperre, heikle Themen, geprüfter Fakt-Teil, Auftrag."""

import json

import pytest

from cudi_video import job, satire as S
from cudi_video.firma import ideen
from cudi_video.satire import render as R

NEWS = {"meldungen": [
    {"titel": "Trump offers White House press secretary role to Dana White", "kurz": "", "link": "https://www.dw.com/en/a/1",
     "quelle": "Deutsche Welle (en)", "sprache": "en", "status": "bestätigt", "n_quellen": 2,
     "quellen": [{"quelle": "Deutsche Welle (en)", "titel": "Trump offers White House press secretary role to Dana White",
                  "link": "https://www.dw.com/en/a/1"},
                 {"quelle": "NPR", "titel": "UFC's Dana White says he will meet with Trump Monday over the offer",
                  "link": "https://www.npr.org/2026/11/08/x"}]},
    {"titel": "Gunman kills 6 in Krakow", "kurz": "", "link": "https://www.bbc.co.uk/n/1", "quelle": "BBC", "sprache": "en",
     "status": "bestätigt", "n_quellen": 2,
     "quellen": [{"quelle": "BBC", "titel": "Gunman kills 6 in Krakow", "link": "https://www.bbc.co.uk/n/1"},
                 {"quelle": "AP", "titel": "Six killed in Krakow shooting", "link": "https://apnews.com/n/2"}]}]}


@pytest.fixture()
def daten(tmp_path, monkeypatch):
    (tmp_path / "news.json").write_text(json.dumps(NEWS), "utf-8")
    monkeypatch.setenv("CUDI_FIRMA_DATEN", str(tmp_path))
    from cudi_video import handoff
    monkeypatch.setattr(handoff, "request", lambda *a, **k: None)
    return tmp_path


def fakten_geprueft():
    return S.pruefe_fakten({"fakten": S.regel_fakt(quellen())}, quellen(), "en")[0]


def quellen():
    q, _, _ = S.sammle("Trump offers White House press secretary role to Dana White", [])
    return q


# --------------------------------------------------------------------------- Regeln

def test_satire_signal_pflicht():
    assert S.pruefe_satire("Man stelle sich vor, dazu gäbe es sofort einen Ausschuss.", "", "de")[0]
    ok, why = S.pruefe_satire("Dazu gibt es sofort einen Ausschuss mit drei Unterausschüssen.", "", "de")
    assert ok is None and "Signal" in why


@pytest.mark.parametrize("text", [
    'Angeblich rief er „Das ist mein Land“ in die Menge.',                 # erfundenes Zitat
    'Allegedly he shouted "this is my country" at the crowd.',
    "Angeblich sagte der Minister, er habe nichts gewusst.",              # Zuschreibung
    "Allegedly the minister said he knew nothing.",
    "Man stelle sich vor, laut Experten würde alles besser.",
])
def test_keine_erfundenen_zitate(text):
    ok, why = S.pruefe_satire(text, "", "de" if "Man" in text or "Angeblich" in text else "en")
    assert ok is None and ("Zitat" in why or "Zuschreibung" in why)


@pytest.mark.parametrize("text,grund", [
    ("Man stelle sich vor, alle Migranten bekämen einen Hut.", "Gruppe"),
    ("Imagine all women getting a hat.", "Gruppe"),
    ("Angeblich ist der Minister ein Trottel.", "Beleidigung"),
    ("Man stelle sich vor, es kostet 40 Milliarden.", "neue Zahl"),
    ("Imagine Michael planning a summit.", "neuer Name"),
    ("Man stelle sich vor, dabei gäbe es Tote.", "heikles"),
])
def test_gruppen_beleidigung_zahlen_namen_heikel(text, grund):
    ok, why = S.pruefe_satire(text, "Der Minister plant ein Treffen.", "de" if "Man" in text or "Angeblich" in text else "en")
    assert ok is None and grund in why


def test_zahl_aus_dem_fakt_ist_erlaubt():
    assert S.pruefe_satire("Man stelle sich vor, die 40 Minuten wären ein Jahr.", "Das Treffen dauerte 40 Minuten.", "de")[0]


def test_regel_satire_besteht_eigene_pruefung():
    for lang in ("de", "en"):
        over, pointe = S.regel_satire(lang, "abc", "Der Minister plant ein Treffen.")
        assert len(over) == 2 and pointe
        assert all(S.pruefe_satire(t, "x", lang)[0] for t in over) and S.pruefe_satire(pointe, "x", lang, signal=False)[0]


def test_heikle_themen_abgelehnt(daten, tmp_path):
    with pytest.raises(S.SatireError) as exc:
        S.run({"id": "satire02", "thema": "Erdbeben in Japan", "sprache": "de"}, tmp_path / "f")
    assert "Reportage" in str(exc.value)
    with pytest.raises(S.SatireError) as exc:                                # heikel erst in den Quellen erkennbar
        S.run({"id": "satire03", "thema": "Gunman Krakow", "meldung": "Gunman kills 6 in Krakow", "sprache": "en"}, tmp_path / "g")
    assert "Reportage" in str(exc.value)


# --------------------------------------------------------------------------- Fakt-Teil

def test_fakt_braucht_zwei_betreiber_und_woertlichen_beleg(daten):
    q = quellen()
    assert len({x["betreiber"] for x in q}) == 2
    gut = {"text": "Trump offers a White House press secretary role to Dana White.",
           "belege": [{"quelle": "Q1", "zitat": "Trump offers White House press secretary role to Dana White"},
                      {"quelle": "Q2", "zitat": "Dana White says he will meet with Trump Monday"}]}
    ok, rej = S.pruefe_fakten({"fakten": [gut]}, q, "en")
    assert len(ok) == 1 and not rej
    einer = {**gut, "belege": [gut["belege"][0], {"quelle": "Q1", "zitat": "Trump offers White House press secretary"}]}
    assert S.pruefe_fakten({"fakten": [einer]}, q, "en")[0] == []                      # nur ein Betreiber
    erfunden = {**gut, "belege": [gut["belege"][0], {"quelle": "Q2", "zitat": "Dana White promised to quit the UFC"}]}
    assert S.pruefe_fakten({"fakten": [erfunden]}, q, "en")[0] == []                   # Zitat nicht wörtlich
    zahl = {**gut, "text": "Trump offers 3 roles to Dana White."}
    assert S.pruefe_fakten({"fakten": [zahl]}, q, "en")[0] == []                       # Zahl ohne Beleg


def test_wahrheits_pruefer_prueft_den_fakt_teil(daten):
    q = quellen()
    fakt = fakten_geprueft()
    assert S.wahrheit_fakten(fakt, "en")[0] == fakt
    superl = [{"text": "This is the only press secretary role ever offered to a fighter.", "belege": fakt[0]["belege"]}]
    ok, rej = S.wahrheit_fakten(superl, "en")
    assert ok == [] and "Wahrheits-Prüfer" in rej[0][1]


# --------------------------------------------------------------------------- Kennzeichnung

def test_titel_und_texte_tragen_satire(daten):
    fakten = fakten_geprueft()
    for vorschlag in ("Press secretary role", "SATIRE: Press secretary role", "Top 5 shocking secrets", ""):
        titel = S.waehle_titel(vorschlag, fakten, "en")
        assert titel.startswith("SATIRE: ") and len(titel) <= S.TITLE_MAX
    titel = S.waehle_titel("A very very very long title that does not fit into sixty characters at all", fakten, "en")
    assert len(titel) <= S.TITLE_MAX
    yt, tt = S.texte(titel, fakten, quellen(), "en")
    assert "satire" in yt.splitlines()[0].lower() and "satire" in yt.lower().split("\n\n")[1] and "satire" in tt.lower()


def test_abnahme_prueft_kennzeichnung_und_text(daten):
    fakten = fakten_geprueft()
    over, pointe = S.regel_satire("en", "x", fakten[0]["text"])
    titel = S.waehle_titel("", fakten, "en")
    sk = S.baue_skript(titel, fakten, over, pointe, "en", "satire")
    yt, tt = S.texte(titel, fakten, quellen(), "en")
    assert S.abnahme(sk, fakten, over, pointe, titel, yt, tt)["ok"]
    assert not S.abnahme(sk, fakten, over, pointe, "Press secretary role", yt, tt)["ok"]      # Titel ohne SATIRE
    assert not S.abnahme(sk, fakten, over, pointe, titel, "Beschreibung", tt)["ok"]
    sk["szenen"][2]["text"] = "Etwas Anderes, nicht Geprüftes."
    assert not S.abnahme(sk, fakten, over, pointe, titel, yt, tt)["ok"]


def test_stempel_in_jedem_szenentyp_und_cover(tmp_path):
    for typ in R.SCENES:
        job_ = {"index": 0, "typ": typ, "lang": "de", "text": "Ein kurzer Beispielsatz zum Testen.", "words": [], "lead": 0.6,
                "voice_dur": 2.0, "frames": 90, "duration": 3.4, "fps": 30, "quellen": ["DW"]}
        scene = R.make_scene(job_)
        for t in (0.0, 0.5, 1.7, 3.3):
            f = scene.frame(t).convert("RGB")
            box = f.crop((R.STAMP_POS[0], R.STAMP_POS[1], R.STAMP_POS[0] + 300, R.STAMP_POS[1] + 110))
            red = sum(1 for p in box.getdata() if p[0] > 170 and p[1] < 90 and p[2] < 90)  # noqa
            assert red > 400, (typ, t)
    texts = R.make_cover(tmp_path / "c.jpg", "SATIRE: Beispiel", "de")
    assert texts["headline"] == "SATIRE" and (tmp_path / "c.jpg").exists()


def test_profil_satire():
    from cudi_video import tts
    assert tts.speech_profile("satire") == "satire"
    assert tts.SPEECH_PROFILES["satire"]["rollen"]["satire"][0] > tts.SPEECH_PROFILES["satire"]["rollen"]["fakt"][0]


# --------------------------------------------------------------------------- Auftrag, Ideen

def test_satire_auftrag_validierung():
    ok = job.parse_order({"id": "sat00001", "art": "satire", "meldung": "https://www.dw.com/en/a/1", "sprache": "en"}, set())
    assert ok["art"] == "satire" and ok["meldung"].startswith("https://") and ok["sprache"] == "en"
    assert job.parse_order({"id": "sat00002", "art": "satire", "thema": "Eine harmlose Meldung"}, set())["sprache"] == "de"
    with pytest.raises(job.OrderError):
        job.parse_order({"id": "sat00003", "art": "satire"}, set())
    with pytest.raises(job.OrderError):
        job.parse_order({"id": "sat00004", "art": "satire", "thema": "Eine harmlose Meldung", "sprache": "fr"}, set())


def test_run_ende_zu_ende_ohne_modell(daten, tmp_path, monkeypatch):
    seen = {}

    def fake_render(skript, out, progress=None, musik=True):
        seen["skript"] = skript
        (out / "satire.mp4").write_bytes(b"x")
        (out / "satire_cover.jpg").write_bytes(b"x")
        return {"video": "satire.mp4", "cover": "satire_cover.jpg", "duration": 30.0, "qa": None}

    monkeypatch.setattr(R, "render_satire", fake_render)
    result = S.run({"id": "satire04", "meldung": "Trump offers White House press secretary role to Dana White", "sprache": "en"},
                   tmp_path / "ok")
    typen = [s["typ"] for s in seen["skript"]["szenen"]]
    assert typen[0] == "intro" and "fakt" in typen and typen.count("satire") >= 2 and typen[-2:] == ["pointe", "outro"]
    assert result["kind"] == "satire" and result["videos"]["en"]["abnahme"]["ok"]
    review = (tmp_path / "ok" / "satire" / "review.md").read_text("utf-8")
    assert "Fakt-Teil" in review and "SATIRE" in (tmp_path / "ok" / "satire" / "youtube.txt").read_text("utf-8")


def test_ideen_satire_nur_aus_bestaetigten_news_nie_heikel():
    trends = {"themen": [{"thema": "Ein Trendthema", "warum": "Top"}]}
    cand = ideen.candidates(trends, NEWS)
    raw = [{"bereich": "satire", "titel": "Presse-Posten", "thema": "Der Presse-Posten", "quelle_trend": "Trump offers White House press secretary role to Dana White"},
           {"bereich": "satire", "titel": "Trend", "thema": "Ein Trendthema satirisch", "quelle_trend": "Ein Trendthema"},
           {"bereich": "satire", "titel": "Krakau", "thema": "Krakau satirisch", "quelle_trend": "Gunman kills 6 in Krakow"}]
    out = ideen.finish(raw, cand, {}, False, [], set())
    by_title = {o["titel"]: o for o in out}
    assert by_title["Presse-Posten"]["bereich"] == "satire" and by_title["Presse-Posten"]["auftrag"]["art"] == "satire"
    assert by_title["Presse-Posten"]["auftrag"]["meldung"].startswith("Trump offers")
    assert "Trend" not in by_title                                           # kein News-Beleg -> keine Satire
    assert by_title["Krakau"]["bereich"] == "reportage" and "nur als Reportage" in by_title["Krakau"]["hinweis"]
