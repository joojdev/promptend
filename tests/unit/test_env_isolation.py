"""The suite must not depend on a developer's local .env."""


def test_settings_ignore_local_env_file(tmp_path, monkeypatch):
    from src.config.settings import Settings

    (tmp_path / ".env").write_text("PERSONALITY=teapot\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PERSONALITY", raising=False)

    settings = Settings(llm_api_key="k", llm_model="m")

    assert settings.personality == "default"


def test_token_settings_ignore_local_env_file(tmp_path, monkeypatch):
    from src.cli.tokens import TokenSettings

    (tmp_path / ".env").write_text("TOKENS_DB_PATH=from-dotenv.db\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TOKENS_DB_PATH", raising=False)

    assert TokenSettings().tokens_db_path != "from-dotenv.db"
