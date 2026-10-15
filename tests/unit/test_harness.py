import sys

import pytest


# T012
def test_system_prompt_contains_both_sections(tmp_path, monkeypatch):
    personality_content = "I am a sarcastic butler."
    personality_file = tmp_path / "personality.md"
    personality_file.write_text(personality_content)

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality_file))

    from src.agent.harness import build_system_prompt

    prompt = build_system_prompt(str(personality_file))

    assert personality_content in prompt
    assert "respond" in prompt.lower()


# T013
def test_empty_personality_yields_only_programmatic_block(tmp_path, monkeypatch):
    personality_file = tmp_path / "personality.md"
    personality_file.write_text("")

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality_file))

    from src.agent.harness import build_system_prompt

    prompt = build_system_prompt(str(personality_file))

    assert prompt.strip() != ""
    assert "respond" in prompt.lower()
    assert len(prompt.strip().splitlines()) > 0


def test_anthropic_provider_builds_chat_anthropic(monkeypatch):
    from langchain_anthropic import ChatAnthropic

    from src.agent.harness import _build_llm_from_settings
    from src.config.settings import Settings

    settings = Settings(
        _env_file=None,
        llm_provider="anthropic",
        llm_api_key="test-key",
        llm_model="claude-sonnet-5-5",
    )

    llm = _build_llm_from_settings(settings)

    assert isinstance(llm, ChatAnthropic)
    assert llm.model == "claude-sonnet-5-5"


def test_anthropic_provider_requires_api_key():
    from pydantic import ValidationError

    from src.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="anthropic", llm_api_key="", llm_model="m")


@pytest.mark.parametrize(
    ("provider", "module", "package", "hint"),
    [
        ("openai", "langchain_openai", "langchain-openai", "uv sync --extra openai"),
        ("bedrock", "langchain_aws", "langchain-aws", "uv sync --extra bedrock"),
        ("anthropic", "langchain_anthropic", "langchain-anthropic", "uv sync"),
    ],
)
def test_missing_provider_package_exits_with_install_hint(
    monkeypatch, capsys, provider, module, package, hint
):
    from src.agent.harness import _build_llm_from_settings
    from src.config.settings import Settings

    monkeypatch.setitem(sys.modules, module, None)  # makes `import module` raise ImportError
    settings = Settings(
        _env_file=None, llm_provider=provider, llm_api_key="test-key", llm_model="m"
    )

    with pytest.raises(SystemExit) as exc:
        _build_llm_from_settings(settings)

    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert package in err
    assert hint in err
    assert "Traceback" not in err


def test_create_app_exits_early_when_provider_package_missing(monkeypatch, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setitem(sys.modules, "langchain_openai", None)

    from src.api.app import create_app

    with pytest.raises(SystemExit):
        create_app()

    assert "uv sync --extra openai" in capsys.readouterr().err
