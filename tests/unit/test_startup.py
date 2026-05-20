import pytest


# T010
def test_missing_required_env_var_raises_system_exit(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    from src.config.settings import load_settings

    with pytest.raises(SystemExit):
        load_settings()


# T011
def test_missing_personality_file_raises_system_exit(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")

    from src.agent.harness import load_harness

    with pytest.raises(SystemExit):
        load_harness(str(tmp_path / "nonexistent.md"))
