"""Notbetrieb: Schreibaufgaben über ein freies Sprachmodell (llm.chat gemockt), wenn Claude nicht verfügbar ist."""

import json

import pytest

from cudi_video import config, handoff, narrate, planner
from tests.test_video import make_research, make_spec


@pytest.fixture
def notbetrieb(tmp_path, monkeypatch):
    monkeypatch.delenv(handoff.ENV, raising=False)
    monkeypatch.delenv(handoff.PREFS_ENV, raising=False)
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setattr(config, "LLM_MODEL", "test-modell")
    calls = []

    def fake_chat(system, user, **kw):
        calls.append(user)
        return fake_chat.reply

    fake_chat.reply = "{}"
    fake_chat.calls = calls
    monkeypatch.setattr("cudi_video.llm.chat", fake_chat)
    return fake_chat, tmp_path


def test_parse_json_answer_strips_fences_and_text():
    assert handoff.parse_json_answer('Klar!\n```json\n{"a": [1, 2]}\n```\nViel Erfolg') == {"a": [1, 2]}
    assert handoff.parse_json_answer("[1, 2]") == [1, 2]
    assert handoff.parse_json_answer("kein json") is None


def test_answers_and_caches_in_task_file(notbetrieb):
    chat, folder = notbetrieb
    chat.reply = '```json\n{"art": "ranking"}\n```'
    assert handoff.active() and not handoff.enabled()
    assert handoff.request("planen", "Plane.", {"wunsch": "x"}) == {"art": "ranking"}
    assert "Plane." in chat.calls[0] and '"wunsch": "x"' in chat.calls[0]
    saved = json.loads((folder / "schreiben_planen.json").read_text("utf-8"))
    assert saved["antwort"] == {"art": "ranking"}
    chat.reply = "{}"
    assert handoff.request("planen", "Plane.", {"wunsch": "x"}) == {"art": "ranking"}     # aus der Aufgabendatei
    assert len(chat.calls) == 1


def test_adds_preferences(notbetrieb, monkeypatch):
    chat, _ = notbetrieb
    chat.reply = '{"ok": 1}'
    monkeypatch.setenv(handoff.PREFS_ENV, json.dumps({"gut": ["kurz"], "schlecht": []}))
    handoff.request("x", "Anleitung", {})
    assert "vorlieben" in chat.calls[0] and "kurz" in chat.calls[0]


def test_failures_give_none_and_are_not_cached(notbetrieb, monkeypatch):
    chat, folder = notbetrieb

    def boom(*a, **k):
        raise OSError("Netz weg")

    monkeypatch.setattr("cudi_video.llm.chat", boom)
    assert handoff.request("planen", "x", {}) is None
    monkeypatch.setattr("cudi_video.llm.chat", chat)
    chat.reply = "Ich kann nicht."
    assert handoff.request("planen", "x", {}) is None
    assert not (folder / "schreiben_planen.json").exists()


def test_claude_mode_has_priority(notbetrieb, monkeypatch):
    chat, _ = notbetrieb
    monkeypatch.setenv(handoff.ENV, "1")
    with pytest.raises(handoff.WritingNeeded):
        handoff.request("planen", "x", {})
    assert chat.calls == []


def test_inactive_without_claude_and_llm(monkeypatch):
    monkeypatch.delenv(handoff.ENV, raising=False)
    monkeypatch.setattr(config, "LLM_BASE_URL", "")
    assert not handoff.active() and handoff.request("t", "x", {}) is None


def test_narration_and_planning_run_through_llm(notbetrieb):
    chat, _ = notbetrieb
    spec, research = make_spec(), make_research()
    chat.reply = json.dumps({"de": {"1": "Turm A misst 828 Meter. Ein Rekord."}})
    narrate.request(spec, research, ["de"])
    assert chat.calls and "plaetze" in chat.calls[0]
    chat.reply = json.dumps({"fehler": "nicht darstellbar"})
    with pytest.raises(planner.PlanFailed):
        planner.plan_with_claude("irgendwas", 10)
