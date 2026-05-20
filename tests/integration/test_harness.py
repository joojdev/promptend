import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolCall

from tests.conftest import ToolCapableFakeLLM


@pytest.fixture()
def app_client(monkeypatch, tmp_path):
    personality = tmp_path / "personality.md"
    personality.write_text("Test persona.")

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality))

    fake_llm = ToolCapableFakeLLM(responses=["pong"])

    from src.api.app import create_app

    application = create_app(llm=fake_llm)
    with TestClient(application) as client:
        yield client


# T008
def test_health_check(app_client):
    response = app_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "agent": "ready"}


# T009
def test_catch_all_returns_reply_key(app_client):
    response = app_client.post("/hello", content="hi")
    assert response.status_code == 200
    assert "reply" in response.json()


# T024
def test_agent_invokes_respond_tool_and_returns_reply(monkeypatch, tmp_path):
    personality = tmp_path / "personality.md"
    personality.write_text("Test persona.")

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality))

    tool_call_msg = AIMessage(
        content="",
        tool_calls=[ToolCall(name="respond", args={"reply": "eat my shorts"}, id="tc1")],
    )
    fake_llm = ToolCapableFakeLLM(responses=[], queued_messages=[tool_call_msg])

    from src.api.app import create_app

    application = create_app(llm=fake_llm)
    with TestClient(application) as client:
        response = client.post(
            "/api/echo",
            content='{"repeat_this": "eat my shorts"}',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 200
    assert response.json() == {"reply": "eat my shorts"}
