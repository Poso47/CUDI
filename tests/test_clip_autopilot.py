"""Clip-Scout-Quellen (Telegram, Discord, eigene Belege) und Clip-Autopilot – ohne Netz."""
import json

import pytest

from cudi_video.firma import clipautopilot, clipscout, common, export

TG_HTML = """<div class="tgme_widget_message" data-post="uwekanal/12"><div class="tgme_widget_message_text">Clipper gesucht! Schneidet meine Streams,
die besten Clips bekommen Preise.</div><time datetime="2026-11-10T12:00:00+00:00"></time></div>
<div class="tgme_widget_message" data-post="uwekanal/13"><div class="tgme_widget_message_text">Heute Stream um 20 Uhr</div></div>"""


@pytest.fixture(autouse=True)
def daten(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    monkeypatch.setattr(clipscout, "campaigns", lambda notes: [])
    monkeypatch.setattr(clipscout, "entdecke", lambda *a, **k: [])
    monkeypatch.setattr(clipscout, "twitch_clips", lambda login, limit=20: [])
    monkeypatch.setenv("CUDI_DISCORD_BOT_TOKEN", "")


def test_aufruf_muster_und_namen():
    assert clipscout.STRONG_SELBST.search("Wir suchen Clipper, wir brauchen Support")      # nur bei eigenen Belegen
    assert clipscout.STRONG_SELBST.search("FLYING UWE SUCHT CLIPPER!") and clipscout.STRONG_SELBST.search("Clipper werden gesucht.")
    assert not clipscout.STRONG.search("Wir suchen Clipper für unser Team")                # fremde Beschreibung: nur Hinweis
    assert not clipscout.STRONG.search("Clip vom Stream gestern")
    assert clipscout.telegram_name("https://t.me/s/uwe_kanal") == "uwe_kanal" and clipscout.telegram_name("t.me/joinchat") == ""
    assert clipscout.discord_code("https://discord.gg/AbC-12") == "AbC-12"
    assert clipscout.kontakt_links(["Telegram: t.me/meinkanal, Discord: discord.gg/xyz99"]) == {"telegram": ["meinkanal"], "discord": ["xyz99"]}


def test_telegram_vorschau_wird_beleg():
    posts = clipscout.telegram_posts("uwekanal", html=TG_HTML)
    assert [p["url"] for p in posts] == ["https://t.me/uwekanal/12", "https://t.me/uwekanal/13"]
    belege = clipscout.evidence_from_posts(posts, "telegram")
    assert belege and belege[0]["art"] == "telegram" and belege[0]["staerke"] == "eindeutig" and belege[0]["datum"] == "2026-11-10"
    assert clipscout.decide({"name": "U"}, belege)["status"] == "erlaubt"


def test_eigener_beleg_macht_erlaubt_und_verbot_sperrt():
    b = clipscout.manueller_beleg({"url": "https://www.tiktok.com/@flyinguwe", "zitat": "Wir suchen Clipper. Clipper werden gesucht.",
                                   "datum": "2026-11-16"})
    assert b["art"] == "aufruf" and b["staerke"] == "eindeutig"
    assert clipscout.manueller_beleg({"url": "ftp://x", "zitat": "Wir suchen Clipper", "datum": "2026-11-16"}) is None
    assert clipscout.decide({"name": "U"}, [b])["status"] == "erlaubt"
    verbot = clipscout.manueller_beleg({"url": "https://x.de/a", "zitat": "Bitte keine Clips von meinen Streams", "datum": "2026-11-01"})
    assert clipscout.decide({"name": "U"}, [b, verbot])["status"] == "gesperrt"


def test_scout_lauf_mit_telegram_discord_und_eigenem_beleg(monkeypatch):
    common.write_json("clip_creators.json", {"creators": [{"name": "Flying Uwe", "youtube": [], "twitch": ["flyinguwe"],
        "tiktok": [], "telegram": ["https://t.me/uwekanal"], "discord": ["https://discord.gg/uwe1"],
        "hinweis": "Kontakt: erstes Wort „Clipper“"}]})

    class R:
        def __init__(self, text="", data=None): self.text, self._d = text, data
        def json(self): return self._d
    def fetch(url, **kw):
        if "t.me/s/" in url:
            return R(TG_HTML)
        if "/invites/" in url:
            return R(data={"guild": {"id": "9", "name": "Uwes Server", "description": "Clipper gesucht – Regeln im Kanal"},
                           "approximate_member_count": 1200})
        raise AssertionError(url)
    monkeypatch.setattr(common, "fetch", fetch)
    clipscout.run()
    erl = common.read_json("clip_erlaubnis.json")["creators"][0]
    assert erl["status"] == "erlaubt" and {b["art"] for b in erl["belege"]} >= {"telegram", "discord"}
    assert erl["kanaele"]["telegram"] == ["uwekanal"] and erl["kanaele"]["discord"] == ["https://discord.gg/uwe1"]
    assert "Kontakt: erstes Wort „Clipper“" in erl["bedingungen"]
    assert any("Discord-Lese-Bot nicht eingerichtet" in h for h in common.read_json("clip_radar.json")["hinweise"])


def test_discord_bot_liest_nur_passende_kanaele(monkeypatch):
    seen = []

    class R:
        def __init__(self, d): self._d = d
        def json(self): return self._d
    def fetch(url, **kw):
        seen.append(url)
        assert kw["headers"]["Authorization"] == "Bot geheim"
        if url.endswith("/users/@me/guilds"):
            return R([{"id": "9", "name": "Uwes Server"}])
        if url.endswith("/guilds/9/channels"):
            return R([{"id": "1", "type": 0, "name": "clipper-infos"}, {"id": "2", "type": 0, "name": "allgemein"}])
        return R([{"id": "77", "content": "Clipper gesucht! Regeln: Credit Pflicht", "timestamp": "2026-11-12T10:00:00+00:00"}])
    monkeypatch.setattr(common, "fetch", fetch)
    out = clipscout.discord_bot_posts([], token="geheim")
    assert out["9"]["posts"][0]["url"] == "https://discord.com/channels/9/1/77"
    assert not any("/channels/2/" in u for u in seen)                      # „allgemein“ wird nicht gelesen


def _radar_und_erlaubnis(status="erlaubt"):
    common.write_json("clip_radar.json", {"videos": [
        {"creator": "Flying Uwe", "url": "https://www.youtube.com/watch?v=a1", "titel": "Stream-Moment", "aufrufe_je_stunde": 900,
         "erlaubnis": status, "veroeffentlicht": common.iso()},
        {"creator": "Anderer", "url": "https://www.youtube.com/watch?v=b2", "titel": "x", "aufrufe_je_stunde": 5000,
         "erlaubnis": "geduldet", "veroeffentlicht": common.iso()}], "clip_posts": []})
    common.write_json("clip_erlaubnis.json", {"creators": [{"name": "Flying Uwe", "status": status, "kanaele": {"twitch": ["flyinguwe"]},
        "belege": [{"url": "https://www.tiktok.com/@flyinguwe", "zitat": "Wir suchen Clipper", "datum": "2026-11-16", "staerke": "eindeutig"}]}]})


def test_autopilot_schneidet_nur_erlaubtes_und_haelt_tagesgrenze():
    _radar_und_erlaubnis()
    common.write_json("clip_autopilot_einstellungen.json", {"max_pro_tag": 1})
    gestartet = []

    def runner(order, folder, via_claude=True):
        assert via_claude is False and order["hochladen"]["freigabe"] is False
        gestartet.append(order)
        return 0, {"ok": True, "hochgeladen": [{"ziel": "youtube", "ok": True, "url": "https://youtu.be/neu1"}]}
    res = clipautopilot.run(runner=runner)
    assert len(gestartet) == 1 and gestartet[0]["quelle"] == "https://www.youtube.com/watch?v=a1"   # geduldet nie
    assert res["neu"][0]["ok"] and res["neu"][0]["credit"].startswith("Original: Flying Uwe")
    assert common.read_json("clip_radar.json")["clip_posts"] == ["https://youtu.be/neu1"]
    gestartet.clear()
    clipautopilot.run(runner=runner)                                          # Tagesgrenze erreicht, Quelle schon fertig
    assert gestartet == []
    ap = export._autopilot()
    assert ap["heute"] == 1 and ap["letzte"][0]["links"] == ["https://youtu.be/neu1"]


def test_autopilot_ohne_erlaubnis_und_fehlschlaege():
    _radar_und_erlaubnis(status="geduldet")
    assert clipautopilot.run(runner=lambda *a, **k: pytest.fail("darf nicht starten"))["neu"] == []
    _radar_und_erlaubnis()
    common.write_json("clip_autopilot_einstellungen.json", {"max_versuche": 2})
    calls = []
    def kaputt(order, folder, via_claude=True):
        calls.append(order["id"])
        return 1, {"ok": False, "fehler": "YouTube sperrt die Cloud-Adresse"}
    for _ in range(3):
        clipautopilot.run(runner=kaputt)
    quelle = clipautopilot._id("https://www.youtube.com/watch?v=a1")
    assert calls.count(quelle) == 2                                           # höchstens 2 Versuche je Quelle
    assert json.dumps(common.read_json("clip_autopilot.json"), ensure_ascii=False).count("YouTube sperrt") >= 2
