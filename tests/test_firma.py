"""Firma-Mitarbeiter (Trend-Scout, News-Reporter, Ideen-Entwickler, Putzmann) mit gemockten HTTP-Antworten."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
import requests
import yaml

from cudi_video.firma import common, ideen, news, putzen, trends

ROOT = Path(__file__).resolve().parent.parent


class Resp:
    def __init__(self, data=None, content=b"", status=200):
        self._data, self.content, self.status_code = data, content, status

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def daten(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    monkeypatch.delenv("CUDI_YT_API_KEY", raising=False)
    monkeypatch.delenv("CUDI_YT_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("CUDI_LLM_BASE_URL", raising=False)
    monkeypatch.setattr("cudi_video.config.LLM_BASE_URL", "")
    monkeypatch.setattr("cudi_video.config.LLM_MODEL", "")
    monkeypatch.setattr("time.sleep", lambda s: None)
    return tmp_path / "firma_daten"


GT_XML = b"""<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>heerenveen - feyenoord</title><ht:approx_traffic>2K+</ht:approx_traffic>
<ht:news_item><ht:news_item_title>Feyenoord gewinnt</ht:news_item_title><ht:news_item_source>Zeitung</ht:news_item_source></ht:news_item></item>
<item><title>Taylor Swift</title><ht:approx_traffic>500+</ht:approx_traffic></item></channel></rss>"""


def test_google_trends_und_warum(monkeypatch):
    monkeypatch.setattr(trends, "fetch", lambda *a, **k: Resp(content=GT_XML))
    rows = trends.google_trends("DE")
    assert [r["name"] for r in rows] == ["heerenveen - feyenoord", "Taylor Swift"]
    assert rows[0]["suchen"] == 2000 and rows[0]["nachrichten"][0]["quelle"] == "Zeitung"
    assert "Platz 1 der Google-Trends (DE)" in trends.warum(rows[0]) and "Feyenoord gewinnt" in trends.warum(rows[0])


def test_wikipedia_top_filtert_und_nimmt_vortag_bei_404(monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(url)
        if len(calls) == 1:
            raise requests.HTTPError("404")
        return Resp({"items": [{"articles": [{"article": "Hauptseite", "views": 9, "rank": 1},
                                             {"article": "Spezial:Suche", "views": 8, "rank": 2},
                                             {"article": "Ilse_Aigner", "views": 7, "rank": 3}]}]})
    monkeypatch.setattr(trends, "fetch", fake)
    out = trends.wikipedia_top("de")
    assert [o["name"] for o in out] == ["Ilse Aigner"] and len(calls) == 2


def test_youtube_ohne_zugang_ist_nur_ein_hinweis():
    notes = []
    assert common.run_source("YouTube DE", lambda: trends.youtube_popular("DE"), notes) == []
    assert notes and notes[0].startswith("YouTube DE: nicht erreichbar")


def test_youtube_mit_api_key(monkeypatch):
    monkeypatch.setenv("CUDI_YT_API_KEY", "geheim")
    seen = {}

    def fake(url, params=None, headers=None, **kw):
        seen.update(params)
        return Resp({"items": [{"id": "abc", "snippet": {"title": "Ein Video", "channelTitle": "K", "categoryId": "10"},
                                "statistics": {"viewCount": "1234"}}]})
    monkeypatch.setattr(trends, "fetch", fake)
    out = trends.youtube_popular("US")
    assert out[0]["aufrufe"] == 1234 and out[0]["kategorie_quelle"] == "Musik" and seen["regionCode"] == "US"
    assert "geheim" not in json.dumps(out)


def test_merge_verschmilzt_quellen_und_bewahrt_erstmals():
    e = [{"quelle": "google", "region": "DE", "rang": 1, "name": "Taylor Swift", "suchen": 5},
         {"quelle": "wikipedia", "region": "en", "rang": 2, "name": "Taylor Swift", "aufrufe": 99, "tag": "2026-11-06",
          "kategorie": "Person"},
         {"quelle": "reddit", "region": "all", "rang": 1, "name": "Etwas ganz anderes", "subreddit": "news", "art": "top"}]
    prev = [{"thema": "Taylor Swift", "erstmals": "2026-11-01T00:00:00Z", "zuletzt": iso_now(), "score": 50, "quellen": []}]
    out = trends.merge(e, prev)
    swift = next(t for t in out if t["thema"] == "Taylor Swift")
    assert len(swift["quellen"]) == 2 and swift["kategorie"] == "Person" and swift["erstmals"].startswith("2026-11-01")
    assert swift["score"] > max(t["score"] for t in out if t is not swift) - 1 and swift["score"] <= 100


def iso_now():
    return common.iso()


def test_classify():
    assert trends.classify("American singer", "", "X") == "Person"
    assert trends.classify("Hurricane of 2026", "", "X") == "Ereignis"
    assert trends.classify("Programmiersprache", "", "Python") == "Thema"
    assert trends.classify("", "", "Russell Brand") == "Thema"       # „brand“ allein ist kein Ereignis


def test_trends_run_schreibt_nur_bei_aenderung(monkeypatch, daten):
    entries = [{"quelle": "google", "region": "DE", "rang": 1, "name": "Thema A", "suchen": 1}]
    monkeypatch.setattr(trends, "collect", lambda notes: (notes.append("YouTube DE: nicht erreichbar"), entries)[1])
    data = trends.run()
    assert data["themen"][0]["thema"] == "Thema A" and data["hinweise"]
    first = (daten / "trends.json").read_text("utf-8")
    trends.run()
    # zweiter Lauf: Inhalt gleich -> Datei bleibt byte-gleich (Zeitstempel wechseln nicht)
    assert (daten / "trends.json").read_text("utf-8") == first
    status = json.loads((daten / "status.json").read_text("utf-8"))["mitarbeiter"]["trends"]
    assert status["ergebnis"] == "ok" and "naechste_planung" in status


def test_trends_alle_quellen_aus_behaelt_alte_daten(monkeypatch, daten):
    common.write_json("trends.json", {"erzeugt": "x", "themen": [{"thema": "Alt", "zuletzt": common.iso(), "score": 1}]})
    monkeypatch.setattr(trends, "collect", lambda notes: [])
    trends.run()
    assert json.loads((daten / "trends.json").read_text("utf-8"))["themen"][0]["thema"] == "Alt"
    assert json.loads((daten / "status.json").read_text("utf-8"))["mitarbeiter"]["trends"]["ergebnis"] == "fehler"


# --------------------------------------------------------------------------- News

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Gunman kills six in Krakow main square, police say</title><link>https://a.example/1</link>
<description>&lt;p&gt;Kurz &lt;b&gt;Text&lt;/b&gt;&lt;/p&gt;</description><pubDate>Sun, 08 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Ein ganz anderes Thema ueber Bienen</title><link>https://a.example/2</link></item></channel></rss>"""


def test_publisher_of():
    assert news.publisher_of("https://www.bbc.co.uk/news/x") == news.publisher_of("bbc.com") == "bbc"
    assert news.publisher_of("tagesschau.de") == "tagesschau"
    assert news.publisher_of("https://www.abc.net.au/a") == "abc"


def test_rss_parse_kurzzeile_ohne_html(monkeypatch):
    monkeypatch.setattr(news, "fetch", lambda *a, **k: Resp(content=RSS))
    rows = news.rss("BBC World", "bbc", "en", "https://x")
    assert rows[0]["kurz"] == "Kurz Text" and rows[0]["zeit"].startswith("2026-11-08T10:00")
    assert len(news.clean("wort " * 100)) <= 161


def item(title, pub, lang="en"):
    return {"titel": title, "kurz": "", "link": f"https://{pub}.example/{abs(hash(title)) % 99}", "quelle": pub.upper(),
            "betreiber": pub, "sprache": lang, "zeit": "2026-11-08T10:00:00Z"}


def test_cluster_bestaetigt_nur_mit_zwei_unabhaengigen_quellen():
    items = [item("Gunman kills six in Krakow main square", "bbc"),
             item("Poland: Gunman kills 6 in Krakow main square, police say", "npr"),
             item("Gunman kills six in Krakow square again", "bbc"),           # gleiche Quelle zählt nicht doppelt
             item("Bee population recovers across Europe this summer", "dw")]
    out = news.cluster(items)
    krakow = next(m for m in out if "Krakow" in m["titel"])
    bees = next(m for m in out if "Bee" in m["titel"])
    assert krakow["status"] == "bestätigt" and krakow["n_quellen"] == 2
    assert bees["status"] == "unbestätigt" and bees["n_quellen"] == 1
    solo = news.cluster([item("Gunman kills six in Krakow main square", "bbc"),
                         item("Gunman kills six in Krakow main square today", "bbc")])
    assert solo[0]["status"] == "unbestätigt"


def test_news_run_mit_ausgefallener_quelle(monkeypatch, daten):
    def fake(url, **kw):
        if "bbci" in url:
            return Resp(content=RSS)
        raise requests.ConnectionError("down")
    monkeypatch.setattr(news, "fetch", fake)
    monkeypatch.setattr(news, "FEEDS", [f for f in news.FEEDS if f[1] in ("bbc", "tagesschau")])
    monkeypatch.setattr(news, "MAX_AGE_H", 24 * 365 * 5)
    data = news.run()
    assert data["anzahl"] == 2 and any("Tagesschau" in h for h in data["hinweise"])
    assert any("GDELT" in h for h in data["hinweise"])


# --------------------------------------------------------------------------- Ideen

CAND = {"Berge in Europa": {"typ": "trend", "score": 50, "kategorie": "Thema", "warum": "Platz 1", "quellen": ["google"]},
        "Taylor Swift": {"typ": "trend", "score": 40, "kategorie": "Person", "warum": "Platz 2", "quellen": ["wikipedia"]}}
PRESETS = {"hoechste-berge": {"title": {"de": "Die {count} höchsten Berge der Welt", "en": "Highest Mountains"}}}


def test_preset_match():
    assert ideen.preset_match("Die höchsten Berge der Welt", PRESETS) == "hoechste-berge"
    assert ideen.preset_match("Taylor Swift", PRESETS) is None


def test_finish_verwirft_ideen_ohne_beleg_und_baut_app_auftraege():
    raw = [{"bereich": "ranking", "titel": "Höchste Berge", "thema": "Die höchsten Berge der Welt",
            "begruendung": "x", "quelle_trend": "Berge in Europa"},
           {"bereich": "fakten", "titel": "Erfunden", "thema": "Etwas", "quelle_trend": "Nicht in den Daten"},
           {"bereich": "story", "titel": "Swift", "thema": "Eine Story", "quelle_trend": "Taylor Swift"},
           {"bereich": "erklaer", "titel": "Swift erklärt", "thema": "Wie Tourneen funktionieren", "quelle_trend": "Taylor Swift"},
           {"bereich": "unbekannt", "titel": "x", "thema": "y", "quelle_trend": "Taylor Swift"}]
    out = ideen.finish(raw, CAND, PRESETS, False, [], set())
    assert [i["bereich"] for i in out] == ["ranking", "story", "erklaer"]
    rank, story, erk = out
    assert rank["geprueft"] == "vorlage" and rank["auftrag"]["vorlage"] == "hoechste-berge" and "thema" not in rank["auftrag"]
    assert story["auftrag"]["art"] == "story" and story["app_auftrag"] is True
    assert erk["app_auftrag"] is False and erk["quelle"]["name"] == "Taylor Swift"


def test_ranking_ohne_vorlage_ohne_llm_bleibt_idee():
    raw = [{"bereich": "ranking", "titel": "Neu", "thema": "Die tiefsten Höhlen", "quelle_trend": "Taylor Swift"}]
    (idea,) = ideen.finish(raw, CAND, PRESETS, False, [], set())
    assert idea["geprueft"] == "idee" and idea["auftrag"]["thema"] == "Die tiefsten Höhlen"


def test_ideen_run_regelbasiert_ohne_secrets(monkeypatch, daten):
    common.write_json("trends.json", {"themen": [
        {"thema": "Taylor Swift", "kategorie": "Person", "score": 90, "warum": "Platz 1", "quellen": [{"quelle": "google"}]},
        {"thema": "Wahl in Hessen", "kategorie": "Ereignis", "score": 80, "warum": "Platz 2", "quellen": [{"quelle": "google"}]},
        {"thema": "Streit um Hunde", "kategorie": "Thema", "score": 70, "warum": "r/news", "quellen": [{"quelle": "reddit"}]}]})
    data = ideen.run()
    assert data["modus"] == "regeln"
    assert {i["bereich"] for i in data["ideen"]} == {"fakten", "erklaer", "story"}
    assert all(i["geprueft"] == "idee" for i in data["ideen"])
    again = ideen.run()                                  # gleiche Ideen werden nicht verdoppelt
    assert again["anzahl"] == data["anzahl"]


def test_ideen_run_llm_fehler_faellt_auf_regeln_zurueck(monkeypatch, daten):
    common.write_json("trends.json", {"themen": [{"thema": "Wahl in Hessen", "kategorie": "Ereignis", "score": 80,
                                                  "warum": "Platz 2", "quellen": [{"quelle": "google"}]}]})
    monkeypatch.setattr("cudi_video.llm.available", lambda: True)
    monkeypatch.setattr(ideen, "llm_ideas", lambda *a: (_ for _ in ()).throw(ValueError("kaputt")))
    data = ideen.run()
    assert data["modus"] == "regeln" and any("Sprachmodell nicht nutzbar" in h for h in data["hinweise"])


# --------------------------------------------------------------------------- Putzmann

class FakeGH:
    def __init__(self, dry=False):
        old, new = common.iso(common.now() - timedelta(days=9)), common.iso(common.now() - timedelta(days=1))
        long_ago = common.iso(common.now() - timedelta(days=40))
        self.calls = []
        self.data = {
            "/actions/artifacts": {"artifacts": [{"id": 1, "created_at": old}, {"id": 2, "created_at": new}]},
            "/actions/runs": {"workflow_runs": [{"id": 10, "status": "completed", "created_at": long_ago}]},
            "/issues": [
                {"number": 1, "state": "closed", "state_reason": "completed", "closed_at": long_ago, "locked": False,
                 "labels": [{"name": "cudi-auftrag"}]},
                {"number": 2, "state": "closed", "state_reason": "not_planned", "closed_at": long_ago, "locked": False,
                 "labels": [{"name": "cudi-auftrag"}]},
                {"number": 3, "state": "closed", "state_reason": "completed", "closed_at": long_ago, "locked": False,
                 "labels": [{"name": "bug"}]},
                {"number": 4, "state": "closed", "state_reason": "completed", "closed_at": new, "locked": False,
                 "labels": [{"name": "cudi-auftrag"}]},
                {"number": 5, "state": "closed", "state_reason": "completed", "closed_at": long_ago, "locked": False,
                 "pull_request": {}, "labels": [{"name": "cudi-auftrag"}]},
            ]}
        self.dry = dry


def fake_github(monkeypatch, gh):
    def fetch(url, params=None, method="GET", **kw):
        path = url.split("/repos/o/r", 1)[1]
        gh.calls.append((method, path))
        if method == "GET":
            return Resp(gh.data[path] if (params or {}).get("page", 1) == 1 else ([] if path == "/issues" else {}))
        return Resp({}, status=204)
    monkeypatch.setattr(putzen, "fetch", fetch)


def test_putzmann_loescht_nur_altes_und_sperrt_nur_erledigte(monkeypatch, daten):
    gh = FakeGH()
    fake_github(monkeypatch, gh)
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    report = putzen.run(dry=False)
    writes = [c for c in gh.calls if c[0] != "GET"]
    assert ("DELETE", "/actions/artifacts/1") in writes and ("DELETE", "/actions/artifacts/2") not in writes
    assert ("DELETE", "/actions/runs/10") in writes
    assert [c for c in writes if c[0] == "PUT"] == [("PUT", "/issues/1/lock")]
    assert all("/contents" not in p and "releases" not in p for _, p in gh.calls)
    assert report["protokoll"][0]["entfernt"] == {"artefakte": 1, "laeufe": 1, "issues_gesperrt": 1}


def test_putzmann_probelauf_aendert_nichts(monkeypatch, daten):
    gh = FakeGH()
    fake_github(monkeypatch, gh)
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    putzen.run(dry=True)
    assert not [c for c in gh.calls if c[0] != "GET"]


def test_putzmann_ohne_token_duennt_nur_daten_aus(monkeypatch, daten):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    old = common.iso(common.now() - timedelta(days=20))
    common.write_json("ideen.json", {"ideen": [{"id": "a", "erstellt": old}, {"id": "b", "erstellt": common.iso()}]})
    report = putzen.run(dry=False)
    assert [i["id"] for i in json.loads((daten / "ideen.json").read_text("utf-8"))["ideen"]] == ["b"]
    assert report["protokoll"][0]["entfernt"]["daten"] == {"ideen": 1}
    assert any("GITHUB_TOKEN" in h for h in report["letzter_lauf"]["hinweise"])


# --------------------------------------------------------------------------- Gemeinsames

def test_write_json_ignoriert_fluechtige_felder(daten):
    assert common.write_json("x.json", {"erzeugt": "a", "wert": 1}) is True
    assert common.write_json("x.json", {"erzeugt": "b", "wert": 1}) is False
    assert common.write_json("x.json", {"erzeugt": "b", "wert": 2}) is True


def test_short_error_ohne_abfrage_teil():
    exc = requests.HTTPError("403 for url: https://x.example/a?key=GEHEIM&b=1")
    assert "GEHEIM" not in common.short_error(exc)


@pytest.mark.parametrize("name", ["trends", "news", "ideen", "putzen", "lernen", "wissen"])
def test_workflow_yaml(name):
    wf = yaml.safe_load((ROOT / f".github/workflows/firma-{name}.yml").read_text("utf-8"))
    assert wf[True]["schedule"][0]["cron"] and "workflow_dispatch" in wf[True]
    assert wf["permissions"]["contents"] == "write" and wf["concurrency"]["group"] == "firma-daten"
    steps = wf["jobs"][name]["steps"]
    assert any(f"cudi_video.firma {name}" in s.get("run", "") for s in steps)
    assert any("firma_commit.sh" in s.get("run", "") for s in steps)
    if name == "putzen":
        assert wf["permissions"]["actions"] == "write" and wf["permissions"]["issues"] == "write"


def test_heikle_themen_nur_als_reportage():
    from cudi_video.firma import ideen

    trends = {"themen": [{"thema": "Russell Brand", "warum": "Wikipedia-Top"},
                         {"thema": "Erdbeben in Japan", "warum": "Google-Trends"}]}
    news = {"meldungen": [{"titel": "Gunman kills 6 in Krakow", "status": "bestätigt"},
                          {"titel": "Neues Teleskop entdeckt Galaxie", "status": "bestätigt"}]}
    cand = ideen.candidates(trends, news)
    assert not cand["Russell Brand"]["heikel"] and not cand["Neues Teleskop entdeckt Galaxie"]["heikel"]
    assert cand["Erdbeben in Japan"]["heikel"] and cand["Gunman kills 6 in Krakow"]["heikel"]
    raw = [{"bereich": "fakten", "titel": "Spannende Fakten", "thema": "Erdbeben in Japan", "quelle_trend": "Erdbeben in Japan"}]
    out = ideen.finish(raw, cand, {}, False, [], set())
    assert out and out[0]["bereich"] == "reportage" and out[0]["regeln"]
    assert out[0]["app_auftrag"] is True and out[0]["auftrag"]["art"] == "reportage"      # startbar als Reportage-Auftrag


def test_export_kompakt(daten, tmp_path, monkeypatch):
    from cudi_video.firma import export
    monkeypatch.setattr(export, "OUT", tmp_path / "docs" / "firma" / "firma.json")
    assert export.write() is False                                    # ohne Läufe nichts veröffentlichen
    common.write_json("trends.json", {"themen": [{"thema": f"T{i}", "kategorie": "Ereignis", "score": 10 - i} for i in range(9)]})
    common.write_json("news.json", {"bestaetigt": 1, "anzahl": 2, "meldungen": [
        {"titel": "a", "status": "unbestätigt", "link": "https://x.example"}, {"titel": "b", "status": "bestätigt", "n_quellen": 2}]})
    common.write_json("ideen.json", {"ideen": [{"id": "i1", "bereich": "ranking", "titel": "t", "app_auftrag": True, "auftrag": {"art": "ranking"}},
                                               {"id": "i2", "bereich": "reportage", "titel": "r", "app_auftrag": False, "auftrag": None}]})
    common.record_status("trends", 0.0, True, "9 Themen", ["h1", "h2", "h3", "h4"])
    assert export.write() is True
    data = json.loads(export.OUT.read_text("utf-8"))
    assert len(data["trends"]) == 5 and data["news"]["meldungen"][0]["titel"] == "b"
    assert data["ideen"][0]["auftrag"] == {"art": "ranking"} and data["ideen"][1]["auftrag"] is None
    assert data["status"]["trends"]["ergebnis"] == "ok" and len(data["status"]["trends"]["hinweise"]) == 3
    assert export.write() is False                                    # unverändert -> kein neuer Commit
    assert "cudi_video.firma export" in (ROOT / "scripts/firma_commit.sh").read_text("utf-8")


def test_news_cluster_zieht_keine_fremde_meldung_ueber_wortmenge():
    from cudi_video.firma import news
    def it(titel, pub):
        return {"titel": titel, "kurz": "", "link": "https://" + pub, "quelle": pub, "betreiber": pub,
                "sprache": "en", "zeit": ""}
    out = news.cluster([
        it("Seven dead and more than 100 injured after trains collide in Egypt", "bbc.com"),
        it("Egypt train crash leaves several dead, over 100 injured", "dw.com"),
        it("Eight people are killed and another is injured in a shooting spree in Turkey", "apnews.com"),
    ])
    egypt = next(m for m in out if "Egypt" in m["titel"])
    assert egypt["n_quellen"] == 2 and all("Turkey" not in q["titel"] for q in egypt["quellen"])
