"""Clip-Scout und Messung ohne Netz: Feeds/HTML als Fixture."""

import json
from pathlib import Path

import pytest
import yaml

from cudi_video.firma import briefing, clipscout, common, export, lernen, messung

ROOT = Path(__file__).resolve().parent.parent
ECHTE_ENTDECKUNG = clipscout.entdecke


@pytest.fixture(autouse=True)
def daten(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    monkeypatch.setattr(clipscout, "campaigns", lambda notes: [])
    monkeypatch.setattr(clipscout, "entdecke", lambda *a, **k: [])             # Entdeckung nur in den eigenen Tests


def feed(desc: str, views: int = 5000, hours_old: int = 5, vid: str = "abc123") -> bytes:
    pub = (common.now() - __import__("datetime").timedelta(hours=hours_old)).isoformat()
    return f"""<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"
    xmlns:media="http://search.yahoo.com/mrss/"><author><name>Kanal</name></author>
    <entry><yt:videoId>{vid}</yt:videoId><title>Titel</title><published>{pub}</published>
    <media:group><media:description>{desc}</media:description>
    <media:community><media:statistics views="{views}"/></media:community></media:group></entry>
    <entry><yt:videoId>old</yt:videoId><title>alt</title><published>{pub}</published>
    <media:group><media:description>x</media:description><media:community><media:statistics views="50"/></media:community></media:group></entry>
    </feed>""".encode()


class Resp:
    def __init__(self, content): self.content, self.text = content, content.decode()


def setup_run(monkeypatch, creator, desc):
    common.write_json("clip_creators.json", {"creators": [creator]})
    monkeypatch.setattr(common, "fetch", lambda url, **kw: Resp(feed(desc)))
    monkeypatch.setattr(clipscout, "twitch_clips", lambda login, limit=20: [])


CID = "UC" + "a" * 22


def test_leere_liste_ist_ehrlich_leer():
    data = clipscout.run()
    assert data["videos"] == [] and any("clip_creators.json" in h for h in data["hinweise"])
    assert common.read_json("clip_erlaubnis.json")["creators"] == []


def test_erlaubt_nur_mit_woertlichem_beleg(monkeypatch):
    desc = "Neues Video! Clipper gesucht, Link im Discord: https://discord.gg/xyz Viel Spaß"
    setup_run(monkeypatch, {"name": "Max", "youtube": [CID]}, desc)
    clipscout.run()
    c = common.read_json("clip_erlaubnis.json")["creators"][0]
    assert c["status"] == "erlaubt" and c["belege"][0]["url"].endswith("abc123")
    assert c["belege"][0]["zitat"].replace("  ", " ") in desc and c["belege"][0]["datum"]
    radar = common.read_json("clip_radar.json")
    assert radar["videos"][0]["erlaubt"] is True and radar["vorschlaege"][0]["art"] == "clip"
    assert "bestaetigt_erlaubnis" not in radar["vorschlaege"][0]


def test_ohne_beleg_unklar_und_kein_vorschlag(monkeypatch):
    setup_run(monkeypatch, {"name": "Max", "youtube": [CID]}, "Nur ein normales Video")
    clipscout.run()
    assert common.read_json("clip_erlaubnis.json")["creators"][0]["status"] == "unklar"
    radar = common.read_json("clip_radar.json")
    assert radar["vorschlaege"] == [] and not radar["videos"][0]["erlaubt"]


def test_sperre_gewinnt(monkeypatch):
    setup_run(monkeypatch, {"name": "Max", "youtube": [CID], "gesperrt": True}, "Clipper gesucht, Link: https://discord.gg/x")
    clipscout.run()
    assert common.read_json("clip_erlaubnis.json")["creators"][0]["status"] == "gesperrt"
    assert common.read_json("clip_radar.json")["vorschlaege"] == []


def test_schwacher_hinweis_und_rauschen_reichen_nicht():
    assert clipscout.find_call("Barber Vlog mit meinem hair clipper") is None
    weak = clipscout.find_call("Wir suchen Clipper für unser Team")
    assert weak and weak["staerke"] == "hinweis"
    assert clipscout.decide({"name": "x"}, [{"url": "u", "zitat": "z", "datum": "2026-01-01", "art": "beschreibung",
                                             "staerke": "hinweis"}])["status"] == "unklar"


def test_quelle_faellt_aus(monkeypatch):
    common.write_json("clip_creators.json", {"creators": [{"name": "Max", "youtube": [CID], "twitch": ["x"]}]})
    def boom(url, **kw): raise RuntimeError("down")
    monkeypatch.setattr(common, "fetch", boom)
    monkeypatch.setattr(clipscout, "twitch_clips", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("t")))
    data = clipscout.run()
    assert len(data["hinweise"]) >= 2 and common.read_json("status.json")["mitarbeiter"]["clipscout"]["ergebnis"] == "ok"


def test_kampagnen_parser():
    obj = {"availableBudgetRaw": 900, "id": "c1", "title": "Clip Max deutsch", "type": "cpm", "payoutSortRaw": 1.5,
           "description": "Schneide die besten Momente von https://www.youtube.com/@max", "creatorCountRaw": 3}
    html = '<script>self.__next_f.push([1,"' + json.dumps(obj).replace('"', '\\"') + '"])</script>'
    camps = clipscout.parse_campaigns(html)
    s = clipscout.summarize_campaign(camps[0])
    assert s["kanaele"] == ["https://www.youtube.com/@max"] and s["satz_pro_1000"] == 1.5 and s["art"] == "clipping"
    c = clipscout.evidence_from_campaigns({"youtube": ["@max"]}, [s], [])
    assert c and clipscout.decide({"name": "m"}, c)["status"] == "unklar"       # Kampagne allein erlaubt nichts


def test_messung_zeitreihe(monkeypatch):
    common.write_json("uploads.json", {"eintraege": [{"ziel": "youtube", "video_id": "v1", "url": "", "auftrag": "a1"}]})
    vals = iter([{"zeit": "2026-11-09T10:00:00Z", "aufrufe": 10, "likes": 1, "kommentare": 0},
                 {"zeit": "2026-11-09T10:10:00Z", "aufrufe": 12, "likes": 1, "kommentare": 0},
                 {"zeit": "2026-11-09T12:00:00Z", "aufrufe": 40, "likes": 3, "kommentare": 1}])
    monkeypatch.setattr(messung, "read_stats", lambda url: next(vals))
    messung.run(); messung.run(); messung.run()
    e = common.read_json("messung.json")["posts"]["https://www.youtube.com/watch?v=v1"]
    assert [p["aufrufe"] for p in e["verlauf"]] == [10, 40]            # zweiter Punkt < 1 h nach dem ersten: übersprungen
    assert messung.latest("https://www.youtube.com/watch?v=v1")["aufrufe"] == 40


def test_messung_nicht_lesbar_und_leer(monkeypatch):
    data = messung.run()
    assert data["anzahl"] == 0 and data["hinweise"]
    common.write_json("clip_radar.json", {"clip_posts": [{"url": "https://www.tiktok.com/@a/video/1"}]})
    monkeypatch.setattr(messung, "read_stats", lambda url: None)
    data = messung.run()
    assert data["posts"]["https://www.tiktok.com/@a/video/1"]["fehler"] and data["gesamt_aufrufe"] == 0


def test_lernen_nutzt_messung_ohne_api():
    common.write_json("messung.json", {"posts": {"https://www.youtube.com/watch?v=v1": {"verlauf": [
        {"zeit": "2026-11-09T10:00:00Z", "aufrufe": 77, "likes": 2, "kommentare": 1}]}}})
    out: list = []
    notes: list = []
    lernen._from_messung([{"ziel": "youtube", "video_id": "v1", "auftrag": "a1", "varianten": {"format": "karte"}}], out, notes)
    assert out[0]["views"] == 77 and notes


def test_briefing_clipteam_nur_belegt():
    secs = briefing.build_sections()
    assert secs[-1]["titel"].startswith("6. Clip-Team") and "Kein belegtes" in secs[-1]["punkte"][0]["text"]
    common.write_json("clip_radar.json", {"videos": [{"creator": "Max", "titel": "T", "url": "https://y/1", "erlaubt": True,
                                                     "faktor": 2.0, "aufrufe_je_stunde": 900}]})
    common.write_json("clip_erlaubnis.json", {"creators": [{"name": "Max", "status": "erlaubt", "geprueft": common.iso(),
                                                           "belege": [{"url": "https://y/1", "zitat": "Clipper gesucht", "datum": "2026-11-08"}]}]})
    common.write_json("messung.json", {"posts": {"https://p/1": {"verlauf": [{"zeit": "2026-11-09T10:00:00Z", "aufrufe": 5, "likes": 1}]}}})
    texts = " ".join(p["text"] for p in briefing.build_sections()[-1]["punkte"])
    assert "Virales erlaubtes Material" in texts and "Erlaubnis belegt" in texts and "Eigener Post" in texts


def test_export_clipteam(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "OUT", tmp_path / "f.json")
    common.record_status("clipscout", 0.0, True, "x")
    common.write_json("clip_erlaubnis.json", {"creators": [{"name": "Max", "status": "erlaubt"}]})
    export.write()
    assert json.loads(export.OUT.read_text("utf-8"))["clipteam"]["erlaubt"] == ["Max"]


@pytest.mark.parametrize("name", ["clipscout", "messung"])
def test_workflow_yaml(name):
    wf = yaml.safe_load((ROOT / f".github/workflows/firma-{name}.yml").read_text("utf-8"))
    assert wf[True]["schedule"][0]["cron"] and wf["concurrency"]["group"] == "firma-daten"
    steps = wf["jobs"][name]["steps"]
    assert any(f"cudi_video.firma {name}" in s.get("run", "") for s in steps)
    assert any("firma_commit.sh" in s.get("run", "") for s in steps) and any("yt-dlp" in s.get("run", "") for s in steps)


# ----------------------------------------------------------------------------- Entdeckung + vier Stufen

def cand(name="Neo", plattform="youtube", kanal=CID, punkte=30, signal=None, bestaetigt=True, quelle="reddit"):
    return clipscout._cand(name, plattform, kanal, "Testgrund", quelle, punkte, signal, "https://x.test/" + name, bestaetigt)


def entdeckung_ohne_netz(monkeypatch, cands):
    monkeypatch.setattr(clipscout, "entdecke", lambda notes, camps, old, cache: clipscout.merge_entdeckt(cands, old))


def test_quelle_kampagne_und_aufrufsuche(monkeypatch):
    camp = [{"titel": "Clip Max", "link": "https://contentrewards.com/c/campaigns/1", "kanaele": ["https://www.youtube.com/@max"]}]
    c = clipscout.src_kampagnen(camp)[0]
    assert c["kanal"] == "@max" and c["quellen"] == ["kampagne"] and c["signal"]["kampagnen"] == 1
    monkeypatch.setattr(clipscout, "youtube_suche", lambda q, limit=10: [
        {"title": "Clipper gesucht für meinen Kanal", "channel": "Ana", "channel_id": CID, "url": "https://y/1"},
        {"title": "Hair clipper review", "channel": "Bob", "channel_id": "UC" + "b" * 22, "url": "https://y/2"}])
    out = clipscout.src_aufruf_suche()
    assert [o["name"] for o in out] == ["Ana", "Ana"]            # zwei Suchanfragen, Rauschen fällt weg


def test_quelle_youtube_trends_und_wikipedia(monkeypatch):
    trends = {"themen": [
        {"thema": "Video", "kategorie": "Thema", "quellen": [{"quelle": "youtube", "region": "DE", "rang": 2, "kanal": "Kanal X",
                                                              "link": "https://www.youtube.com/watch?v=v1"}]},
        {"thema": "Kai Beispiel", "kategorie": "Person", "quellen": [{"quelle": "wikipedia", "region": "de", "rang": 4, "link": "https://w/1"}]},
        {"thema": "Ein Politiker", "kategorie": "Person", "quellen": [{"quelle": "wikipedia", "region": "de", "rang": 5, "link": "https://w/2"}]}]}
    class R:
        def __init__(self, data): self.data = data
        def json(self): return self.data
    def fake(url, params=None, **kw):
        if "oembed" in url:
            return R({"author_name": "Kanal X", "author_url": "https://www.youtube.com/@kanalx"})
        if "wikipedia.org" in url:
            return R({"wikibase_item": "Q1" if "Kai" in url else "Q2"})
        occ = "YouTuber" if "Q1" in params["query"] else "politician"
        return R({"results": {"bindings": [{"occ": {"value": occ}, "yt": {"value": CID}}]}})
    monkeypatch.setattr(common, "fetch", fake)
    monkeypatch.setattr(clipscout.time, "sleep", lambda s: None)
    yt = clipscout.src_youtube_trends(trends, {})
    assert yt[0]["kanal"] == "@kanalx" and yt[0]["signal"]["yt_trend_rang"] == 2
    wiki_cache: dict = {}
    wp = clipscout.src_wikipedia(trends, wiki_cache)
    assert [w["name"] for w in wp] == ["Kai Beispiel"] and wp[0]["kanal"] == CID      # Politiker: Beruf passt nicht
    assert wiki_cache["de:Ein Politiker"] == {}                                        # Negativtreffer gemerkt


def test_quelle_reddit_namen(monkeypatch):
    posts = [{"title": "Destiny talks about things", "score": 10}, {"title": "Destiny reacts to chat", "score": 20},
             {"title": "The streamer left", "score": 400}, {"title": "DariusIRL's girlfriend speaks", "score": 300}]
    namen = clipscout.streamer_namen(posts)
    assert namen["Destiny"]["n"] == 2 and "The" not in namen and namen["DariusIRL"]["punkte"] == 300
    class R:
        def json(self): return {"data": [{**p, "id": str(i), "over_18": False} for i, p in enumerate(posts)]}
    monkeypatch.setattr(common, "fetch", lambda *a, **k: R())
    out = clipscout.src_reddit()
    assert {o["name"] for o in out} == {"Destiny", "DariusIRL"} and all(not o["kanal_bestaetigt"] for o in out)


def test_limit_neue_und_ausduennen():
    cands = [cand(f"N{i}", kanal=f"@n{i}", punkte=i) for i in range(70)]
    out = clipscout.merge_entdeckt(cands, [])
    assert len(out) == clipscout.MAX_NEU and out[0]["punkte"] == 69             # höchste Signale zuerst
    alt = {**out[0], "zuletzt": common.iso(common.now() - __import__("datetime").timedelta(days=15))}
    frisch = {**out[1], "zuletzt": common.iso(common.now() - __import__("datetime").timedelta(days=3))}
    again = clipscout.merge_entdeckt([], [alt, frisch])
    assert [e["key"] for e in again] == [frisch["key"]]                          # >14 Tage ohne Sichtung fliegt raus


def test_zusammenfuehren_gleicher_kanal_aus_zwei_quellen():
    out = clipscout.merge_entdeckt([cand(quelle="reddit", punkte=20), cand(quelle="kampagne", punkte=30)], [])
    assert len(out) == 1 and out[0]["quellen"] == ["kampagne", "reddit"] and out[0]["punkte"] == 50


def run_entdeckt(monkeypatch, eintrag, desc="Nur ein normales Video", creators=None):
    common.write_json("clip_creators.json", {"creators": creators or []})
    entdeckung_ohne_netz(monkeypatch, [eintrag])
    monkeypatch.setattr(common, "fetch", lambda url, **kw: Resp(feed(desc)))
    monkeypatch.setattr(clipscout, "twitch_clips", lambda login, limit=20: [])
    clipscout.run()
    return common.read_json("clip_entdeckt.json")["creators"][0], common.read_json("clip_radar.json")


def test_entdeckter_mit_aufruf_ist_erlaubt_und_bekommt_vorschlag(monkeypatch):
    e, radar = run_entdeckt(monkeypatch, cand(), "Clipper gesucht, Link: https://discord.gg/xyz")
    assert e["erlaubnis"] == "erlaubt" and e["signal"]["aufruf"] and radar["vorschlaege"][0]["erlaubnis"] == "erlaubt"
    assert common.read_json("clip_erlaubnis.json")["creators"][0]["belege"][0]["url"].endswith("abc123")


def test_geduldet_nur_mit_signalen_und_ehrlichem_vorschlag(monkeypatch):
    sig = {"reddit_beitraege": 4, "reddit_sub": "LivestreamFail", "yt_trend_rang": 3, "region": "DE"}
    e, radar = run_entdeckt(monkeypatch, cand(signal=sig))
    assert e["erlaubnis"] == "geduldet" and len({s.split(":")[0] for s in e["signale"]}) == 2
    v = radar["vorschlaege"][0]
    assert v["erlaubnis"] == "geduldet" and "nicht ausdrücklich erlaubt" in v["hinweis"] and v["credit"].startswith("Original: Neo")
    assert "bestaetigt_erlaubnis" not in v and "geduldet" in radar["videos"][0]["grund"]
    assert "nicht ausdrücklich erlaubt" in common.read_json("clip_erlaubnis.json")["creators"][0]["bedingungen"][0]


def test_ein_signal_ist_unklar_und_ohne_vorschlag(monkeypatch):
    e, radar = run_entdeckt(monkeypatch, cand(signal={"yt_trend_rang": 3, "region": "DE"}))
    assert e["erlaubnis"] == "unklar" and radar["vorschlaege"] == [] and radar["im_hype_erlaubnis_offen"][0]["name"] == "Neo"


def test_vermuteter_kanal_wird_nie_geduldet(monkeypatch):
    sig = {"reddit_beitraege": 4, "reddit_sub": "LivestreamFail", "yt_trend_rang": 3, "region": "DE"}
    e, radar = run_entdeckt(monkeypatch, cand(signal=sig, bestaetigt=False))
    assert e["erlaubnis"] == "unklar" and radar["vorschlaege"] == []


def test_verbot_in_beschreibung_sperrt_trotz_signalen(monkeypatch):
    sig = {"reddit_beitraege": 4, "reddit_sub": "LivestreamFail", "yt_trend_rang": 3, "region": "DE"}
    e, radar = run_entdeckt(monkeypatch, cand(signal=sig), "Clipper gesucht! https://discord.gg/x  Aber: no clips of the finale please")
    assert e["erlaubnis"] == "gesperrt" and radar["vorschlaege"] == []
    z = common.read_json("clip_erlaubnis.json")["creators"][0]
    assert "ausdrückliches Verbot" in z["bedingungen"][0] and z["belege"][0]["art"] == "verbot"
    for text in ("keine Clips bitte", "Don't reupload my content", "copyright strike"):
        assert clipscout.VERBOT.search(text)


def test_sperrliste_gewinnt_ueber_entdeckung(monkeypatch):
    manual = {"name": "Neo", "youtube": [CID], "gesperrt": True}
    e, radar = run_entdeckt(monkeypatch, cand(), "Clipper gesucht, Link: https://discord.gg/x", creators=[manual])
    assert e["erlaubnis"] == "gesperrt" and e["bereits_manuell"] and radar["vorschlaege"] == []
    assert [c["status"] for c in common.read_json("clip_erlaubnis.json")["creators"]] == ["gesperrt"]


def test_briefing_und_export_zeigen_stufen_ehrlich(tmp_path, monkeypatch):
    common.write_json("clip_entdeckt.json", {"anzahl": 3, "creators": [
        {"name": "Ana", "plattform": "youtube", "erlaubnis": "geduldet", "signale": ["Reddit: 4 Beiträge", "Trends: Rang 3"], "link": "https://a/1", "aufrufe_je_stunde": 800},
        {"name": "Bo", "plattform": "twitch", "erlaubnis": "unklar", "grund": "In r/LivestreamFail 3× genannt", "link": "https://b/1"},
        {"name": "Cy", "plattform": "youtube", "erlaubnis": "erlaubt", "grund": "Aufruf", "link": "https://c/1", "erste_sichtung": common.iso()},
        {"name": "Di", "plattform": "youtube", "erlaubnis": "gesperrt", "link": "https://d/1"}]})
    texts = " ".join(p["text"] for p in briefing.build_sections()[-1]["punkte"])
    assert "geduldet, nicht ausdrücklich erlaubt (Signale: Reddit: 4 Beiträge" in texts and "Im Hype, Erlaubnis offen: Bo" in texts
    assert "Neu entdeckt mit belegter Erlaubnis: Cy" in texts and "Di" not in texts
    monkeypatch.setattr(export, "OUT", tmp_path / "f.json")
    common.record_status("clipscout", 0.0, True, "x")
    export.write()
    ct = json.loads(export.OUT.read_text("utf-8"))["clipteam"]
    assert ct["entdeckt"] == 3 and [h["erlaubnis"] for h in ct["im_hype"]] == ["geduldet", "unklar", "erlaubt"]


def test_clip_erlaubnis_geduldet_braucht_bestaetigung_und_credit(tmp_path, monkeypatch):
    from cudi_video.clip import ClipError, erlaubnis
    monkeypatch.setenv("CUDI_FIRMA_DATEN", str(tmp_path))
    monkeypatch.setattr(erlaubnis, "meta_holen", lambda url: {})
    (tmp_path / "clip_erlaubnis.json").write_text(json.dumps({"creators": [{"name": "Ana", "status": "geduldet", "kanaele": {"twitch": ["ana"]},
                                                                           "signale": ["Reddit: 4 Beiträge"]}]}), "utf-8")
    url = "https://www.twitch.tv/ana/clip/abc"
    assert erlaubnis.pruefe(url)["status"] == "geduldet" and erlaubnis.pruefe(url)["erlaubt"] is False
    with pytest.raises(ClipError, match="nicht ausdrücklich erlaubt"):
        erlaubnis.pruefe_auftrag(url, False)
    r = erlaubnis.pruefe_auftrag(url, True)
    assert r["vermerk"].startswith("geduldet, vom Nutzer bestätigt") and r["credit"] == f"Original: Ana – {url}"
    assert any("Credit" in z for z in erlaubnis.bericht_zeilen(r))


def test_sprachfokus_deutsch(monkeypatch, tmp_path):
    from cudi_video.firma import clipscout, common
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.delenv("CUDI_CLIP_SPRACHEN", raising=False)
    assert clipscout.erlaubte_sprachen() == {"de"}
    de = clipscout.src_de_bekannt()
    assert de and all(c["sprache"] == "de" and c["plattform"] == "twitch" for c in de)
    monkeypatch.setattr(clipscout, "src_kampagnen", lambda camps: [])
    monkeypatch.setattr(clipscout, "src_aufruf_suche", lambda: [])
    monkeypatch.setattr(clipscout, "src_youtube_trends", lambda t, c: [])
    monkeypatch.setattr(clipscout, "src_wikipedia", lambda t, c: [])
    monkeypatch.setattr(clipscout, "src_reddit", lambda: [clipscout._cand("Destiny", "twitch", "destiny", "x", "reddit", 10, sprache="en")])
    notes = []
    out = ECHTE_ENTDECKUNG(notes, [], [], {})
    assert out and all(c["sprache"] == "de" for c in out) and any("Sprachfokus" in n for n in notes)
    monkeypatch.setenv("CUDI_CLIP_SPRACHEN", "de,en")
    assert any(c["name"] == "Destiny" for c in ECHTE_ENTDECKUNG([], [], [], {}))
