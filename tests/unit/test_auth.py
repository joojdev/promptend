import pytest

from src.api.auth import ANONYMOUS_USER, Principal, authenticate, parse_bearer
from src.auth.tokens import TokenStore


@pytest.mark.parametrize("header", [None, "", "Basic x", "Bearer", "Bearer ", "Bearer a b"])
def test_parse_bearer_rejects(header):
    assert parse_bearer(header) is None


@pytest.mark.parametrize("header", ["bearer TOKEN", "Bearer TOKEN", "BEARER TOKEN"])
def test_parse_bearer_accepts(header):
    assert parse_bearer(header) == "TOKEN"


@pytest.fixture()
def store(tmp_path):
    return TokenStore(tmp_path / "tokens.db")


def test_enabled_user_token(store):
    issued = store.create_user_token("app")
    assert authenticate(f"Bearer {issued.token}", store, True) == Principal("user", issued.id)


def test_enabled_admin_token(store):
    issued = store.issue_admin_token(60)
    assert authenticate(f"Bearer {issued.token}", store, True) == Principal("admin", issued.id)


@pytest.mark.parametrize("header", [None, "Basic x", "Bearer sk_unknown"])
def test_enabled_invalid(store, header):
    assert authenticate(header, store, True) is None


@pytest.mark.parametrize("header", [None, "Basic x", "Bearer sk_unknown"])
def test_disabled_invalid_is_anonymous_user(store, header):
    assert authenticate(header, store, False) == ANONYMOUS_USER
    assert ANONYMOUS_USER == Principal("user", None)


def test_disabled_admin_token_still_admin(store):
    issued = store.issue_admin_token(60)
    assert authenticate(f"Bearer {issued.token}", store, False) == Principal("admin", issued.id)
