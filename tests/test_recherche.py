"""Recherche-Agent ohne Netz: Datums-/Seitenerkennung, Suchwege, Wikipedia-Regel, Abgleich, Aktualität, Gesamtablauf."""

from datetime import date, datetime, timezone

import pytest

from cudi_video import handoff, recherche
import importlib

from cudi_video.recherche import ablauf, fachquellen, lesen, web, wikipedia

suchmod = importlib.import_module("cudi_video.recherche.suche")   # Paket-Name `suche` ist die Funktion

HEUTE = date(2026, 11, 9)


@pytest.fixture(autouse=True)
def _iso(monkeypatch, tmp_path):
    monkeypatch.setenv("CUDI_RECHERCHE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CUDI_EIGENTUEMER_WIKIDATA", "0")
    monkeypatch.delenv("CUDI_BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("CUDI_SCHREIBEN", raising=False)
    monkeypatch.setattr(web, "robots_erlaubt", lambda url: True)
    monkeypatch.setattr(suchmod, "DDG_PAUSE", 0)
    monkeypatch.setattr(suchmod, "GDELT_PAUSE", 0)
    recherche.neuer_lauf()
    yield


def seite(titel, datum, text, extra_head=""):
    return (f"<html><head><title>{titel}</title>{extra_head}</head><body><nav>Menü Menü Menü</nav><article>"
            f"<p>{text}</p></article><footer>Impressum</footer></body></html>")


LANG = "Die Inflationsrate in Deutschland lag im Oktober 2026 bei 2,8 Prozent gegenüber dem Vorjahresmonat, teilte die Behörde mit. "


# --------------------------------------------------------------------------- Datum, Lesen

def test_parse_datum_formate():
    assert lesen.parse_datum("2026-10-30T09:00:00+02:00") == "2026-10-30"
    assert lesen.parse_datum("Stand: 30.10.2026") == "2026-10-30"
    assert lesen.parse_datum("Veröffentlicht am 3. März 2026") == "2026-03-03"
    assert lesen.parse_datum("October 12, 2026") == "2026-10-12"
    assert lesen.parse_datum("2031-01-01") is None and lesen.parse_datum("1985-01-01") is None
    assert lesen.parse_monat("im Oktober 2026 stieg") == "2026-10"


def test_lese_meta_jsonld_text(monkeypatch):
    html1 = seite("Meta", "", LANG * 2, '<meta property="article:published_time" content="2026-10-30T08:00:00Z">'
                  '<meta property="article:modified_time" content="2026-11-02">')
    html2 = seite("LD", "", LANG * 2, '<script type="application/ld+json">{"@graph":[{"datePublished":"2026-09-01","dateModified":"2026-09-05"}]}</script>')
    html3 = seite("Text", "", "Stand: 12. Oktober 2026. " + LANG * 2)
    pages = {"https://www.destatis.de/a": html1, "https://www.example-blog.de/b": html2, "https://www.spiegel.de/c": html3}
    monkeypatch.setattr(web, "hole", lambda url, **k: {"url": url, "status": 200, "typ": "text/html", "last_modified": "", "text": pages[url]})
    a, b, c = (lesen.lese(u) for u in pages)
    assert (a["veroeffentlicht"], a["geaendert"], a["datum"], a["datum_quelle"]) == ("2026-10-30", "2026-11-02", "2026-11-02", "meta")
    assert (b["veroeffentlicht"], b["geaendert"], b["datum_quelle"]) == ("2026-09-01", "2026-09-05", "json-ld")
    assert c["datum"] == "2026-10-12" and c["datum_quelle"] == "Text"
    assert a["typ"] == "Behörde/Primärquelle" and a["betreiber"] and "Menü" not in a["text"] and "Impressum" not in a["text"]


def test_lese_fehler_und_urlschutz(monkeypatch):
    assert not web.erlaubt_url("file:///etc/passwd") and not web.erlaubt_url("http://127.0.0.1/x")
    assert not web.erlaubt_url("http://user:pw@example.com/") and web.erlaubt_url("https://example.com/x")
    r = lesen.lese("http://localhost/x")
    assert not r["ok"] and "nicht erlaubt" in r["fehler"]
    monkeypatch.setattr(web, "robots_erlaubt", lambda url: False)
    assert "robots" in lesen.lese("https://example.com/privat")["fehler"]


def test_seitenbegrenzung(monkeypatch):
    monkeypatch.setenv("CUDI_RECHERCHE_SEITEN", "1")
    monkeypatch.setattr(web, "hole", lambda url, **k: {"url": url, "status": 200, "typ": "text/html", "last_modified": "", "text": seite("T", "", LANG * 2)})
    assert lesen.lese("https://www.zeit.de/a")["ok"]
    assert lesen.lese("https://www.zeit.de/b").get("begrenzt")


# --------------------------------------------------------------------------- Suche

DDG_HTML = ('<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.destatis.de%2Fx&rut=1">Destatis Inflation</a>'
            '<a class="result__snippet">Inflationsrate im Oktober</a></div>'
            '<div class="result"><a class="result__a" href="https://www.tagesschau.de/y">Tagesschau</a></div>')


def test_ddg_parse():
    t = suchmod.ddg_parse(DDG_HTML)
    assert [x["url"] for x in t] == ["https://www.destatis.de/x", "https://www.tagesschau.de/y"] and t[0]["auszug"] == "Inflationsrate im Oktober"


def test_suche_rangfolge_und_ausweichweg(monkeypatch):
    calls = []
    monkeypatch.setattr(suchmod, "weg_brave", lambda *a: calls.append("brave") or [])            # kein Schlüssel -> leer
    def ddg(a, s, z):
        calls.append("ddg")
        raise web.WebFehler("Captcha")
    monkeypatch.setattr(suchmod, "weg_ddg", ddg)
    monkeypatch.setattr(suchmod, "weg_gdelt", lambda a, s, z: [suchmod._treffer("https://www.dw.com/n", "DW", "2026-11-08", "", "GDELT")])
    monkeypatch.setattr(fachquellen, "finde", lambda *a: [])
    r = suchmod.suche(["Inflation Deutschland"], "de", "woche", "news")
    assert calls[:2] == ["brave", "ddg"]
    assert [t["url"] for t in r["treffer"]] == ["https://www.dw.com/n"]
    assert any("DuckDuckGo: nicht verfügbar" in s for s in r["schritte"])


def test_brave_nur_mit_schluessel(monkeypatch):
    assert suchmod.weg_brave("x", "de", None) == []
    monkeypatch.setenv("CUDI_BRAVE_API_KEY", "dummy")

    class R:
        def raise_for_status(self): pass
        def json(self): return {"web": {"results": [{"url": "https://www.zeit.de/a", "title": "Z", "description": "<b>Text</b>", "page_age": "2026-11-01T00:00:00"}]}}
    monkeypatch.setattr(suchmod.requests, "get", lambda *a, **k: R())
    t = suchmod.weg_brave("x", "de", "woche")
    assert t[0]["datum"] == "2026-11-01" and t[0]["auszug"] == "Text"


def test_claude_weg_nur_gefundenes_mit_url(monkeypatch):
    monkeypatch.setattr(handoff, "enabled", lambda: True)
    monkeypatch.setattr(handoff, "request", lambda task, ins, data: {"treffer": [
        {"url": "https://www.destatis.de/x", "titel": "A", "datum": "2026-10-30", "auszug": "x"},
        {"url": "ohne-adresse", "titel": "B"}, {"titel": "C"}, {"url": "javascript:alert(1)"}]})
    t = suchmod.weg_claude(["q"], "de", None)
    assert [x["url"] for x in t] == ["https://www.destatis.de/x"]
    monkeypatch.setattr(handoff, "enabled", lambda: False)          # Notbetrieb-Modell hat kein Internet -> nie fragen
    assert suchmod.weg_claude(["q"], "de", None) == []


def test_fachquellen_eurostat_weltbank():
    data = {"dimension": {"time": {"category": {"index": {"2026-08": 0, "2026-09": 1, "2026-10": 2}}}}, "value": {"0": 2.1, "1": 3.3, "2": 2.8}}
    t = fachquellen.eurostat_inflation(fachquellen.land_erkennen("Inflation in Deutschland"), "de", abruf=lambda u, p: data)[0]
    assert "2,8 Prozent" in t["text"] and "Oktober 2026" in t["text"] and t["datum"].startswith("2026-10")
    wb = [{}, [{"value": 2.17, "date": "2025"}]]
    w = fachquellen.weltbank(fachquellen.land_erkennen("Frankreich"), fachquellen.indikator_erkennen("Inflation"), "de", abruf=lambda u, p: wb)[0]
    assert "2,17" in w["text"] and w["datum"] == "2025-12-31"


# --------------------------------------------------------------------------- Wikipedia-Regel

def api_antwort(templates=(), revs=(), schutz=(), log=()):
    return {"query": {"pages": [{"title": "Berlin", "templates": [{"title": f"Vorlage:{t}"} for t in templates],
                                 "revisions": list(revs), "protection": list(schutz)}], "logevents": list(log)}}


def revs(n, kommentar="", tags=()):
    return [{"timestamp": "2026-11-0%dT10:00:00Z" % (1 + i % 8), "comment": kommentar, "tags": list(tags)} for i in range(n)]


JETZT = datetime(2026, 11, 9, tzinfo=timezone.utc)


def test_wikipedia_sauber():
    p = wikipedia.pruefe_seite("Berlin", "de", JETZT, api=lambda l, q: api_antwort(revs(5, "Tippfehler")))
    assert p["ok"] and p["geprueft"] and not p["zeichen"]


@pytest.mark.parametrize("antwort,teil", [
    (api_antwort(templates=["Neutralität"]), "Baustein"),
    (api_antwort(templates=["Belege fehlen"]), "Baustein"),
    (api_antwort(templates=["POV"]), "Baustein"),
    (api_antwort(revs=revs(5, "Revert auf Version von X")), "Rückgängig"),
    (api_antwort(revs=revs(4, "", ["mw-undo"])), "Rückgängig"),
    (api_antwort(revs=revs(45, "Ergänzung")), "Änderungen"),
    (api_antwort(schutz=[{"type": "edit", "level": "sysop"}], log=[{"comment": "Edit-War zwischen Nutzern"}]), "Seitenschutz"),
])
def test_wikipedia_manipulationszeichen(antwort, teil):
    p = wikipedia.pruefe_seite("Berlin", "de", JETZT, api=lambda l, q: antwort)
    assert not p["ok"] and any(teil in z for z in p["zeichen"])


def test_wikipedia_schutz_ohne_streit_und_ausfall():
    ok = wikipedia.pruefe_seite("Berlin", "de", JETZT, api=lambda l, q: api_antwort(schutz=[{"type": "edit", "level": "autoconfirmed"}],
                                                                                  log=[{"comment": "Vandalismus"}]))
    assert ok["ok"]
    def kaputt(l, q): raise OSError("Netz")
    aus = wikipedia.pruefe_seite("Berlin2", "de", JETZT, api=kaputt)
    assert not aus["ok"] and not aus["geprueft"]


def test_wikipedia_nur_fakten_geschichte_und_nur_mit_zweitquelle():
    url = "https://de.wikipedia.org/wiki/Berlin"
    sauber = {"ok": True, "zeichen": []}
    assert wikipedia.darf_belegen("fakten", url, True, sauber)[0]
    assert wikipedia.darf_belegen("geschichte", url, True, sauber)[0]
    ok, grund = wikipedia.darf_belegen("reportage", url, True, sauber)
    assert not ok and "kein Beleg" in grund
    ok, grund = wikipedia.darf_belegen("fakten", url, False, sauber)
    assert not ok and "allein" in grund
    ok, grund = wikipedia.darf_belegen("fakten", url, True, {"ok": False, "zeichen": ["Baustein „POV“"]})
    assert not ok and "POV" in grund
    assert wikipedia.darf_belegen("satire", "https://www.zeit.de/a", False)[0]


# --------------------------------------------------------------------------- Abgleich, Aktualität

def kand(url, datum, text, name=None, typ="Medium", quelle="meta"):
    from cudi_video import eigentuemer
    host = eigentuemer.host_von(url)
    s = {"url": url, "titel": host, "betreiber": name or host, "eigentuemer": "", "typ": typ, "datum": datum,
         "veroeffentlicht": datum, "geaendert": None, "datum_quelle": quelle}
    return {"seite": s, "text": text, "zitat": text, "zahlen": ablauf.zahlen(text), "bezug": lesen.parse_monat(text), "weg": "Regeln"}


S28 = "Die Inflationsrate in Deutschland betrug im Oktober 2026 genau 2,8 Prozent im Vergleich zum Vorjahresmonat."


def test_gleicher_betreiber_zaehlt_einmal_verschiedene_bestaetigen():
    gleich = [kand("https://www.destatis.de/a", "2026-10-30", S28), kand("https://presse.destatis.de/b", "2026-10-31", S28)]
    a, _ = ablauf.abgleichen(gleich, "fakten", HEUTE)
    assert len(a) == 1 and a[0]["status"] == "einzeln" and a[0]["n_gruppen"] == 1
    versch = [kand("https://www.destatis.de/a", "2026-10-30", S28), kand("https://www.tagesschau.de/b", "2026-10-31", S28)]
    a, _ = ablauf.abgleichen(versch, "fakten", HEUTE)
    assert a[0]["status"] == "bestaetigt" and a[0]["n_gruppen"] == 2 and len(a[0]["belege"]) == 2


def test_widerspruch_gleicher_zeitraum_wird_ausgewiesen():
    k = [kand("https://www.destatis.de/a", "2026-10-30", S28), kand("https://www.tagesschau.de/b", "2026-10-31", S28),
         kand("https://www.example-blog.de/c", "2026-10-31", S28.replace("2,8", "3,4"))]
    a, w = ablauf.abgleichen(k, "fakten", HEUTE)
    assert [x["art"] for x in w] == ["widerspruch"]
    by = {x["zahlen"].get("3.4") and "blog" or "amt": x for x in a}
    assert by["blog"]["status"] == "widersprochen" and by["amt"]["status"] == "bestaetigt" and by["amt"]["gegenstimmen"]


def test_aktualitaet_sortierung_und_veraltet():
    alt = S28.replace("Oktober 2026", "Dezember 2025").replace("2,8", "2,0")
    k = [kand("https://www.eurostat.example/a", "2025-12-28", alt), kand("https://www.destatis.de/a", "2026-10-30", S28),
         kand("https://www.tagesschau.de/b", "2026-11-02", S28)]
    a, w = ablauf.abgleichen(k, "fakten", HEUTE)
    assert a[0]["neuestes_datum"] == "2026-11-02" and a[0]["status"] == "bestaetigt"
    assert a[-1]["status"] == "veraltet" and "2025-12" in a[-1]["hinweis"]
    assert w and w[0]["art"] == "zeitlich verschieden"
    news = ablauf.abgleichen([kand("https://www.dw.com/a", "2026-09-01", S28)], "news", HEUTE)[0][0]
    assert news["status"] == "veraltet" and "älter als 14 Tage" in news["hinweis"]


def test_wikipedia_im_abgleich():
    wiki = kand("https://de.wikipedia.org/wiki/X", "2026-11-01", S28, typ="Wikipedia")
    amt = kand("https://www.destatis.de/a", "2026-10-30", S28)
    sauber = {wiki["seite"]["url"]: {"ok": True, "zeichen": []}}
    # nur Wikipedia: zählt nicht (Zweitquelle fehlt)
    a, _ = ablauf.abgleichen([wiki], "fakten", HEUTE, sauber)
    assert a[0]["status"] == "einzeln" and a[0]["belege"][0]["zaehlt_nicht"]
    # Wikipedia + Behörde im Bereich fakten: bestätigt
    a, _ = ablauf.abgleichen([wiki, amt], "fakten", HEUTE, sauber)
    assert a[0]["status"] == "bestaetigt"
    # gleiche Quellen im Bereich reportage: Wikipedia kein Beleg
    a, _ = ablauf.abgleichen([wiki, amt], "reportage", HEUTE, sauber)
    assert a[0]["status"] == "einzeln" and "kein Beleg" in next(b["zaehlt_nicht"] for b in a[0]["belege"] if "wikipedia" in b["url"])
    # Manipulationszeichen: Wikipedia zählt nicht, auch in fakten
    schlecht = {wiki["seite"]["url"]: {"ok": False, "zeichen": ["Baustein „Neutralität“"]}}
    a, _ = ablauf.abgleichen([wiki, amt], "fakten", HEUTE, schlecht)
    assert a[0]["status"] == "einzeln" and "Neutralität" in next(b["zaehlt_nicht"] for b in a[0]["belege"] if "wikipedia" in b["url"])


def test_zahlen_erkennung():
    assert ablauf.zahlen("Im Oktober 2026 lag sie bei 2,8 % nach 3,3 % im September") == {2.8: "%", 3.3: "%"}
    assert ablauf.zahlen("Deutschland hat 83.491.249 Einwohner (Stand 31. Dezember 2025)") == {83491249.0: ""}
    assert ablauf.zahlen("15 Städte im Jahr 2024") == {}


# --------------------------------------------------------------------------- Gesamtablauf

def test_recherchiere_gesamt_ohne_netz(monkeypatch):
    texte = {
        "https://www.destatis.de/p": ("Destatis", "2026-10-30", "Die Inflationsrate in Deutschland wird im Oktober 2026 voraussichtlich 2,8 Prozent betragen, teilte das Amt am Freitag mit."),
        "https://www.tagesschau.de/i": ("Tagesschau", "2026-11-02", "Die Inflationsrate in Deutschland ist im Oktober 2026 auf 2,8 Prozent gesunken, wie das Statistische Amt mitteilte."),
        "https://www.example-blog.de/x": ("Blog", "2026-10-31", "Die Inflationsrate in Deutschland lag im Oktober 2026 bei 3,9 Prozent nach Angaben des Autors."),
        "https://de.wikipedia.org/wiki/Inflation": ("Wikipedia", "2026-11-05", "Die Inflationsrate in Deutschland beträgt 2,8 Prozent im Oktober 2026 laut Eintrag."),
    }
    monkeypatch.setattr(suchmod, "suche", lambda anf, s, z, b, aufgabe="": {"treffer": [
        {"url": u, "titel": v[0], "datum": v[1], "auszug": "", "weg": "Test"} for u, v in texte.items()], "schritte": ["Test-Suche: 4 Treffer"]})
    def lese(url):
        t, d, text = texte[url]
        from cudi_video import eigentuemer
        info = eigentuemer.eigentuemer(url)
        return {"ok": True, "url": url, "titel": t, "text": text + " " + "Weitere Hinweise zur Methode. " * 3, "veroeffentlicht": d, "geaendert": None,
                "datum": d, "datum_quelle": "meta", "betreiber": info["name"], "eigentuemer": eigentuemer.anzeige(info),
                "typ": lesen.seitentyp(info["domain"], info), "fehler": "", "host": info["domain"]}
    monkeypatch.setattr(ablauf.lesen, "lese", lese)
    sauber = lambda l, q: api_antwort(revs(3, "Tippfehler"))
    e = recherche.recherchiere("Wie hoch ist die aktuelle Inflationsrate in Deutschland?", "reportage", "de", llm=False, heute=HEUTE, wiki_api=sauber)
    assert e["seiten_gelesen"] >= 3 and all(q["datum"] for q in e["quellen"])
    assert not any("wikipedia" in q["url"] for q in e["quellen"])                    # Reportage: Wikipedia nur Suchhinweis
    st = {a["status"] for a in e["aussagen"]}
    assert "bestaetigt" in st and "widersprochen" in st
    assert any(w["art"] == "widerspruch" for w in e["widersprueche"])
    assert e["aussagen"][0]["neuestes_datum"] >= e["aussagen"][-1]["neuestes_datum"] or e["aussagen"][-1]["status"] != "bestaetigt"
    md = recherche.bericht(e)
    assert "## Recherche" in md and "destatis.de" in md and "2026-10-30" in md and "widerspruch" in md
    # im Bereich fakten wird Wikipedia gelesen, geprüft und zählt zusätzlich
    e2 = recherche.recherchiere("Wie hoch ist die aktuelle Inflationsrate in Deutschland?", "fakten", "de", llm=False, heute=HEUTE, wiki_api=sauber)
    assert any("wikipedia" in q["url"] for q in e2["quellen"])
    assert any("Wikipedia-Prüfung bestanden" in s for s in e2["schritte"])


def test_recherchiere_ehrlich_leer(monkeypatch):
    monkeypatch.setattr(suchmod, "suche", lambda *a, **k: {"treffer": [], "schritte": ["Kein Suchweg lieferte Treffer"]})
    e = recherche.recherchiere("Gibt es Einhörner?", "fakten", "de", llm=False, heute=HEUTE)
    assert e["aussagen"] == [] and any("Keine Treffer" in h for h in e["hinweise"])


def test_anfragen_planung():
    a = ablauf.anfragen_planen("Wie hoch ist die aktuelle Inflationsrate in Deutschland?", "de", "fakten", HEUTE)
    assert len(a) == 4 and any("inflation rate Germany" in x for x in a) and any("site:destatis.de" in x for x in a)


def test_einzelstimme_mit_gleichem_wert_ist_kein_widerspruch():
    from datetime import date
    from cudi_video.recherche import ablauf
    def k(url, betr, zitat, z, datum):
        return {"seite": {"url": url, "titel": "", "betreiber": betr, "eigentuemer": betr, "typ": "medium", "datum": datum},
                "zitat": zitat, "text": zitat, "zahlen": z, "bezug": "2026-10"}
    ks = [k("https://a.de/1", "a.de", "Die Inflationsrate in Deutschland beträgt im Oktober 2026 voraussichtlich 2,8 %.", {"2.8": "%"}, "2026-10-30"),
          k("https://b.de/1", "b.de", "Im Oktober 2026 sank die Inflationsrate in Deutschland auf 2,8 %.", {"2.8": "%"}, "2026-10-30"),
          k("https://c.de/1", "c.de", "Die aktuelle Inflationsrate in Deutschland beträgt 2,8 % (Oktober 2026, vorläufig).", {"2.8": "%"}, "2026-11-04"),
          k("https://a.de/1", "a.de", "Die Inflationsrate ohne Nahrungsmittel und Energie beträgt im Oktober 2026 voraussichtlich 2,1 %.", {"2.1": "%"}, "2026-10-30")]
    aussagen, _ = ablauf.abgleichen(ks, "fakten", date(2026, 11, 9))
    assert not any(a["status"] == "widersprochen" for a in aussagen)
