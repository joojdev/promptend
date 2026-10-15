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
        "AGENT_TIMEOUT_SECONDS",
        "SENSITIVE_HEADER_NAMES",
        "SENSITIVE_HEADER_FRAGMENTS",
    ):
        monkeypatch.delenv(name, raising=False)
    s = _settings()
    assert s.rate_limit_per_minute == 20
    assert s.agent_timeout_seconds == 30
    names, fragments = s.sensitive_header_rule
    assert names == frozenset(
        {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
    )
    assert fragments == ("token", "secret", "key")


def test_hardening_settings_env_override(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "1.5")
    s = _settings()
    assert s.rate_limit_per_minute == 5
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


_COSMETIC_ENV = (
    "PERSONALITY",
    "PERSONALITY_PATH",
    "STATE_FILE",
    "KV_MAX_VALUE_BYTES",
    "KV_MAX_KEYS",
    "LLM_PRICE_INPUT_PER_MTOK",
    "LLM_PRICE_OUTPUT_PER_MTOK",
)


def test_cosmetic_setting_defaults(monkeypatch):
    for name in _COSMETIC_ENV:
        monkeypatch.delenv(name, raising=False)
    s = _settings()
    assert s.personality == "default"
    assert s.personality_path == ""
    assert s.state_file == ""
    assert s.kv_max_value_bytes == 65536
    assert s.kv_max_keys == 1000
    assert s.llm_price_input_per_mtok is None
    assert s.llm_price_output_per_mtok is None


def test_cosmetic_settings_env_override(monkeypatch):
    monkeypatch.setenv("PERSONALITY", "shop")
    monkeypatch.setenv("PERSONALITY_PATH", "custom.md")
    monkeypatch.setenv("STATE_FILE", "state.json")
    monkeypatch.setenv("KV_MAX_VALUE_BYTES", "10")
    monkeypatch.setenv("KV_MAX_KEYS", "2")
    monkeypatch.setenv("LLM_PRICE_INPUT_PER_MTOK", "3")
    monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_MTOK", "15.5")
    s = _settings()
    assert s.personality == "shop"
    assert s.personality_path == "custom.md"
    assert s.state_file == "state.json"
    assert s.kv_max_value_bytes == 10
    assert s.kv_max_keys == 2
    assert s.llm_price_input_per_mtok == 3.0
    assert s.llm_price_output_per_mtok == 15.5


@pytest.mark.parametrize("field", ["kv_max_value_bytes", "kv_max_keys"])
@pytest.mark.parametrize("value", [0, -1])
def test_non_positive_kv_limits_rejected(monkeypatch, field, value):
    for name in _COSMETIC_ENV:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(Exception):
        _settings(**{field: value})


@pytest.mark.parametrize(
    "prices",
    [
        {"llm_price_input_per_mtok": 3.0},
        {"llm_price_output_per_mtok": 15.0},
    ],
)
def test_only_one_price_rejected(monkeypatch, prices):
    for name in _COSMETIC_ENV:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(Exception, match="LLM_PRICE_"):
        _settings(**prices)


@pytest.mark.parametrize(
    "prices",
    [
        {"llm_price_input_per_mtok": -1.0, "llm_price_output_per_mtok": 15.0},
        {"llm_price_input_per_mtok": 3.0, "llm_price_output_per_mtok": -0.01},
    ],
)
def test_negative_price_rejected(monkeypatch, prices):
    for name in _COSMETIC_ENV:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(Exception, match="LLM_PRICE_"):
        _settings(**prices)


def test_zero_prices_accepted(monkeypatch):
    for name in _COSMETIC_ENV:
        monkeypatch.delenv(name, raising=False)
    s = _settings(llm_price_input_per_mtok=0, llm_price_output_per_mtok=0)
    assert s.llm_price_input_per_mtok == 0
    assert s.llm_price_output_per_mtok == 0


_AUTH_ENV = (
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD_HASH",
    "ADMIN_TOKEN_TTL_MINUTES",
    "LOGIN_RATE_LIMIT_PER_MINUTE",
    "TOKENS_DB_PATH",
    "AUTH_ENABLED",
)


def test_auth_setting_defaults(monkeypatch):
    for name in _AUTH_ENV:
        monkeypatch.delenv(name, raising=False)
    s = _settings()
    assert s.admin_username == ""
    assert s.admin_password_hash == ""
    assert s.admin_token_ttl_minutes == 60
    assert s.login_rate_limit_per_minute == 5
    assert s.tokens_db_path == "data/tokens.db"
    assert s.auth_enabled is True
    assert s.admin_enabled is False


def test_auth_settings_env_override(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "  root  ")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", " $argon2id$x ")
    monkeypatch.setenv("ADMIN_TOKEN_TTL_MINUTES", "15")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("TOKENS_DB_PATH", "/tmp/t.db")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    s = _settings()
    assert s.admin_username == "root"
    assert s.admin_password_hash == "$argon2id$x"
    assert s.admin_token_ttl_minutes == 15
    assert s.login_rate_limit_per_minute == 3
    assert s.tokens_db_path == "/tmp/t.db"
    assert s.auth_enabled is False
    assert s.admin_enabled is True


@pytest.mark.parametrize("field", ["admin_token_ttl_minutes", "login_rate_limit_per_minute"])
@pytest.mark.parametrize("value", [0, -1])
def test_non_positive_auth_ints_rejected(monkeypatch, field, value):
    for name in _AUTH_ENV:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(Exception):
        _settings(**{field: value})


@pytest.mark.parametrize(
    "fields",
    [
        {"admin_username": "admin"},
        {"admin_password_hash": "$argon2id$x"},
        {"admin_username": "  ", "admin_password_hash": "$argon2id$x"},
        {"admin_username": "admin", "admin_password_hash": "   "},
    ],
)
def test_admin_enabled_needs_both_fields(monkeypatch, fields):
    for name in _AUTH_ENV:
        monkeypatch.delenv(name, raising=False)
    assert _settings(**fields).admin_enabled is False


def test_invalid_admin_hash_exits_without_echo(monkeypatch, capsys, tmp_path):
    from tests.conftest import make_queued_llm

    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    from src.api.app import create_app  # import first: the module builds an app on import

    persona = tmp_path / "persona.md"
    persona.write_text("x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("PERSONALITY_PATH", str(persona))
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "not-a-hash")

    with pytest.raises(SystemExit) as exc:
        create_app(llm=make_queued_llm())
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "ADMIN_PASSWORD_HASH is not a valid argon2 hash" in err
    assert "not-a-hash" not in err


def test_no_plain_password_setting():
    from src.config.settings import Settings

    names = [n for n in Settings.model_fields if "password" in n]
    assert names == ["admin_password_hash"]
