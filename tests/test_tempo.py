"""Tempo: Zeitmessung, gebündelte Schreibrunde, parallele Quellen – alles ohne Netz."""

import json
import threading
import time

import pytest

from cudi_video import enrich, handoff, media, metadata, narrate, zeiten
from tests.test_video import make_research, make_spec


@pytest.fixture
def writing(tmp_path, monkeypatch):
    monkeypatch.setenv(handoff.ENV, "1")
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    return tmp_path


def test_zeiten_exclusive_and_persisted(tmp_path):
    zeiten.reset()
    with zeiten.stufe("aussen"):
        time.sleep(0.03)
        with zeiten.stufe("innen"):
            time.sleep(0.1)
    snap = zeiten.snapshot()
    assert zeiten._totals["innen"] >= 0.1 and zeiten._totals["aussen"] < 0.09             # innere Zeit wird nicht doppelt gezählt
    zeiten.speichern(tmp_path)
    zeiten.reset()
    zeiten.laden(tmp_path)                                           # Fortsetzen nach Schreibaufgabe addiert
    zeiten.laden(tmp_path)
    assert zeiten.snapshot()["innen"] >= 0.2
    section = zeiten.review_section(zeiten.bericht(tmp_path))
    assert section.startswith("## Zeiten") and "Summe" in section
    zeiten.reset()


def test_bundle_one_round_for_narration_and_titles(writing):
    spec, research = make_spec(), make_research()
    tasks = [narrate.task(spec, research, ["de"]), metadata.title_task(spec, research, ["de"])]
    assert all(tasks)
    with pytest.raises(handoff.WritingNeeded) as need:
        handoff.request_many(tasks)
    bundle = json.loads(need.value.path.read_text("utf-8"))
    assert set(bundle["daten"]) == {"erzaehlen", "titel"} and bundle["antwort"] is None
    assert "BÜNDEL" in bundle["anleitung"]
    # Claude antwortet nur auf „titel“ – „erzaehlen“ fehlt und wird dann ganz normal einzeln gefragt
    bundle["antwort"] = {"titel": {"de": ["A", "B", "C"]}}
    need.value.path.write_text(json.dumps(bundle), "utf-8")
    handoff.request_many(tasks)                                      # verteilt die Antworten, wirft nichts mehr
    assert metadata.request_titles(spec, research, ["de"]) == {"de": ["A", "B", "C"]}
    with pytest.raises(handoff.WritingNeeded) as single:
        narrate.request(spec, research, ["de"])
    assert single.value.path.name == "schreiben_erzaehlen.json"
    handoff.request_many(tasks)                                      # nie eine zweite Bündelrunde (keine Endlosschleife)


def test_bundle_skipped_when_inactive_or_single(monkeypatch, tmp_path):
    monkeypatch.delenv(handoff.ENV, raising=False)
    handoff.request_many([("a", "x", {}), ("b", "y", {})])           # nicht aktiv: nichts
    monkeypatch.setenv(handoff.ENV, "1")
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    (tmp_path / "schreiben_a.json").write_text(json.dumps({"antwort": 1}), "utf-8")
    handoff.request_many([("a", "x", {}), ("b", "y", {})])           # nur eine offen: kein Bündel, kein Wurf
    assert not list(tmp_path.glob("schreiben_buendel*"))


def test_gather_runs_sources_in_parallel_and_keeps_order():
    item = make_research().items[0]
    started = []

    def slow(tag):
        def source(_item):
            started.append(tag)
            time.sleep(0.2)
            return [tag]
        source.__name__ = tag
        return source

    t = time.time()
    result = media.gather((slow("a"), slow("b"), slow("c"), slow("d")), item)
    assert time.time() - t < 0.6 and result == ["a", "b", "c", "d"]


def test_gather_survives_failing_source():
    item = make_research().items[0]

    def broken(_item):
        raise media.net.FetchError("down")

    assert media.gather((broken, lambda i: [1]), item) == [1]


def test_parallel_map_keeps_order_and_wikimedia_pace(monkeypatch):
    assert enrich.parallel_map(lambda x: x * 2, [1, 2, 3, 4]) == [2, 4, 6, 8]
    seen = set()
    enrich.parallel_map(lambda x: seen.add(threading.get_ident()), range(6), workers=3)
    assert len(seen) >= 1
    enrich._wm_last[0] = 0.0
    t = time.monotonic()
    enrich.wikimedia_pace(0.15)
    enrich.wikimedia_pace(0.15)
    assert time.monotonic() - t >= 0.14


def test_loudnorm_filter_falls_back(monkeypatch, tmp_path):
    from cudi_video import qa

    monkeypatch.setattr(qa, "_run", lambda *a, **k: (_ for _ in ()).throw(OSError("kein ffmpeg")))
    assert qa.loudnorm_filter(tmp_path / "x.wav").startswith("loudnorm=I=-14")
