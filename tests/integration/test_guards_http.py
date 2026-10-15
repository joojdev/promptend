import pytest
from fastapi.testclient import TestClient

from src.api import guards
from tests.conftest import CountingFakeLLM


@pytest.fixture()
def make_client(monkeypatch, tmp_path):
    personality = tmp_path / "personality.md"
    personality.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality))

    def _make(limit=None, client=("testclient", 50000)):
        if limit is not None:
            monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", str(limit))
        llm = CountingFakeLLM(responses=["pong"], prompts=[])
        from src.api.app import create_app

        return TestClient(create_app(llm=llm), client=client), llm

    return _make


def test_rate_limit_429_and_no_llm_call(make_client):
    c, llm = make_client(limit=2)
    with c:
        assert c.get("/a").status_code == 200
        assert c.get("/a").status_code == 200
        r = c.get("/a")
    assert r.status_code == 429
    assert r.json() == {"error": "rate_limited"}
    assert llm.calls == 2


def test_clients_independent(make_client):
    c1, _ = make_client(limit=1, client=("1.2.3.4", 50000))
    with c1:
        assert c1.get("/a").status_code == 200
        assert c1.get("/a").status_code == 429
    c2, _ = make_client(limit=1, client=("5.6.7.8", 50000))
    with c2:
        assert c2.get("/a").status_code == 200


def test_clients_share_limiter_per_app_independent_hosts(monkeypatch, make_client):
    # same app, two hosts: build app once, swap client address per request is not supported,
    # so verify via limiter directly at the app level using different TestClients on one app
    c1, _ = make_client(limit=1, client=("1.2.3.4", 1))
    with c1:
        app = c1.app
        c2 = TestClient(app, client=("5.6.7.8", 1))
        assert c1.get("/a").status_code == 200
        assert c2.get("/a").status_code == 200
        assert c1.get("/a").status_code == 429


def test_window_elapsed_allows_again(monkeypatch, make_client):
    now = [1000.0]
    monkeypatch.setattr(guards.time, "monotonic", lambda: now[0])
    c, _ = make_client(limit=1)
    with c:
        assert c.get("/a").status_code == 200
        assert c.get("/a").status_code == 429
        now[0] += 61
        assert c.get("/a").status_code == 200


def test_health_exempt(make_client):
    c, _ = make_client(limit=1)
    with c:
        assert c.get("/a").status_code == 200
        assert c.get("/a").status_code == 429
        assert c.get("/health").status_code == 200


def test_oversized_body_413_no_llm(monkeypatch, make_client):
    monkeypatch.setenv("MAX_REQUEST_BODY_SIZE", "10")
    c, llm = make_client()
    with c:
        r = c.post("/a", content="x" * 100)
    assert r.status_code == 413
    assert llm.calls == 0
