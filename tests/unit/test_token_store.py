from datetime import UTC, datetime, timedelta

import pytest

from src.auth import tokens
from src.auth.tokens import IssuedToken, TokenStore


@pytest.fixture()
def store(tmp_path):
    return TokenStore(tmp_path / "sub" / "tokens.db")


def test_schema_and_parent_dir_created_on_first_use(tmp_path, store):
    assert not (tmp_path / "sub").exists()
    store.create_user_token("app")
    assert (tmp_path / "sub" / "tokens.db").is_file()


def test_constructor_does_no_io(tmp_path):
    TokenStore(tmp_path / "lazy" / "tokens.db")
    assert not (tmp_path / "lazy").exists()


def test_create_user_token(store):
    issued = store.create_user_token("app")
    assert isinstance(issued, IssuedToken)
    assert issued.token.startswith("sk_")
    assert issued.prefix == issued.token[:8]
    assert isinstance(issued.id, int)
    assert issued.name == "app"
    assert issued.expires_at is None


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_rejected(store, name):
    with pytest.raises(ValueError):
        store.create_user_token(name)


def test_authenticate_user_token_sets_last_used(store):
    issued = store.create_user_token("app")
    record = store.authenticate(issued.token)
    assert record is not None
    assert record.role == "user"
    assert record.id == issued.id
    assert record.last_used_at is not None
    [listed] = store.list_user_tokens()
    assert listed.last_used_at is not None


def test_unknown_token(store):
    store.create_user_token("app")
    assert store.authenticate("sk_nope") is None


def test_revoke(store):
    issued = store.create_user_token("app")
    assert store.revoke_user_token(issued.id) is True
    assert store.authenticate(issued.token) is None
    assert store.revoke_user_token(issued.id) is True
    assert store.authenticate(issued.token) is None
    assert store.revoke_user_token(999) is False


def test_admin_token(store):
    issued = store.issue_admin_token(ttl_minutes=60)
    assert issued.token.startswith("adm_")
    expires = datetime.fromisoformat(issued.expires_at)
    expected = datetime.now(UTC) + timedelta(minutes=60)
    assert abs((expires - expected).total_seconds()) < 5
    record = store.authenticate(issued.token)
    assert record is not None and record.role == "admin"


def test_expired_admin_token_rejected(monkeypatch, store):
    issued = store.issue_admin_token(ttl_minutes=60)
    later = datetime.now(UTC) + timedelta(minutes=61)
    monkeypatch.setattr(tokens, "_now", lambda: later)
    assert store.authenticate(issued.token) is None


def _admin_rows(path):
    import sqlite3

    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM tokens WHERE role = 'admin'").fetchone()[0]


def test_issuing_admin_token_purges_expired(monkeypatch, tmp_path, store):
    store.issue_admin_token(ttl_minutes=1)
    store.issue_admin_token(ttl_minutes=1)
    assert _admin_rows(store.path) == 2
    later = datetime.now(UTC) + timedelta(minutes=5)
    monkeypatch.setattr(tokens, "_now", lambda: later)
    store.issue_admin_token(ttl_minutes=1)
    assert _admin_rows(store.path) == 1


def test_cannot_revoke_admin_token(store):
    issued = store.issue_admin_token(ttl_minutes=60)
    assert store.revoke_user_token(issued.id) is False
    assert store.authenticate(issued.token) is not None


def test_list_user_tokens(store):
    a = store.create_user_token("a")
    store.issue_admin_token(ttl_minutes=60)
    b = store.create_user_token("b")
    store.revoke_user_token(a.id)
    records = store.list_user_tokens()
    assert [r.id for r in records] == [a.id, b.id]
    assert [r.revoked for r in records] == [True, False]
    assert all(r.role == "user" for r in records)
    for r in records:
        assert not hasattr(r, "token")
        assert not hasattr(r, "token_hash")
    assert [r.id for r in store.list_user_tokens(include_revoked=False)] == [b.id]


def test_to_public_dict(store):
    issued = store.create_user_token("a")
    [record] = store.list_user_tokens()
    assert record.to_public_dict() == {
        "id": issued.id,
        "name": "a",
        "prefix": issued.prefix,
        "created_at": issued.created_at,
        "last_used_at": None,
        "revoked": False,
    }


def test_two_instances_share_file(tmp_path):
    path = tmp_path / "tokens.db"
    one, two = TokenStore(path), TokenStore(path)
    issued = one.create_user_token("a")
    assert two.authenticate(issued.token) is not None
    two.revoke_user_token(issued.id)
    assert one.authenticate(issued.token) is None


def test_raw_storage_holds_no_full_token(store):
    issued = [store.create_user_token(f"t{i}") for i in range(3)]
    issued.append(store.issue_admin_token(ttl_minutes=60))
    raw = b"".join(
        p.read_bytes() for p in store.path.parent.iterdir() if p.name.startswith("tokens.db")
    )
    for item in issued:
        assert item.token.encode() not in raw
        assert item.prefix.encode() in raw


def test_table_columns(store):
    import sqlite3

    store.create_user_token("a")
    with sqlite3.connect(store.path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(tokens)")]
    assert columns == [
        "id",
        "role",
        "name",
        "token_hash",
        "prefix",
        "created_at",
        "last_used_at",
        "expires_at",
        "revoked",
    ]
