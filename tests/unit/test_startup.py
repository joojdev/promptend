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


def _settings(**kwargs):
    from src.config.settings import Settings

    return Settings(
        _env_file=None,
        llm_provider="anthropic",
        llm_api_key="k",
        llm_model="m",
        **kwargs,
    )


def test_hardening_setting_defaults(monkeypatch):
    for name in (
        "RATE_LIMIT_PER_MINUTE",
        "DOPAMINE_ACCESS_KEY",
        "AGENT_TIMEOUT_SECONDS",
        "SENSITIVE_HEADER_NAMES",
        "SENSITIVE_HEADER_FRAGMENTS",
    ):
        monkeypatch.delenv(name, raising=False)
    s = _settings()
    assert s.rate_limit_per_minute == 20
    assert s.dopamine_access_key == ""
    assert s.agent_timeout_seconds == 30
    names, fragments = s.sensitive_header_rule
    assert names == frozenset(
        {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
    )
    assert fragments == ("token", "secret", "key")


def test_hardening_settings_env_override(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("DOPAMINE_ACCESS_KEY", "  s3cret  ")
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "1.5")
    s = _settings()
    assert s.rate_limit_per_minute == 5
    assert s.dopamine_access_key == "s3cret"
    assert s.agent_timeout_seconds == 1.5


@pytest.mark.parametrize("field", ["rate_limit_per_minute", "agent_timeout_seconds"])
@pytest.mark.parametrize("value", [0, -1])
def test_non_positive_values_rejected(field, value):
    with pytest.raises(Exception):
        _settings(**{field: value})


def test_header_lists_lowercased_blanks_dropped():
    s = _settings(
        sensitive_header_names=" X-Foo, ,Bar,, ",
        sensitive_header_fragments="PASS, ,Word",
    )
    names, fragments = s.sensitive_header_rule
    assert names == frozenset({"x-foo", "bar"})
    assert fragments == ("pass", "word")
