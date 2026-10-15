from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from tests.conftest import admin_env, ai_tool_call, enable_auth, make_queued_llm, user_token


@pytest.fixture()
def env(monkeypatch, tmp_path):
    persona = tmp_path / "persona.md"
    persona.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(persona))
    for name in (
        "STATE_FILE",
        "RATE_LIMIT_PER_MINUTE",
        "LOGIN_RATE_LIMIT_PER_MINUTE",
        "ADMIN_TOKEN_TTL_MINUTES",
    ):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / "tokens.db"


def _llm(n=5):
    return make_queued_llm(*[ai_tool_call("respond", {"body": "hi"}) for _ in range(n)])


def _app(llm):
    from src.api.app import create_app

    return create_app(llm=llm)


def _client(app):
    return TestClient(app, raise_server_exceptions=False)


def _login(c, username="admin", password="pw"):
    return c.post("/_admin/login", json={"username": username, "password": password})


# --- US2: login ---


def test_login_success(monkeypatch, env):
    admin_env(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN_TTL_MINUTES", "30")
    llm = _llm()
    with _client(_app(llm)) as c:
        r = _login(c)
    assert r.status_code == 200
    data = r.json()
    assert data["token"].startswith("adm_")
    assert data["token_type"] == "bearer"
    expires = datetime.fromisoformat(data["expires_at"])
    assert expires.tzinfo is not None
    assert abs((expires - (datetime.now(UTC) + timedelta(minutes=30))).total_seconds()) < 5
    assert llm.calls == 0


def test_login_failures_identical(monkeypatch, env):
    admin_env(monkeypatch)
    llm = _llm()
    with _client(_app(llm)) as c:
        wrong_pw = _login(c, password="nope")
        wrong_user = _login(c, username="root")
    assert wrong_pw.status_code == wrong_user.status_code == 401
    assert wrong_pw.json() == wrong_user.json() == {"error": "unauthorized"}
    assert llm.calls == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"username": "admin"}},
        {"json": {"password": "pw"}},
        {"json": {"username": "", "password": "pw"}},
        {"json": {"username": "admin", "password": ""}},
        {"content": "not json", "headers": {"content-type": "application/json"}},
    ],
)
def test_login_validation_422(monkeypatch, env, kwargs):
    admin_env(monkeypatch)
    llm = _llm()
    with _client(_app(llm)) as c:
        r = c.post("/_admin/login", **kwargs)
    assert r.status_code == 422
    assert llm.calls == 0


def test_login_rate_limited(monkeypatch, env):
    admin_env(monkeypatch)
    monkeypatch.setenv("LOGIN_RATE_LIMIT_PER_MINUTE", "2")
    with _client(_app(_llm())) as c:
        assert _login(c, password="x").status_code == 401
        assert _login(c, password="x").status_code == 401
        r = _login(c)
    assert r.status_code == 429
    assert r.json() == {"error": "rate_limited"}


def test_admin_routes_404_when_disabled(env):
    llm = _llm()
    app = _app(llm)
    with capture_logs() as logs:
        with _client(app) as c:
            responses = [
                _login(c),
                c.get("/_admin/tokens"),
                c.get("/_admin/anything"),
                c.post("/_admin/tokens", json={"name": "x"}),
            ]
    for r in responses:
        assert r.status_code == 404
        assert r.json() == {"error": "not_found"}
    assert any(e["event"] == "admin_routes_disabled" for e in logs)
    assert llm.calls == 0


def test_admin_prefix_is_exact(env):
    llm = _llm()
    with _client(_app(llm)) as c:
        assert c.get("/_adminx").status_code == 200
    assert llm.calls == 1


def test_unknown_admin_subpath_never_reaches_agent(monkeypatch, env):
    admin_env(monkeypatch)
    llm = _llm()
    with _client(_app(llm)) as c:
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            r = c.request(method, "/_admin/whatever/deep")
            assert r.status_code == 404
            assert r.json() == {"error": "not_found"}
    assert llm.calls == 0


def test_user_tokens_work_without_admin(monkeypatch, env):
    enable_auth(monkeypatch)
    token = user_token(env)
    with _client(_app(_llm())) as c:
        r = c.get("/a", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


# --- US3: token management ---


def _admin_headers(c):
    return {"Authorization": f"Bearer {_login(c).json()['token']}"}


def test_token_lifecycle(monkeypatch, env):
    admin_env(monkeypatch)
    enable_auth(monkeypatch)
    llm = _llm()
    with _client(_app(llm)) as c:
        adm = _admin_headers(c)
        r = c.post("/_admin/tokens", json={"name": "app"}, headers=adm)
        assert r.status_code == 201
        created = r.json()
        assert set(created) == {"id", "name", "prefix", "token", "created_at"}
        assert created["token"].startswith("sk_")
        assert created["prefix"] == created["token"][:8]
        assert created["name"] == "app"

        listed = c.get("/_admin/tokens", headers=adm)
        assert listed.status_code == 200
        [row] = listed.json()
        assert row["id"] == created["id"] and row["revoked"] is False
        assert "token" not in row and "token_hash" not in row

        sk = {"Authorization": f"Bearer {created['token']}"}
        assert c.get("/a", headers=sk).status_code == 200
        assert c.delete(f"/_admin/tokens/{created['id']}", headers=adm).status_code == 204
        assert c.delete(f"/_admin/tokens/{created['id']}", headers=adm).status_code == 204
        assert c.get("/a", headers=sk).status_code == 401
        assert c.get("/_admin/tokens", headers=adm).json()[0]["revoked"] is True
    assert llm.calls == 1


@pytest.mark.parametrize("body", [{"name": ""}, {}, {"name": 3}])
def test_create_token_validation(monkeypatch, env, body):
    admin_env(monkeypatch)
    with _client(_app(_llm())) as c:
        adm = _admin_headers(c)
        assert c.post("/_admin/tokens", json=body, headers=adm).status_code == 422
        assert c.get("/_admin/tokens", headers=adm).json() == []


def test_revoke_unknown_or_admin_id_404(monkeypatch, env):
    from src.auth.tokens import TokenStore

    admin_env(monkeypatch)
    with _client(_app(_llm())) as c:
        adm = _admin_headers(c)
        r = c.delete("/_admin/tokens/999", headers=adm)
        assert r.status_code == 404 and r.json() == {"error": "not_found"}
        admin_id = TokenStore(env).issue_admin_token(60).id
        assert c.delete(f"/_admin/tokens/{admin_id}", headers=adm).status_code == 404


def test_admin_tokens_not_listed(monkeypatch, env):
    admin_env(monkeypatch)
    with _client(_app(_llm())) as c:
        adm = _admin_headers(c)
        assert c.get("/_admin/tokens", headers=adm).json() == []


def test_token_routes_require_admin_token(monkeypatch, env):
    from src.auth import tokens

    admin_env(monkeypatch)
    sk = user_token(env)
    llm = _llm()
    with _client(_app(llm)) as c:
        adm = _admin_headers(c)
        bad = [{}, {"Authorization": f"Bearer {sk}"}, {"Authorization": "Bearer adm_nope"}]
        for headers in bad:
            for method, path, kw in (
                ("GET", "/_admin/tokens", {}),
                ("POST", "/_admin/tokens", {"json": {"name": "x"}}),
                ("DELETE", "/_admin/tokens/1", {}),
            ):
                r = c.request(method, path, headers=headers, **kw)
                assert r.status_code == 401, (headers, method)
                assert r.json() == {"error": "unauthorized"}
        later = datetime.now(UTC) + timedelta(minutes=61)
        monkeypatch.setattr(tokens, "_now", lambda: later)
        assert c.get("/_admin/tokens", headers=adm).status_code == 401
    assert llm.calls == 0


def test_unsupported_method_on_tokens(monkeypatch, env):
    admin_env(monkeypatch)
    llm = _llm()
    with _client(_app(llm)) as c:
        r = c.put("/_admin/tokens", headers=_admin_headers(c))
    assert r.status_code in (404, 405)
    assert llm.calls == 0
