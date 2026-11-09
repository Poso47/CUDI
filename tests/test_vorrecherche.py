"""Vorrecherche: Cache-Treffer/-Alter, Rückfall auf live, Pipeline-Anbindung, Mitarbeiter – alles ohne Netz."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from cudi_video import net, pipeline, vorrecherche as vr
from cudi_video.firma import vorrecherche as worker
from cudi_video.models import RankItem, Research
from tests.test_video import make_research, make_spec


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CUDI_VORRECHERCHE", "1")
    monkeypatch.setenv("CUDI_VORRECHERCHE_DIR", str(tmp_path / "vor"))
    monkeypatch.setenv("CUDI_FIRMA_DATEN", str(tmp_path / "firma"))
    from cudi_video.firma import common
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma")
    monkeypatch.delenv("CUDI_VORRECHERCHE_ALTER", raising=False)
    return tmp_path / "vor"


def research_bestaetigt() -> Research:
    r = make_research()
    for it in r.items:
        it.verification = {"status": "bestätigt", "sources": ["Wikidata", "Weltbank"], "evidence": []}
    r.warnings = ["Hinweis aus dem Abgleich"]
    return r


def speichere(spec, stand=None, research=None, **kw):
    key = vr.schluessel(spec)
    entry = vr.eintrag(key, spec, research or research_bestaetigt(), stand or iso(1), **kw)
    vr.schreiben(vr.pfad(key), entry)
    return key


def test_schluessel_ignoriert_id_und_titel_aber_nicht_anzahl_und_sprachen():
    a, b = make_spec(id="eins", count=3), make_spec(id="zwei", count=3, title={"de": "Anders", "en": "Other"})
    assert vr.schluessel(a) == vr.schluessel(b)
    assert vr.schluessel(a) != vr.schluessel(make_spec(count=4))
    assert vr.schluessel(a) != vr.schluessel(make_spec(count=3, langs=["de"]))
    assert vr.schluessel(a) != vr.schluessel(make_spec(count=3, source={"type": "wikidata", "class": "Q8502", "property": "P2044"}))


def test_treffer_junger_eintrag(cache):
    spec = make_spec()
    speichere(spec, stand=iso(2))
    got = vr.lade(make_spec(id="anderes-video"))
    assert got is not None and got.spec_id == "anderes-video"
    assert got.vorrecherche.startswith(iso(2)[:10]) and len(got.items) == 3
    assert got.warnings == ["Hinweis aus dem Abgleich"]
    assert "Vorrecherche vom" in vr.review_zeile(got) and "nicht aus diesem Lauf" in vr.review_zeile(got)


def test_zu_alt_wird_nie_genutzt_und_alter_je_eigenschaft(cache, monkeypatch):
    spec = make_spec()                       # P2048 (Höhe) = langlebig: 30 Tage
    speichere(spec, stand=iso(20))
    assert vr.lade(make_spec()) is not None
    speichere(spec, stand=iso(31))
    assert vr.lade(make_spec()) is None
    einwohner = make_spec(source={"type": "wikidata", "class": "Q6256", "property": "P1082"})     # Einwohner: 7 Tage
    speichere(einwohner, stand=iso(6))
    assert vr.lade(make_spec(source={"type": "wikidata", "class": "Q6256", "property": "P1082"})) is not None
    speichere(einwohner, stand=iso(8))
    assert vr.lade(make_spec(source={"type": "wikidata", "class": "Q6256", "property": "P1082"})) is None
    monkeypatch.setenv("CUDI_VORRECHERCHE_ALTER", "standard=10,P2048=3")        # konfigurierbar
    speichere(spec, stand=iso(5))
    assert vr.lade(make_spec()) is None
    speichere(einwohner, stand=iso(8))
    assert vr.lade(make_spec(source={"type": "wikidata", "class": "Q6256", "property": "P1082"})) is not None


def test_zukunft_kaputt_aus_und_fremder_schluessel(cache, monkeypatch):
    spec = make_spec()
    key = speichere(spec, stand=iso(-3))                    # Stand in der Zukunft = Uhr/Datei unglaubwürdig
    assert vr.lade(make_spec()) is None
    speichere(spec, stand=iso(1))
    assert vr.lade(make_spec()) is not None
    vr.pfad(key).write_bytes(b"kaputt")
    assert vr.lade(make_spec()) is None
    speichere(spec, stand=iso(1))
    monkeypatch.setenv("CUDI_VORRECHERCHE", "0")
    assert vr.lade(make_spec()) is None
    monkeypatch.setenv("CUDI_VORRECHERCHE", "1")
    entry = vr.lesen(vr.pfad(key))
    entry["key"] = "anderer"
    vr.schreiben(vr.pfad(key), entry)
    assert vr.lade(make_spec()) is None


def test_gleicher_inhalt_gleiche_bytes(cache):
    spec = make_spec()
    entry = vr.eintrag(vr.schluessel(spec), spec, research_bestaetigt(), "2026-11-01T01:00:00+00:00")
    vr.schreiben(vr.pfad("a"), entry)
    vr.schreiben(vr.pfad("b"), entry)
    assert vr.pfad("a").read_bytes() == vr.pfad("b").read_bytes()      # keine Scheinänderungen im Repo


def test_anzahl_und_titel_wie_nach_dem_abgleich(cache):
    spec = make_spec(count=3, title={"de": "Die {count} höchsten", "en": "The {count} highest"})
    key = vr.schluessel(spec)
    nach = make_spec(count=3, title={"de": "Die {count} höchsten", "en": "The {count} highest"})
    nach.shrink_to(2)                                      # der Abgleich fand nur 2 verwendbare Plätze
    research = research_bestaetigt()
    research.items = research.items[:2]
    vr.schreiben(vr.pfad(key), vr.eintrag(key, nach, research, iso(1)))
    live = make_spec(count=3, title={"de": "Die 3 höchsten", "en": "The 3 highest"})
    got = vr.lade(live)
    assert len(got.items) == 2 and live.count == 2 and "2" in live.title["de"]


def test_pipeline_nutzt_cache_ohne_netz_und_faellt_zurueck(cache, tmp_path, monkeypatch):
    spec = make_spec()
    speichere(spec, stand=iso(1))
    boom = lambda *a, **k: pytest.fail("kein Netz bei Cache-Treffer")        # noqa: E731
    monkeypatch.setattr(pipeline, "fetch_ranking", boom)
    monkeypatch.setattr(pipeline, "fetch_identifiers", boom)
    monkeypatch.setattr(pipeline, "verify", boom)
    monkeypatch.setattr(pipeline, "load_references", boom)
    monkeypatch.setattr(pipeline, "enrich", lambda research, langs, images=True: None)
    out = tmp_path / "out"
    out.mkdir()
    research = pipeline.research_stage(make_spec(), out, images=False)
    assert research.vorrecherche and len(research.items) == 3
    saved = json.loads((out / "research.json").read_text("utf-8"))
    assert saved["vorrecherche"] == research.vorrecherche
    # zu alt -> live wie bisher
    speichere(spec, stand=iso(40))
    called = []

    def live(spec_, fresh=False):
        called.append("fetch")
        return make_research()

    monkeypatch.setattr(pipeline, "fetch_ranking", live)
    monkeypatch.setattr(pipeline, "fetch_identifiers", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "verify", lambda s, r, strict=False: r)
    monkeypatch.setattr(pipeline, "load_references", lambda s: {})
    r2 = pipeline.research_stage(make_spec(), out, images=False)
    assert called == ["fetch"] and r2.vorrecherche == ""
    # streng: nie aus dem Cache
    speichere(spec, stand=iso(1))
    called.clear()
    pipeline.research_stage(make_spec(), out, images=False, strict=True)
    assert called == ["fetch"]


def test_prueffbericht_vermerkt_vorrecherche(cache):
    from cudi_video.metadata import build_review

    r = research_bestaetigt()
    assert "Vorrecherche" not in build_review(make_spec(), r, [])
    r.vorrecherche = iso(2)
    assert f"Vorrecherche vom {iso(2)[:10]}" in build_review(make_spec(), r, [])


# --------------------------------------------------------------------------- Mitarbeiter

def test_faellig_und_ziele(cache, monkeypatch):
    spec = make_spec()
    assert worker.faellig(spec, cache)                       # fehlt
    speichere(spec, stand=iso(1))
    assert not worker.faellig(spec, cache)                   # 30-Tage-Eigenschaft: erst nach 12 Tagen fällig
    speichere(spec, stand=iso(13))
    assert worker.faellig(spec, cache)
    monkeypatch.setenv("CUDI_VORRECHERCHE_PLAETZE", "10,5")
    todo = worker.ziele([])
    assert {s.count for _, s in todo} == {10, 5} and {tuple(s.langs) for _, s in todo} == {("de",), ("de", "en")}
    assert len({vr.schluessel(s) for _, s in todo}) == len(todo)        # jede Vorgabe einmal


def test_ziele_aus_ideen_nur_planbare_themen(cache):
    ideen = [{"bereich": "ranking", "auftrag": {"art": "ranking", "thema": "die höchsten Berge der Alpen", "plaetze": 5, "sprachen": ["de"]}},
             {"bereich": "ranking", "auftrag": {"art": "ranking", "thema": "Fakten über Kaffeebecher", "plaetze": 7}},
             {"bereich": "ranking", "auftrag": {"art": "ranking", "vorlage": "hoechste-berge", "plaetze": 10}}]
    got = worker.ziele(ideen)
    free = [(n, s) for n, s in got if n.startswith("idee:")]
    assert len(free) == 1 and free[0][1].count == 5 and free[0][1].langs == ["de"]


def test_verarbeite_speichert_nur_vollstaendigen_abgleich(cache, monkeypatch):
    monkeypatch.setattr(worker, "PAUSE_NACH_DROSSELUNG", 0)
    spec = make_spec()
    notes = []
    monkeypatch.setattr(worker, "erzeuge", lambda s: (research_bestaetigt(), s))
    assert worker.verarbeite("t", spec, cache, notes) == "neu"
    assert vr.lade(make_spec()) is not None
    # Drosselung im Abgleich: nichts gespeichert, alter Eintrag bleibt
    vr.pfad(vr.schluessel(spec), cache).unlink()

    def gedrosselt(s):
        net.throttled_count += 2
        return research_bestaetigt(), s

    monkeypatch.setattr(worker, "erzeuge", gedrosselt)
    assert worker.verarbeite("t", spec, cache, notes) == "aufgeschoben"
    assert not vr.pfad(vr.schluessel(spec), cache).exists() and "gedrosselt" in notes[-1]
    # lückenhaft (kaum bestätigt) -> nicht speichern
    def luecke(s):
        r = research_bestaetigt()
        for it in r.items[:2]:
            it.verification = {"status": "nur eine Quelle", "sources": ["Wikidata"], "evidence": []}
        return r, s

    monkeypatch.setattr(worker, "erzeuge", luecke)
    assert worker.verarbeite("t", spec, cache, notes) == "aufgeschoben"


def test_neuer_schwaecherer_abgleich_ersetzt_keinen_besseren(cache, monkeypatch):
    spec = make_spec()
    speichere(spec, stand=iso(1))
    schwach = research_bestaetigt()
    schwach.items[0].verification = {"status": "nur eine Quelle", "sources": ["Wikidata"], "evidence": []}
    monkeypatch.setattr(worker, "erzeuge", lambda s: (schwach, s))
    notes = []
    assert worker.verarbeite("t", spec, cache, notes) == "behalten"
    assert vr.lesen(vr.pfad(vr.schluessel(spec), cache))["status"]["bestätigt"] == 3


def test_aufraeumen_entfernt_verwaiste_und_haelt_groessengrenze(cache, monkeypatch):
    spec = make_spec()
    key = speichere(spec)
    vr.schreiben(vr.pfad("verwaist"), {"v": 1, "key": "verwaist"})
    assert worker.aufraeumen(cache, {key}) == 1 and vr.pfad(key).exists() and not vr.pfad("verwaist").exists()
    monkeypatch.setattr(vr, "MAX_BYTES", 1)
    assert worker.aufraeumen(cache, {key}) == 1 and not vr.pfad(key).exists()


def test_run_ende_zu_ende_mit_attrappe(cache, monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ziele", lambda ideen=None: [("a", make_spec()), ("b", make_spec(count=4))])
    monkeypatch.setattr(worker, "erzeuge", lambda s: (research_bestaetigt(), s))
    monkeypatch.setattr(worker, "PAUSE", 0)
    data = worker.run()
    assert data["neu"] == 2 and len(data["eintraege"]) == 2 and (tmp_path / "firma" / "vorrecherche.json").exists()
    data = worker.run()                                      # zweiter Lauf: alles aktuell, nichts zu tun
    assert data["neu"] == 0 and data["aktuell"] == 2
