from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.tools import BaseTool

from src.auth.tokens import TokenStore
from tests.conftest import CountingFakeLLM, ai_tool_call, enable_auth, user_token


class AdminOnlyTool(BaseTool):
    name: str = "admin_only"
    description: str = "test tool for admins"
    role: str = "admin"

    def _run(self) -> str:
        return "secret"


class RecordingLLM(CountingFakeLLM):
    """Each bind_tools returns a copy that remembers its tool names; `seen` logs them per call."""

    bound: list[str] = []
    seen: list[list[str]] = []

    def bind_tools(self, tools, **kwargs: Any):
        names = [t.name for t in tools]
        self.seen.append(["bind", *names])
        return self.model_copy(update={"bound": names})

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(self.bound))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture()
def env(monkeypatch, tmp_path):
    import src.agent.harness as harness

    persona = tmp_path / "persona.md"
    persona.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(persona))
    monkeypatch.delenv("STATE_FILE", raising=False)
    real = harness.build_tools
    monkeypatch.setattr(harness, "build_tools", lambda store: [*real(store), AdminOnlyTool()])
    return tmp_path / "tokens.db"


def _llm():
    return RecordingLLM(
        responses=[""],
        queued_messages=[ai_tool_call("respond", {"body": "hi"}) for _ in range(4)],
        calls=0,
        prompts=[],
        seen=[],
    )


def _calls(llm):
    """Tool lists the model was invoked with (bind records dropped)."""
    return [names for names in llm.seen if names[:1] != ["bind"]]


def _get(llm, headers=None):
    from src.api.app import create_app

    with TestClient(create_app(llm=llm)) as c:
        r = c.get("/a", headers=headers or {})
    assert r.status_code == 200
    return _calls(llm)[-1]


def test_both_agents_built(env):
    llm = _llm()
    _get(llm)
    binds = [names[1:] for names in llm.seen if names[:1] == ["bind"]]
    assert any("admin_only" in names for names in binds)
    assert any("admin_only" not in names and "respond" in names for names in binds)


def test_user_token_gets_user_tools(monkeypatch, env):
    enable_auth(monkeypatch)
    token = user_token(env)
    names = _get(_llm(), {"Authorization": f"Bearer {token}"})
    assert "respond" in names and "admin_only" not in names


def test_admin_token_gets_admin_tools(monkeypatch, env):
    enable_auth(monkeypatch)
    token = TokenStore(env).issue_admin_token(60).token
    names = _get(_llm(), {"Authorization": f"Bearer {token}"})
    assert "admin_only" in names and "respond" in names


def test_auth_disabled_no_token_is_user(env):
    names = _get(_llm())
    assert "admin_only" not in names


def test_auth_disabled_admin_token_is_admin(env):
    token = TokenStore(env).issue_admin_token(60).token
    names = _get(_llm(), {"Authorization": f"Bearer {token}"})
    assert "admin_only" in names
