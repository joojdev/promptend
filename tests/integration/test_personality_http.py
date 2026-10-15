from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from tests.conftest import ai_tool_call, make_queued_llm

PRESETS = Path("config/personalities")


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.delenv("PERSONALITY_PATH", raising=False)
    monkeypatch.delenv("PERSONALITY", raising=False)
    monkeypatch.delenv("STATE_FILE", raising=False)
    return monkeypatch


def _run_one(llm):
    from src.api.app import create_app

    app = create_app(llm=llm)
    with capture_logs() as logs:
        with TestClient(app) as client:
            response = client.get("/hello")
    startup = [e for e in logs if e["event"] == "harness_startup"]
    assert len(startup) == 1
    return response, startup[0]


def test_preset_selected_by_name(env):
    env.setenv("PERSONALITY", "shop")
    llm = make_queued_llm(ai_tool_call("respond", {"body": "ok"}))

    response, startup = _run_one(llm)

    assert response.status_code == 200
    preset = (PRESETS / "shop.md").read_text(encoding="utf-8").strip()
    assert llm.prompts[0].startswith(preset)
    assert "## Role & Context" in llm.prompts[0]
    assert startup["personality_preset"] == "shop"
    assert startup["personality_path"].endswith("config/personalities/shop.md")


def test_default_preset_when_nothing_set(env):
    llm = make_queued_llm(ai_tool_call("respond", {"body": "ok"}))

    response, startup = _run_one(llm)

    assert response.status_code == 200
    preset = (PRESETS / "default.md").read_text(encoding="utf-8").strip()
    assert llm.prompts[0].startswith(preset)
    assert startup["personality_preset"] == "default"


def test_custom_path_wins(env, tmp_path):
    custom = tmp_path / "custom.md"
    custom.write_text("Custom persona.")
    env.setenv("PERSONALITY", "teapot")
    env.setenv("PERSONALITY_PATH", str(custom))
    llm = make_queued_llm(ai_tool_call("respond", {"body": "ok"}))

    response, startup = _run_one(llm)

    assert response.status_code == 200
    assert llm.prompts[0].startswith("Custom persona.")
    assert startup["personality_preset"] is None
