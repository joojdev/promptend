from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.auth import tokens
from src.auth.tokens import TokenStore
from tests.conftest import ai_tool_call, enable_auth, make_queued_llm, user_token


@pytest.fixture()
def env(monkeypatch, tmp_path):
    persona = tmp_path / "persona.md"
    persona.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(persona))
    for name in ("STATE_FILE", "RATE_LIMIT_PER_MINUTE"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / "tokens.db"


def _llm(n=5):
    return make_queued_llm(*[ai_tool_call("respond", {"body": "hi"}) for _ in range(n)])


def _client(llm):
    from src.api.app import create_app

    return TestClient(create_app(llm=llm), raise_server_exceptions=False)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_rejected_requests_401_without_llm(monkeypatch, env):
    enable_auth(monkeypatch)
    store = TokenStore(env)
    revoked = store.create_user_token("old")
    store.revoke_user_token(revoked.id)
    llm = _llm()
    cases = [{}, {"Authorization": "Basic x"}, {"Authorization": "Bearer "}, _bearer("sk_nope")]
    cases.append(_bearer(revoked.token))
    with _client(llm) as c:
        for headers in cases:
            r = c.get("/a", headers=headers)
            assert r.status_code == 401, headers
            assert r.json() == {"error": "unauthorized"}
    assert llm.calls == 0


def test_valid_user_token_reaches_agent(monkeypatch, env):
    enable_auth(monkeypatch)
    token = user_token(env)
    llm = _llm()
    with _client(llm) as c:
        r = c.get("/a", headers=_bearer(token))
    assert r.status_code == 200
    assert r.text == "hi"
    [record] = TokenStore(env).list_user_tokens()
    assert record.last_used_at is not None


def test_admin_token_and_expiry(monkeypatch, env):
    enable_auth(monkeypatch)
    admin = TokenStore(env).issue_admin_token(60)
    llm = _llm()
    with _client(llm) as c:
        assert c.get("/a", headers=_bearer(admin.token)).status_code == 200
        later = datetime.now(UTC) + timedelta(minutes=61)
        monkeypatch.setattr(tokens, "_now", lambda: later)
        assert c.get("/a", headers=_bearer(admin.token)).status_code == 401
    assert llm.calls == 1


def test_health_is_public(monkeypatch, env):
    enable_auth(monkeypatch)
    with _client(_llm()) as c:
        assert c.get("/health").status_code == 200


def test_unauthenticated_requests_do_not_consume_rate_limit(monkeypatch, env):
    enable_auth(monkeypatch)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    token = user_token(env)
    with _client(_llm()) as c:
        assert c.get("/a").status_code == 401
        assert c.get("/a").status_code == 401
        assert c.get("/a", headers=_bearer(token)).status_code == 200


def test_credentials_never_reach_agent(monkeypatch, env):
    enable_auth(monkeypatch)
    token = user_token(env)
    llm = _llm()
    with _client(llm) as c:
        r = c.get("/a", headers={**_bearer(token), "X-API-Key": "zzz"})
    assert r.status_code == 200
    prompt = llm.prompts[0].lower()
    for needle in ("authorization", "x-api-key", token.lower(), "zzz"):
        assert needle not in prompt
