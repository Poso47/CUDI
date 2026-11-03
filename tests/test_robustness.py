"""Robustheit: parallele Läufe, Wikidata-Zeitreihen, Bildrechte, Drosselung, Audio, Zugangscode, Auftragsliste."""

import json

import numpy as np
import pytest


# --------------------------------------------------------------------------- eigene Ausgabeordner

def test_output_folders_are_unique_within_one_second(tmp_path, monkeypatch):
    from cudi_video import config

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    folders = [config.new_output_folder("hoechste-berge") for _ in range(3)]
    assert len({f.name for f in folders}) == 3            # nie derselbe Ordner für zwei Läufe
    assert all(f.is_dir() and f.parent == tmp_path for f in folders)


def test_story_and_ranking_use_unique_folders(tmp_path, monkeypatch):
    from cudi_video import config
    from cudi_video.pipeline import new_output_dir
    from cudi_video.spec import list_presets
    from cudi_video.story.pipeline import new_folder

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    spec = list_presets()[0]
    assert new_output_dir(spec) != new_output_dir(spec)
    assert new_folder("Die Story") != new_folder("Die Story")


# --------------------------------------------------------------------------- neuester Wert vor dem LIMIT

def test_queries_keep_only_latest_statement_before_limit():
    from cudi_video.sources import wikidata
    from cudi_video.spec import WikidataSource

    src = WikidataSource(cls="Q6256", property="P1082", order="desc", min_value=50_000_000)
    query = wikidata.build_ranking_query(src)
    latest = query.index("?ownDate")
    # Auswahl der neuesten Aussage steht vor Wertfilter und LIMIT – alte Werte können nicht durchrutschen
    assert latest < query.index("FILTER(?value >=") < query.index("LIMIT")
    assert "?newerDate > ?ownDate" in query and "FILTER(BOUND(?date) || NOT EXISTS" in query


def test_fallback_route_also_keeps_only_latest(monkeypatch):
    from cudi_video.sources import wikidata
    from cudi_video.spec import WikidataSource

    seen = []
    monkeypatch.setattr(wikidata, "_sparql", lambda q, **kw: seen.append(q) or [])
    wikidata._statements_for(WikidataSource(cls="Q8502", property="P2044"), ["Q513"])
    assert seen and "?newerDate > ?ownDate" in seen[0] and "psn:P2044 [] ; pq:P585" in seen[0]


# --------------------------------------------------------------------------- Bildrechte

@pytest.mark.parametrize("meta, license_name, expected", [
    ({"Artist": {"value": "<a href='x'>Jane Doe</a>"}}, "CC BY-SA 4.0", "Jane Doe"),
    ({"Artist": {"value": "Unknown author"}}, "CC BY-SA 3.0", None),        # Namensnennung nötig, Urheber fehlt
    ({}, "CC BY 2.0", None),
    ({"Artist": {"value": "unknown"}, "Attribution": {"value": "Foto: Max Muster"}}, "CC BY 4.0", "Foto: Max Muster"),
    ({"Artist": {"value": "Unknown author"}}, "Public domain", "Urheber unbekannt"),   # gemeinfrei: erlaubt
    ({}, "CC0", "Urheber unbekannt"),
    ({"AttributionRequired": {"value": "true"}}, "Public domain", None),             # Commons-Angabe zählt
])
def test_credit_author_requires_author_when_license_does(meta, license_name, expected):
    from cudi_video.enrich import credit_author

    assert credit_author(meta, license_name) == expected


def test_image_without_author_is_not_used(monkeypatch):
    from cudi_video import enrich, net
    from cudi_video.models import RankItem

    monkeypatch.setattr(net, "get_json", lambda *a, **kw: {"query": {"pages": [{"imageinfo": [{
        "width": 2000, "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}}}]}]}})
    monkeypatch.setattr(net, "download", lambda *a, **kw: pytest.fail("Bild ohne Urheber darf nicht geladen werden"))
    item = RankItem(qid="Q1", value=1, unit="1", image_file="Bild.jpg")
    assert enrich.fetch_image(item) is True and not item.image_path and not item.image_credit


# --------------------------------------------------------------------------- Drosselung läuft ab

def test_host_block_expires_and_clears(monkeypatch):
    from cudi_video import net

    now = [1000.0]
    monkeypatch.setattr(net.time, "monotonic", lambda: now[0])
    net.reset_blocks()
    for _ in range(net.BLOCK_AFTER):
        net._note_throttled("wikipedia.org")
    assert net.is_blocked("wikipedia.org")
    now[0] += net.BLOCK_SECONDS + 1                       # nach der Pause wird wieder angefragt
    assert not net.is_blocked("wikipedia.org")
    net._note_throttled("wikipedia.org")                  # scheitert es erneut, gilt die Sperre sofort wieder
    assert net.is_blocked("wikipedia.org")
    net._note_ok("wikipedia.org")                         # ein Erfolg hebt sie auf
    assert not net.is_blocked("wikipedia.org") and "wikipedia.org" not in net._blocked_hosts


def test_blocked_host_raises_until_expiry(monkeypatch):
    from cudi_video import net

    now = [50.0]
    monkeypatch.setattr(net.time, "monotonic", lambda: now[0])
    net.reset_blocks()
    for _ in range(net.BLOCK_AFTER):
        net._note_throttled("example.org")
    with pytest.raises(net.FetchError):
        net.get("https://example.org/x", retries=0)
    net.reset_blocks()                                    # neuer Auftrag beginnt ohne Sperre
    assert not net.is_blocked("example.org")


# --------------------------------------------------------------------------- Ducking in linearer Zeit

@pytest.mark.parametrize("n, width", [(50_000, 4800), (20_000, 9600), (12_345, 7), (9600, 9600)])
def test_moving_average_matches_convolution(n, width):
    from cudi_video.render.video import moving_average

    x = np.random.default_rng(n).random(n).astype(np.float32)
    expected = np.convolve(x, np.ones(width) / width, mode="same")
    assert np.allclose(moving_average(x, width), expected, atol=1e-6)


# --------------------------------------------------------------------------- Zugangscode mit Umlauten

class _Req:
    def __init__(self, header=None, query=None):
        self.headers = {"X-Token": header} if header is not None else {}
        self.query_params = {"token": query} if query is not None else {}


@pytest.mark.parametrize("req", [
    _Req(header="M%C3%BCnchen"),                  # so sendet die Oberfläche (URL-kodiert)
    _Req(header="München"),                       # Latin-1 im Header
    _Req(header="MÃ¼nchen"),                      # UTF-8-Bytes, als Latin-1 gelesen (curl & Co.)
    _Req(query="München"),                        # Link mit ?token=
])
def test_token_with_umlaut_is_accepted(monkeypatch, req):
    from cudi_video import config
    from cudi_video.web import app

    monkeypatch.setattr(config, "WEB_TOKEN", "München")
    app._check_token(req)                         # darf weder abstürzen noch ablehnen


@pytest.mark.parametrize("req", [_Req(header="Köln"), _Req(header="falsch"), _Req(), _Req(query="Münch")])
def test_wrong_token_is_rejected_not_crashing(monkeypatch, req):
    from fastapi import HTTPException

    from cudi_video import config
    from cudi_video.web import app

    monkeypatch.setattr(config, "WEB_TOKEN", "München")
    with pytest.raises(HTTPException) as err:
        app._check_token(req)
    assert err.value.status_code == 401


# --------------------------------------------------------------------------- Auftragsliste

def test_jobs_list_returns_copies_and_skips_broken_folders(tmp_path, monkeypatch):
    from cudi_video import config
    from cudi_video.web import app

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "WEB_TOKEN", "")
    good = tmp_path / "20261101-120000_test"
    good.mkdir()
    (good / "spec.json").write_text(json.dumps({"title": {"de": "Test"}}), "utf-8")
    (good / "result.json").write_text(json.dumps({"videos": {}}), "utf-8")
    broken = tmp_path / "20261101-130000_kaputt"          # result.json ohne spec.json
    broken.mkdir()
    (broken / "result.json").write_text("{}", "utf-8")
    (tmp_path / "_work").mkdir()                          # Arbeitsordner werden nie gelistet

    monkeypatch.setattr(app, "_jobs", {"a1": {"id": "a1", "title": "Läuft", "status": "läuft",
                                              "created": "2026-11-01T12:00:00", "folder": None}})
    listed = app.jobs(_Req())
    assert [j["id"] for j in listed] == ["a1", "disk-20261101-120000_test"]
    listed[0]["status"] = "verändert"                     # Kopie: der Auftrag selbst bleibt unberührt
    assert app._jobs["a1"]["status"] == "läuft"


def test_tts_retries_until_the_free_service_delivers(tmp_path, monkeypatch):
    """Gratis-Sprachdienst liefert zeitweise nichts: weiter versuchen, Ursache in der Meldung."""
    import asyncio
    from cudi_video import tts

    calls = {"n": 0}

    class Flaky:
        def __init__(self, *a, **k):
            calls["n"] += 1

        async def stream(self):
            if calls["n"] < 4:
                raise RuntimeError("No audio was received.")
            yield {"type": "audio", "data": b"ID3"}
            yield {"type": "WordBoundary", "offset": 0, "duration": 5_000_000, "text": "Hallo"}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(tts.edge_tts, "Communicate", Flaky)
    monkeypatch.setattr(tts.asyncio, "sleep", no_sleep)
    words = asyncio.run(tts._synthesize("Hallo", "de-DE-X", tmp_path / "a.mp3", "+0%"))
    assert calls["n"] == 4 and words[0]["text"] == "Hallo"

    calls["n"] = -100                                                    # scheitert immer
    with pytest.raises(RuntimeError, match="No audio was received"):
        asyncio.run(tts._synthesize("Hallo", "de-DE-X", tmp_path / "b.mp3", "+0%"))


def test_piper_takes_over_the_whole_video_when_edge_tts_is_down(tmp_path, monkeypatch):
    """Microsoft-Dienst aus: alle Abschnitte mit der Offline-Ersatzstimme, Hinweis fürs Ergebnis."""
    from cudi_video import tts

    async def down(*a, **k):
        raise RuntimeError("Sprachausgabe fehlgeschlagen (No audio was received.)")

    class Chunk:
        audio_int16_bytes = (np.sin(np.arange(3200) / 5) * 8000).astype(np.int16).tobytes()   # 0,2 s Ton

    class FakeVoice:
        class config:
            sample_rate = 16000

        def synthesize(self, text, syn_config=None):
            yield Chunk()

    used = []
    monkeypatch.setattr(tts, "_synthesize", down)
    monkeypatch.setattr(tts, "_piper_voice", lambda key: used.append(key) or FakeVoice())
    monkeypatch.setattr(tts, "_piper_config", lambda scale: None)
    tts.take_notes()
    res = tts.voice_texts(["Hallo Welt. Wie geht es?", "Zweiter Text!"], tmp_path, "de-DE-KatjaNeural")
    assert used[0] == ("de", "f") and len(res) == 2
    wav, words, duration = res[0]
    assert wav.exists() and [w["text"] for w in words] == ["Hallo", "Welt", "Wie", "geht", "es"]
    assert 0.3 < duration < 0.5 and words[0]["start"] == 0 and words[-1]["end"] <= 0.41
    assert any("Ersatzstimme" in n for n in tts.take_notes())
    assert tts.piper_key("en-US-AndrewNeural") == ("en", "m")


def test_piper_takes_over_at_once_when_one_section_is_exhausted(tmp_path, monkeypatch):
    """Kompletter Ausfall: nicht auf die Wiederholungen jedes Abschnitts warten."""
    import asyncio
    import time as _time
    from cudi_video import tts

    async def edge(text, *a, **k):
        if text.startswith("A"):
            raise RuntimeError("Sprachausgabe fehlgeschlagen (No audio was received.)")
        await asyncio.sleep(30)                                  # die anderen hängen noch in ihren Versuchen

    class Chunk:
        audio_int16_bytes = (np.sin(np.arange(1600) / 5) * 8000).astype(np.int16).tobytes()

    class FakeVoice:
        class config:
            sample_rate = 16000

        def synthesize(self, text, syn_config=None):
            yield Chunk()

    monkeypatch.setattr(tts, "_synthesize", edge)
    monkeypatch.setattr(tts, "_piper_voice", lambda key: FakeVoice())
    monkeypatch.setattr(tts, "_piper_config", lambda scale: None)
    start = _time.time()
    res = tts.voice_texts(["A eins.", "B zwei.", "C drei.", "D vier."], tmp_path, "en-US-AndrewNeural")
    assert len(res) == 4 and _time.time() - start < 10
    tts.take_notes()
