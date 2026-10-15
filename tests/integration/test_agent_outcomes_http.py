import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolCall

from tests.conftest import RaisingFakeLLM, SlowFakeLLM, ToolCapableFakeLLM


@pytest.fixture()
def make_client(monkeypatch, tmp_path):
    personality = tmp_path / "personality.md"
    personality.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality))

    def _make(llm, **env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        from src.api.app import create_app

        return TestClient(create_app(llm=llm), raise_server_exceptions=False)

    return _make


def _assert_clean(response):
    text = response.text
    assert "Traceback" not in text
    assert "boom secret text" not in text
    assert "test-key" not in text


def _exc(name):
    return type(name, (Exception,), {"__module__": "anthropic"})("boom secret text")


def test_no_response_502(make_client):
    llm = ToolCapableFakeLLM(responses=[], queued_messages=[AIMessage(content="")])
    with make_client(llm) as c:
        r = c.get("/a")
    assert r.status_code == 502
    assert r.json()["error"] == "agent_no_response"
    _assert_clean(r)


def test_loose_text_warning_header(make_client):
    with make_client(ToolCapableFakeLLM(responses=["pong"])) as c:
        r = c.get("/a")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text == "pong"
    assert r.headers["x-promptend-warning"] == "agent did not use a response tool"


def test_timeout_504(make_client):
    with make_client(SlowFakeLLM(responses=["x"], delay=5), AGENT_TIMEOUT_SECONDS="0.2") as c:
        r = c.get("/a")
    assert r.status_code == 504
    assert r.json()["error"] == "agent_timeout"
    _assert_clean(r)


@pytest.mark.parametrize("name", ["APIConnectionError", "AuthenticationError", "RateLimitError"])
def test_provider_failures_503(make_client, name):
    with make_client(RaisingFakeLLM(responses=[], exc=_exc(name))) as c:
        r = c.get("/a")
    assert r.status_code == 503
    assert r.json()["error"] == "llm_unavailable"
    _assert_clean(r)


def test_loop_limit_500(make_client):
    calls = [
        AIMessage(content="", tool_calls=[ToolCall(name="list_files", args={}, id=f"t{i}")])
        for i in range(60)
    ]
    with make_client(ToolCapableFakeLLM(responses=[], queued_messages=calls)) as c:
        r = c.get("/a")
    assert r.status_code == 500
    assert r.json()["error"] == "agent_loop_limit"
    _assert_clean(r)
