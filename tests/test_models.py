"""Tests der Modellanbieter ohne Netzwerk (Attrappen für HTTP-Sitzung bzw. SDK-Client)."""

import copy
from types import SimpleNamespace

import pytest

from cudi.models.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from cudi.models.base import ProviderError
from cudi.models.ollama_provider import OllamaProvider
from cudi.models.openai_provider import OpenAIProvider

TOOLS = [{"name": "remember", "description": "merken",
          "parameters": {"type": "object", "properties": {"content": {"type": "string"}}}}]
HISTORY = [
    {"role": "user", "content": "Merk dir Blau"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "t1", "name": "remember", "arguments": {"content": "Blau"}}]},
    {"role": "tool", "tool_call_id": "t1", "name": "remember", "content": "Gespeichert", "is_error": False},
]


class FakeHTTP:
    def __init__(self, get=None, posts=None):
        self._get = get
        self._posts = list(posts or [])
        self.sent = []

    def get(self, url, timeout=None):
        if isinstance(self._get, Exception):
            raise self._get
        return self._get

    def post(self, url, json=None, headers=None, timeout=None):
        self.sent.append({"url": url, "json": copy.deepcopy(json), "headers": headers})
        return self._posts.pop(0)


class Resp:
    def __init__(self, data, status=200, text=""):
        self._data, self.status_code, self.text = data, status, text

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# ------------------------------------------------------------------ Ollama
def test_ollama_unreachable_is_reported():
    p = OllamaProvider("http://localhost:11434", "llama3.1", session=FakeHTTP(get=ConnectionError("x")))
    ok, info = p.status()
    assert not ok and "nicht erreichbar" in info
    with pytest.raises(ProviderError):
        p.chat("sys", [{"role": "user", "content": "hi"}])


def test_ollama_uses_installed_model_and_parses_tool_calls():
    http = FakeHTTP(
        get=Resp({"models": [{"name": "qwen2.5:7b"}]}),
        posts=[Resp({"message": {"content": "", "tool_calls": [
            {"function": {"name": "remember", "arguments": {"content": "Blau"}}}]},
            "prompt_eval_count": 10, "eval_count": 5})],
    )
    p = OllamaProvider("http://localhost:11434", "llama3.1", session=http)
    ok, info = p.status()
    assert ok and "qwen2.5:7b" in info
    resp = p.chat("sys", HISTORY, TOOLS)
    assert resp.tool_calls[0].name == "remember" and resp.tool_calls[0].arguments == {"content": "Blau"}
    sent = http.sent[0]["json"]
    assert sent["model"] == "qwen2.5:7b" and sent["messages"][0]["role"] == "system"
    assert sent["messages"][-1] == {"role": "tool", "content": "Gespeichert", "tool_name": "remember"}
    assert resp.usage == {"input_tokens": 10, "output_tokens": 5}


def test_ollama_retries_without_tools_if_model_cannot_use_them():
    http = FakeHTTP(get=Resp({"models": [{"name": "llama3.1:latest"}]}),
                    posts=[Resp({}, 400, "model does not support tools"), Resp({"message": {"content": "Hallo"}})])
    p = OllamaProvider("http://localhost:11434", "llama3.1", session=http)
    assert p.chat("sys", [{"role": "user", "content": "hi"}], TOOLS).text == "Hallo"
    assert "tools" in http.sent[0]["json"] and "tools" not in http.sent[1]["json"]


# ------------------------------------------------------------------ OpenAI
def test_openai_requires_key():
    assert not OpenAIProvider("", "gpt-4o", "https://api.openai.com/v1", session=FakeHTTP()).status()[0]


def test_openai_converts_tool_messages():
    http = FakeHTTP(posts=[Resp({"model": "gpt-4o", "choices": [{"message": {"content": "Fertig"}, "finish_reason": "stop"}],
                                 "usage": {"prompt_tokens": 3, "completion_tokens": 1}})])
    p = OpenAIProvider("key", "gpt-4o", "https://api.openai.com/v1", session=http)
    resp = p.chat("sys", HISTORY, TOOLS)
    assert resp.text == "Fertig" and resp.external
    msgs = http.sent[0]["json"]["messages"]
    assert msgs[2]["tool_calls"][0]["function"]["arguments"] == '{"content": "Blau"}'
    assert msgs[3] == {"role": "tool", "tool_call_id": "t1", "content": "Gespeichert"}
    assert http.sent[0]["headers"]["Authorization"] == "Bearer key"


def test_openai_invalid_key_is_explained():
    p = OpenAIProvider("bad", "gpt-4o", "https://api.openai.com/v1", session=FakeHTTP(posts=[Resp({}, 401)]))
    with pytest.raises(ProviderError, match="ungültig"):
        p.chat("sys", [{"role": "user", "content": "hi"}])


# --------------------------------------------------------------- Anthropic
class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def anthropic_client(response):
    messages = FakeMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages), messages=messages), messages


def test_anthropic_request_shape_and_tool_parsing():
    response = SimpleNamespace(
        stop_reason="tool_use", model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        content=[{"type": "text", "text": "Ich speichere das."},
                 {"type": "tool_use", "id": "tu_1", "name": "remember", "input": {"content": "Blau"}}],
    )
    client, messages = anthropic_client(response)
    p = AnthropicProvider("key", "claude-opus-5-5", "medium", client=client)
    resp = p.chat("sys", HISTORY, TOOLS)

    sent = messages.kwargs
    assert sent["model"] == "claude-opus-5-5" and sent["system"] == "sys"
    assert sent["betas"] == [FALLBACK_BETA] and sent["fallbacks"] == "default"
    assert sent["output_config"] == {"effort": "medium"}
    assert sent["tools"][0]["input_schema"]["type"] == "object"
    assert sent["messages"][1]["content"][0] == {"type": "tool_use", "id": "t1", "name": "remember",
                                                  "input": {"content": "Blau"}}
    assert sent["messages"][2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "Gespeichert"}]}
    assert resp.tool_calls[0].id == "tu_1" and resp.text == "Ich speichere das."
    assert resp.raw[1]["type"] == "tool_use"  # Blöcke werden unverändert zurückgespielt
    assert resp.usage == {"input_tokens": 12, "output_tokens": 7}


def test_anthropic_replays_raw_blocks_and_groups_tool_results():
    raw = [{"type": "thinking", "thinking": "", "signature": "sig"},
           {"type": "tool_use", "id": "a", "name": "x", "input": {}},
           {"type": "tool_use", "id": "b", "name": "y", "input": {}}]
    converted = AnthropicProvider.convert([
        {"role": "user", "content": "los"},
        {"role": "assistant", "content": "", "tool_calls": [], "raw": {"provider": "anthropic", "data": raw}},
        {"role": "tool", "tool_call_id": "a", "name": "x", "content": "1", "is_error": False},
        {"role": "tool", "tool_call_id": "b", "name": "y", "content": "2", "is_error": True},
    ])
    assert converted[1]["content"] is raw
    assert len(converted) == 3 and [b["tool_use_id"] for b in converted[2]["content"]] == ["a", "b"]
    assert converted[2]["content"][1]["is_error"] is True


def test_anthropic_refusal_is_reported_honestly():
    client, _ = anthropic_client(SimpleNamespace(stop_reason="refusal", content=[], model="claude-opus-5-5", usage=None))
    resp = AnthropicProvider("key", "claude-opus-5-5", client=client).chat("sys", [{"role": "user", "content": "x"}])
    assert "abgelehnt" in resp.text and not resp.tool_calls


def test_anthropic_without_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    ok, info = AnthropicProvider("", "claude-opus-5-5").status()
    assert not ok
