"""Eigentümer/Unabhängigkeit (ohne Netz): gleiche Eigentümer, Agenturen, Staaten zählen nicht als Bestätigung."""

import json

import pytest

from cudi_video import eigentuemer as eig
from cudi_video.firma import briefing, common, news, welt


@pytest.fixture(autouse=True)
def ohne_netz(tmp_path, monkeypatch):
    monkeypatch.setenv("CUDI_EIGENTUEMER_WIKIDATA", "0")
    monkeypatch.setenv("CUDI_EIGENTUEMER_CACHE", str(tmp_path / "cache.json"))
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    monkeypatch.setattr("time.sleep", lambda s: None)
    eig.neuer_lauf()


def it(quelle, link, titel="Merz trifft Macron in Paris zu Gesprächen", kurz="", betreiber=None, sprache="de", land="X"):
    host = link.split("/")[2].removeprefix("www.")
    return {"titel": titel, "kurz": kurz, "link": link, "quelle": quelle, "betreiber": betreiber or news.publisher_of(host),
            "sprache": sprache, "zeit": "", "land": land, "art": "privat"}


def test_tabelle_belegt_und_deckt_feeds():
    tab = json.loads(eig.TABELLE.read_text("utf-8"))
    for e in tab["medien"]:
        if e["eigentuemer"] or e["geldgeber"]:
            assert e["quelle"], f"{e['name']}: Eigentümer ohne Beleglink"
        assert e["wikidata"]
    hosts = [news.publisher_of(f[3]) for f in news.FEEDS] + [news.publisher_of(f[5]) for f in welt.FEEDS]
    for f in list(news.FEEDS) + list(welt.FEEDS):
        url = f[3] if len(f) == 4 else f[5]
        assert eig._eintrag_fuer(eig.host_von(url)) is not None, f"Feed ohne Tabelleneintrag: {url}"
    assert hosts


def test_eigentuemer_auskunft():
    info = eig.eigentuemer("https://www.welt.de/politik/x")
    assert info["eigentuemer"] == ["Axel Springer SE"] and info["quelle"] and info["stand"]
    assert eig.eigentuemer("dw.com")["staatsnah"] is True
    assert eig.eigentuemer("xinhuanet.com")["agentur"] == "Xinhua"
    assert eig.eigentuemer("unbekannt.example")["bekannt"] is False


def test_welt_und_business_insider_gleicher_eigentuemer():
    r = eig.pruefe("welt.de", "businessinsider.com")
    assert not r["unabhaengig"] and "Axel Springer" in r["grund"]
    items = [it("Welt", "https://www.welt.de/a"), it("Business Insider", "https://www.businessinsider.com/b")]
    meldung = news.cluster(items)[0]
    assert meldung["status"] == "unbestätigt" and meldung["unabhaengig_n"] == 1
    assert meldung["abhaengig"][0]["grund"].startswith("gleicher Eigentümer")
    assert any(q["zaehlt_nicht"] for q in meldung["quellen"])


def test_zwei_artikel_mit_afp_keine_bestaetigung():
    items = [it("Tagesschau", "https://www.tagesschau.de/a", kurz="Paris (AFP) – Merz trifft Macron"),
             it("Der Standard", "https://www.derstandard.at/b", kurz="AFP: Merz trifft Macron")]
    assert not eig.unabhaengig(items[0], items[1])
    meldung = news.cluster(items)[0]
    assert meldung["status"] == "unbestätigt" and "AFP" in meldung["abhaengig"][0]["grund"]
    assert eig.agenturen_in({"quelle": "Wikipedia · AFP via France 24", "titel": ""}) == {"AFP"}
    assert eig.agenturen_in({"quelle": "X", "titel": "Prüfung im AP-Kurs", "kurz": ""}) == set()


def test_bbc_und_xinhua_bestaetigen():
    assert eig.unabhaengig("bbc.co.uk", "xinhuanet.com")
    items = [it("BBC World", "https://www.bbc.co.uk/a"), it("Xinhua", "https://english.news.cn/b")]
    meldung = news.cluster(items)[0]
    assert meldung["status"] == "bestätigt" and meldung["unabhaengig_n"] == 2 and meldung["abhaengig"] == []


def test_gleicher_staat_und_geldgeber():
    assert not eig.unabhaengig("aa.com.tr", "aa.com.tr/en")
    r = eig.pruefe("afp.com", "france24.com")
    assert not r["unabhaengig"] and "Frankreich" in r["grund"]
    assert not eig.unabhaengig("tagesschau.de", "zdf.de")                    # beide Rundfunkbeitrag
    assert eig.unabhaengig("tagesschau.de", "dw.com")


def test_gleiche_domain_und_transitiv():
    assert not eig.unabhaengig("bbc.co.uk", "bbc.com")
    ana = eig.gruppiere([{"link": "https://welt.de/a", "quelle": "Welt"}, {"link": "https://politico.eu/b", "quelle": "Politico"},
                         {"link": "https://businessinsider.com/c", "quelle": "BI"}, {"link": "https://nzz.ch/d", "quelle": "NZZ"}])
    assert ana["n"] == 2 and ana["gruppe"][:3] == [0, 0, 0] and ana["gruppe"][3] == 1


def test_unbekannter_eigentuemer_wird_vermerkt():
    r = eig.pruefe("a-zeitung.example", "welt.de")
    assert r["unabhaengig"] and r["unbekannt"] == ["a-zeitung.example"]
    items = [it("A-Zeitung", "https://www.a-zeitung.example/x"), it("Welt", "https://www.welt.de/b")]
    meldung = news.cluster(items)[0]
    assert meldung["status"] == "bestätigt" and "a-zeitung.example" in meldung["eigentuemer_unbekannt"]
    assert meldung["quellen"][0]["eigentuemer"] in ("Eigentümer unbekannt", "gehört Axel Springer SE")


def test_wikidata_fallback_und_cache(monkeypatch):
    monkeypatch.setenv("CUDI_EIGENTUEMER_WIKIDATA", "1")
    calls = []

    def fake(host):
        calls.append(host)
        return {"eigentuemer": ["Beispiel Holding"], "geldgeber": [], "quelle": ["https://www.wikidata.org/wiki/Q1"]}
    monkeypatch.setattr(eig, "_wikidata", fake)
    a = eig.eigentuemer("blatt-a.example")
    assert a["eigentuemer"] == ["Beispiel Holding"] and a["herkunft"] == "Wikidata"
    eig.eigentuemer("www.blatt-a.example")
    assert len(calls) == 1                                                   # zweites Mal aus dem Cache
    monkeypatch.setattr(eig, "_wikidata", lambda host: {"eigentuemer": ["Beispiel Holding"], "geldgeber": [], "quelle": []})
    assert not eig.unabhaengig("blatt-a.example", "blatt-b.example")         # gleicher Eigentümer laut Wikidata


def test_wikidata_hoechstens_10_neue_abfragen(monkeypatch):
    monkeypatch.setenv("CUDI_EIGENTUEMER_WIKIDATA", "1")
    n = []
    monkeypatch.setattr(eig, "_wikidata", lambda host: n.append(host))
    for i in range(15):
        eig.eigentuemer(f"seite{i}.example")
    assert len(n) == eig.MAX_NEU


def test_welt_laender_nur_mit_unabhaengigen_quellen():
    t = "Merz meets Macron in Paris for talks"
    items = [it("Dawn", "https://www.dawn.com/a", land="Pakistan", sprache="en", titel=t),
             it("Welt", "https://www.welt.de/b", land="Deutschland", sprache="en", titel=t),
             it("Politico", "https://www.politico.eu/c", land="Belgien", sprache="en", titel=t)]
    g = welt.build_groups(items, [])[0]
    assert len(g["laender_einig"]) == 2 and "Pakistan" in g["laender_einig"] and not g["bestaetigt_laender"]   # Welt+Politico = eine Stimme
    assert g["unabhaengig_n"] == 2 and "Axel Springer" in g["abhaengig"][0]["grund"]
    assert any(q["zaehlt_nicht"] for q in g["quellen"])
    items.append(it("Rappler", "https://www.rappler.com/d", land="Philippinen", sprache="en", titel=t))
    g = welt.build_groups(items, [])[0]
    assert len(g["laender_einig"]) == 3 and g["bestaetigt_laender"]


def test_briefing_zeigt_eigentuemer_und_grund():
    m = {"titel": "Merz trifft Macron", "status": "bestätigt", "unabhaengig_n": 2, "zeit": "",
         "quellen": [{"quelle": "Welt", "titel": "Merz trifft Macron", "link": "https://welt.de/a", "eigentuemer": "gehört Axel Springer SE", "gruppe": 0, "zaehlt_nicht": ""},
                     {"quelle": "Business Insider", "titel": "Merz trifft Macron", "link": "https://bi.com/b", "eigentuemer": "gehört Axel Springer SE", "gruppe": 0,
                      "zaehlt_nicht": "gleicher Eigentümer Axel Springer SE"},
                     {"quelle": "NZZ", "titel": "Merz trifft Macron", "link": "https://nzz.ch/c", "eigentuemer": "gehört NZZ-Mediengruppe", "gruppe": 1, "zaehlt_nicht": ""}]}
    top = briefing.top_items({"meldungen": [m]}, {})
    assert "2 unabhängigen" in top[0]["kopf"]
    assert any("zählt nicht: gleicher Eigentümer Axel Springer SE" in z for z in top[0]["zeilen"])
    assert any("Welt – gehört Axel Springer SE" in z for z in top[0]["zeilen"])
    m["quellen"][2]["gruppe"] = 0
    m["unabhaengig_n"] = 1
    assert briefing.top_items({"meldungen": [m]}, {}) == []
