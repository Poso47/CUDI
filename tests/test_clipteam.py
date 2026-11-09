"""Clip-Scout und Messung ohne Netz: Feeds/HTML als Fixture."""

import json
from pathlib import Path

import pytest
import yaml

from cudi_video.firma import briefing, clipscout, common, export, lernen, messung

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def daten(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    monkeypatch.setattr(clipscout, "campaigns", lambda notes: [])


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
