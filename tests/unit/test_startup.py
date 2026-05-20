import pytest


# T010
def test_missing_required_env_var_raises_system_exit(monkeypatch, tmp_path):
    from src.config.settings import Settings

    env_file = tmp_path / ".env"
    env_file.write_text("")  # empty — no LLM_MODEL

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    with pytest.raises(Exception):
        Settings(_env_file=str(env_file))


# T011
def test_missing_personality_file_raises_system_exit(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")

    from src.agent.harness import load_harness

    with pytest.raises(SystemExit):
        load_harness(str(tmp_path / "nonexistent.md"))
