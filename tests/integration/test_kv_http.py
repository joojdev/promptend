import pytest
from fastapi.testclient import TestClient

from tests.conftest import ai_tool_call, make_queued_llm


@pytest.fixture()
def env(monkeypatch, tmp_path):
    persona = tmp_path / "persona.md"
    persona.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(persona))
    monkeypatch.delenv("STATE_FILE", raising=False)
    monkeypatch.delenv("KV_MAX_VALUE_BYTES", raising=False)
    monkeypatch.delenv("KV_MAX_KEYS", raising=False)
    return monkeypatch


def _client(llm):
    from src.api.app import create_app

    return TestClient(create_app(llm=llm), raise_server_exceptions=False)


def _write_steps():
    return [
        ai_tool_call("kv_set", {"key": "users/1", "value": {"name": "Ana"}}),
        ai_tool_call("respond", {"body": {"created": True}, "status_code": 201}),
    ]


def _read_steps():
    return [
        ai_tool_call("kv_get", {"key": "users/1"}),
        ai_tool_call("respond", {"body": {"ok": True}}),
    ]


def test_write_then_read_across_requests(env):
    llm = make_queued_llm(*_write_steps(), *_read_steps())
    with _client(llm) as client:
        r1 = client.post("/users", json={"name": "Ana"})
        r2 = client.get("/users/1")

    assert r1.status_code == 201
    assert r2.status_code == 200
    assert llm.calls == 4
    assert '"found": true' in llm.prompts[-1]
    assert '"name": "Ana"' in llm.prompts[-1]


def test_separate_apps_do_not_share_memory(env):
    with _client(make_queued_llm(*_write_steps())) as client:
        assert client.post("/users").status_code == 201

    llm = make_queued_llm(*_read_steps())
    with _client(llm) as client:
        assert client.get("/users/1").status_code == 200
    assert '"found": false' in llm.prompts[-1]


def test_state_file_survives_new_app(env, tmp_path):
    env.setenv("STATE_FILE", str(tmp_path / "state.json"))
    with _client(make_queued_llm(*_write_steps())) as client:
        assert client.post("/users").status_code == 201

    llm = make_queued_llm(*_read_steps())
    with _client(llm) as client:
        assert client.get("/users/1").status_code == 200
    assert '"name": "Ana"' in llm.prompts[-1]


def test_limit_violation_reported_to_agent_not_aborted(env):
    env.setenv("KV_MAX_VALUE_BYTES", "10")
    llm = make_queued_llm(
        ai_tool_call("kv_set", {"key": "blobs/1", "value": "x" * 100}),
        ai_tool_call("respond", {"body": {"error": "too large"}, "status_code": 413}),
    )
    with _client(llm) as client:
        r = client.post("/blobs")
    assert r.status_code == 413
    assert "value too large: 102 bytes exceeds KV_MAX_VALUE_BYTES (10)" in llm.prompts[1]
