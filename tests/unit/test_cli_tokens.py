import pytest

from src.auth.passwords import AdminVerifier
from src.auth.tokens import TokenStore
from src.cli import tokens as cli
from src.cli.tokens import main


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "cli" / "tokens.db")


def run(db, *args):
    return main(["--db", db, *args])


def test_create_prints_token_once(db, capsys):
    assert run(db, "create", "app") == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == 'Created token #1 "app"'
    assert lines[1].startswith("sk_")
    assert "will not be shown again" in out
    assert TokenStore(db).authenticate(lines[1]) is not None


def test_list_and_revoke(db, capsys):
    run(db, "create", "app")
    capsys.readouterr()
    assert run(db, "list") == 0
    out = capsys.readouterr().out
    header = out.splitlines()[0].split()
    assert header == ["ID", "NAME", "PREFIX", "CREATED", "AT", "LAST", "USED", "STATUS"]
    assert "app" in out and "active" in out and "never" in out

    assert run(db, "revoke", "1") == 0
    assert capsys.readouterr().out.strip() == "Revoked token #1."
    run(db, "list")
    assert capsys.readouterr().out.strip() == "No tokens."
    run(db, "list", "--all")
    out = capsys.readouterr().out
    assert "app" in out and "revoked" in out


def test_revoke_unknown(db, capsys):
    assert run(db, "revoke", "999") == 1
    captured = capsys.readouterr()
    assert "Token #999 not found." in captured.err
    assert captured.out == ""


def test_empty_list(db, capsys):
    assert run(db, "list") == 0
    assert capsys.readouterr().out.strip() == "No tokens."


def test_blank_name(db, capsys):
    assert run(db, "create", "  ") == 1
    assert capsys.readouterr().out == ""


def test_hash_password(monkeypatch, capsys):
    answers = iter(["pw", "pw"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    assert main(["hash-password"]) == 0
    h = capsys.readouterr().out.strip()
    assert h.startswith("$argon2id$")
    assert AdminVerifier("a", h).verify("a", "pw")


@pytest.mark.parametrize("answers", [["pw", "other"], ["", ""]])
def test_hash_password_rejected(monkeypatch, capsys, answers):
    it = iter(answers)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(it))
    assert main(["hash-password"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err


def test_db_from_env_without_llm_settings(monkeypatch, tmp_path, capsys):
    path = tmp_path / "env.db"
    monkeypatch.setenv("TOKENS_DB_PATH", str(path))
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert main(["create", "envtok"]) == 0
    token = capsys.readouterr().out.splitlines()[1]
    assert TokenStore(path).authenticate(token) is not None
