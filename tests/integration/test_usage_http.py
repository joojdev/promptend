import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from structlog.testing import capture_logs

from tests.conftest import RaisingFakeLLM, SlowFakeLLM, ai_tool_call, make_queued_llm

USAGE = ("x-dopamine-tokens-in", "x-dopamine-tokens-out", "x-dopamine-steps")
ALL_USAGE = (*USAGE, "x-dopamine-cost-usd")


@pytest.fixture()
def make_app(monkeypatch, tmp_path):
    persona = tmp_path / "persona.md"
    persona.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(persona))
    for name in (
        "STATE_FILE",
        "DOPAMINE_ACCESS_KEY",
        "RATE_LIMIT_PER_MINUTE",
        "LLM_PRICE_INPUT_PER_MTOK",
        "LLM_PRICE_OUTPUT_PER_MTOK",
    ):
        monkeypatch.delenv(name, raising=False)

    def _make(llm, **env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        from src.api.app import create_app

        return create_app(llm=llm)

    return _make


def _client(app):
    return TestClient(app, raise_server_exceptions=False)


def _two_steps():
    return make_queued_llm(
        ai_tool_call("list_files", {}, tokens_in=100, tokens_out=20),
        ai_tool_call("respond", {"body": "hi"}, tokens_in=150, tokens_out=30),
    )


def _usage(response):
    return tuple(response.headers.get(h) for h in USAGE)


def test_success_headers_and_log(make_app):
    app = make_app(_two_steps())
    with capture_logs() as logs:
        with _client(app) as c:
            r = c.get("/hello")
    assert r.status_code == 200
    assert _usage(r) == ("250", "50", "2")
    assert "x-dopamine-cost-usd" not in r.headers
    requests = [e for e in logs if e["event"] == "request"]
    assert len(requests) == 1
    entry = requests[0]
    assert (entry["tokens_in"], entry["tokens_out"], entry["steps"]) == (250, 50, 2)
    assert entry["status"] == 200 and entry["path"] == "/hello" and entry["method"] == "GET"
    assert "cost_usd" not in entry


def test_agent_set_usage_headers_overridden(make_app):
    llm = make_queued_llm(
        ai_tool_call(
            "respond",
            {"body": "hi", "headers": {"X-Dopamine-Steps": "999", "x-dopamine-tokens-in": "1"}},
            tokens_in=7,
            tokens_out=3,
        )
    )
    with _client(make_app(llm)) as c:
        r = c.get("/hello")
    assert _usage(r) == ("7", "3", "1")
    assert len(r.headers.get_list("x-dopamine-steps")) == 1
    assert len(r.headers.get_list("x-dopamine-tokens-in")) == 1


def test_respond_with_file_carries_headers(make_app):
    llm = make_queued_llm(ai_tool_call("respond_with_file", {"path": "favicon.ico"}, tokens_in=5))
    with _client(make_app(llm)) as c:
        r = c.get("/favicon.ico")
    assert r.status_code == 200
    assert _usage(r) == ("5", "0", "1")


def test_loose_text_reply_carries_headers(make_app):
    msg = AIMessage(
        content="pong",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    with _client(make_app(make_queued_llm(msg))) as c:
        r = c.get("/ping")
    assert r.headers["x-dopamine-warning"] == "agent did not use a response tool"
    assert _usage(r) == ("10", "5", "0")


def test_provider_error_503_has_headers(make_app):
    exc = type("APIConnectionError", (Exception,), {"__module__": "anthropic"})("down")
    with _client(make_app(RaisingFakeLLM(responses=[], exc=exc))) as c:
        r = c.get("/a")
    assert r.status_code == 503
    assert _usage(r) == ("0", "0", "0")


def test_unexpected_error_500_has_headers(make_app):
    with _client(make_app(RaisingFakeLLM(responses=[], exc=ValueError("boom")))) as c:
        r = c.get("/a")
    assert r.status_code == 500
    assert r.json()["error"] == "internal_error"
    assert _usage(r) == ("0", "0", "0")


def test_no_response_502_has_headers(make_app):
    msg = AIMessage(
        content="",
        usage_metadata={"input_tokens": 4, "output_tokens": 0, "total_tokens": 4},
    )
    with _client(make_app(make_queued_llm(msg))) as c:
        r = c.get("/a")
    assert r.status_code == 502
    assert _usage(r) == ("4", "0", "0")


def test_timeout_504_has_headers_and_log(make_app):
    app = make_app(SlowFakeLLM(responses=["x"], delay=5), AGENT_TIMEOUT_SECONDS="0.05")
    with capture_logs() as logs:
        with _client(app) as c:
            r = c.get("/slow")
    assert r.status_code == 504
    assert _usage(r) == ("0", "0", "0")
    requests = [e for e in logs if e["event"] == "request"]
    assert len(requests) == 1 and requests[0]["status"] == 504


def test_guard_rejections_and_health_have_no_usage_headers(make_app):
    with _client(make_app(_two_steps(), DOPAMINE_ACCESS_KEY="s3cret")) as c:
        r = c.get("/a")
        health = c.get("/health")
    assert r.status_code == 401
    assert health.status_code == 200
    for response in (r, health):
        assert not any(h in response.headers for h in ALL_USAGE)


def test_rate_limited_has_no_usage_headers(make_app):
    llm = make_queued_llm(ai_tool_call("respond", {"body": "hi"}))
    with _client(make_app(llm, RATE_LIMIT_PER_MINUTE="1")) as c:
        assert c.get("/a").status_code == 200
        r = c.get("/a")
    assert r.status_code == 429
    assert not any(h in r.headers for h in ALL_USAGE)


def test_usage_headers_exposed_to_cors(make_app):
    with _client(make_app(_two_steps())) as c:
        r = c.get("/hello", headers={"Origin": "http://example.com"})
    exposed = {h.strip().lower() for h in r.headers["access-control-expose-headers"].split(",")}
    assert set(ALL_USAGE) <= exposed


PRICES = {"LLM_PRICE_INPUT_PER_MTOK": "3", "LLM_PRICE_OUTPUT_PER_MTOK": "15"}


def test_cost_header_and_log_with_prices(make_app):
    app = make_app(_two_steps(), **PRICES)
    with capture_logs() as logs:
        with _client(app) as c:
            r = c.get("/hello")
    assert r.headers["x-dopamine-cost-usd"] == "0.001500"
    entry = next(e for e in logs if e["event"] == "request")
    assert entry["cost_usd"] == "0.001500"


def _agent_sets_cost():
    return make_queued_llm(
        ai_tool_call(
            "respond",
            {"body": "hi", "headers": {"X-Dopamine-Cost-USD": "42"}},
            tokens_in=250,
            tokens_out=50,
        )
    )


def test_agent_set_cost_replaced(make_app):
    with _client(make_app(_agent_sets_cost(), **PRICES)) as c:
        r = c.get("/hello")
    assert r.headers.get_list("x-dopamine-cost-usd") == ["0.001500"]


def test_agent_set_cost_removed_without_prices(make_app):
    with _client(make_app(_agent_sets_cost())) as c:
        r = c.get("/hello")
    assert "x-dopamine-cost-usd" not in r.headers
