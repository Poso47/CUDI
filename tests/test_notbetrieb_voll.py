"""Notbetrieb für alle Arten: Fakten-Auftrag, Ausweichkette der Sprachmodelle, Kommentar je Art (ohne Netz)."""

import importlib.util
import sys
from pathlib import Path

import pytest
import requests

from cudi_video import config, handoff, job, llm, planner

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("notbetrieb_script", SCRIPTS / "notbetrieb.py")
nb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nb)
PRESETS = {"groesste-seen"}


def test_fakten_order_parsed_and_limits():
    o = job.parse_order({"id": "gh0001", "art": "fakten", "thema": "Haie", "plaetze": 5, "sprache": "en", "streng": True}, PRESETS)
    assert o["art"] == "fakten" and o["plaetze"] == 5 and o["sprachen"] == ["en"] and o["streng"] is True
    assert job.parse_order({"id": "gh0002", "art": "fakten", "thema": "Haie"}, PRESETS)["plaetze"] == 5
    for bad in ({"thema": "Haie", "plaetze": 2}, {"thema": "Haie", "plaetze": 11}, {"thema": ""}, {"thema": "Haie", "sprache": "fr"},
                {"thema": "Haie", "plaetze": "viele"}):
        with pytest.raises(job.OrderError):
            job.parse_order({"id": "gh0003", "art": "fakten", **bad}, PRESETS)


def test_all_arts_accepted_in_notbetrieb():
    raws = [{"art": "ranking", "vorlage": "groesste-seen"}, {"art": "fakten", "thema": "Haie"},
            {"art": "story", "stimmung": "creepy", "schritt": "skelett"}, {"art": "reportage", "thema": "Ein Thema für Test"},
            {"art": "satire", "thema": "Ein Thema für Test"}, {"art": "clip", "quelle": "https://example.com/v"}]
    for raw in raws:
        order = nb.prepare_order({**raw, "id": "gh0009"}, PRESETS)
        assert order["art"] == raw["art"] and not order.get("schritt")
    with pytest.raises(job.OrderError):
        nb.prepare_order({"id": "gh0009", "art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten"}, PRESETS)


def test_plan_facts_falls_back_to_topic_as_article(monkeypatch):
    monkeypatch.setattr(handoff, "request", lambda *a, **k: None)
    plan = planner.plan_facts("Haie", 5)
    assert plan["kind"] == "facts" and plan["count"] == 5 and plan["facts"]["articles"]["de"] == ["Haie"]
    monkeypatch.setattr(handoff, "request", lambda *a, **k: {"art": "fakten", "artikel_de": ["Hai"], "artikel_en": ["Shark"],
                                                           "titel_de": "Die 9 Fakten über Haie", "titel_en": "The 9 shark facts"})
    plan = planner.plan_facts("Haie", 5)
    assert plan["count"] == 5 and plan["facts"]["articles"]["en"] == ["Shark"]      # Anzahl aus dem Auftrag gewinnt


def test_fakten_without_any_model_stops_honestly(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "active", lambda: False)
    order = job.parse_order({"id": "gh0004", "art": "fakten", "thema": "Haie"}, PRESETS)
    with pytest.raises(RuntimeError, match="erfunden|Erfunden"):
        job._fakten(order, tmp_path, lambda *a: None)


# --------------------------------------------------------------------------- Ausweichkette

class Resp:
    def __init__(self, status, text="ok"):
        self.status_code, self._text = status, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return {"choices": [{"message": {"content": self._text}}]}


@pytest.fixture
def chain(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://a.example/v1")
    monkeypatch.setattr(config, "LLM_API_KEY", "ka")
    monkeypatch.setattr(config, "LLM_MODEL", "ma")
    monkeypatch.setenv("CUDI_LLM2_BASE_URL", "https://b.example/v1")
    monkeypatch.setenv("CUDI_LLM2_MODEL", "mb")
    monkeypatch.delenv("CUDI_LLM3_BASE_URL", raising=False)


def test_chain_order_and_fallback_on_429(chain, monkeypatch):
    assert [m for _, _, m in llm.providers()] == ["ma", "mb"]
    calls = []

    def post(url, **kw):
        calls.append(url)
        return Resp(429) if "a.example" in url else Resp(200, "von B")

    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.chat("s", "u") == "von B"
    assert calls == ["https://a.example/v1/chat/completions"] * 2 + ["https://b.example/v1/chat/completions"]


def test_chain_retries_same_provider_once_then_succeeds(chain, monkeypatch):
    answers = iter([Resp(503), Resp(200, "zweiter Versuch")])
    monkeypatch.setattr(llm.requests, "post", lambda url, **kw: next(answers))
    assert llm.chat("s", "u") == "zweiter Versuch"


def test_chain_all_fail_raises_and_handoff_gives_none(chain, monkeypatch, tmp_path):
    monkeypatch.setattr(llm.requests, "post", lambda url, **kw: Resp(429))
    with pytest.raises(requests.HTTPError):
        llm.chat("s", "u")
    monkeypatch.delenv(handoff.ENV, raising=False)
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    assert handoff.request("t", "anleitung", {}) is None                      # Textbausteine statt Abbruch


def test_unauthorized_skips_retry(chain, monkeypatch):
    calls = []

    def post(url, **kw):
        calls.append(url)
        return Resp(401) if "a.example" in url else Resp(200, "B")

    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.chat("s", "u") == "B" and len(calls) == 2                       # 401: kein zweiter Versuch beim selben Anbieter


# --------------------------------------------------------------------------- Kommentar

def test_comment_shows_title_variants_texts_and_notes():
    data = {"ok": True, "titel": "Haie", "hinweise": ["Fakt X verworfen"], "pruefbericht": "# Bericht",
            "videos": [{"key": "de", "dauer": 40, "titel_varianten": ["Titel A", "Titel B"], "titel_gewaehlt": "Titel B",
                        "youtube": "Beschreibung", "tiktok": "Text", "qa": {"befunde": ["Lautheit leicht daneben"]}}]}
    text = nb.comment_text(data, "https://run", "https://art")
    for needle in ("Titel A", "Titel B ← gewählt", "Beschreibung", "Text", "Endkontrolle", "Fakt X verworfen", "Prüfbericht", "https://art"):
        assert needle in text
    bare = nb.comment_text({"ok": True, "titel": "Satire", "videos": [{"key": "de"}]}, "https://run")
    assert "keinen fertigen Beschreibungstext" in bare


def test_dry_run_issue_text_to_notbetrieb_inputs():
    """Trockenlauf von auftrag.py: Beispiel-Issue „CUDI Notbetrieb: Test Fakten“ -> Eingaben für notbetrieb.yml."""
    import json

    import auftrag

    body = ('cudi-auftrag\n\n```json\n{"art":"fakten","thema":"Haie","plaetze":5,"sprache":"de"}\n```\n\nSubmit new issue')
    raw = auftrag.extract_json(body)
    order = auftrag.build_json_order(raw, 77, PRESETS)
    assert order["id"] == "gh0077" and order["art"] == "fakten" and order["sprachen"] == ["de"]
    inputs = {"auftrag": json.dumps(order, ensure_ascii=False, separators=(",", ":")), "issue": "77"}
    assert auftrag.summary_line("notbetrieb.yml", inputs).startswith("Notbetrieb · fakten **Haie**")
