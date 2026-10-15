import json
import time

import pytest
from langchain_core.messages import AIMessage, ToolCall

from src.api.errors import (
    AgentLoopLimitError,
    AgentNoResponseError,
    AgentTimeoutError,
    LLMUnavailableError,
)
from tests.conftest import RaisingFakeLLM, SlowFakeLLM, ToolCapableFakeLLM

INCOMING = {
    "method": "POST",
    "path": "/x",
    "query_params": {},
    "headers": {},
    "body": "my own request text",
}


@pytest.fixture()
def build(monkeypatch, tmp_path):
    personality = tmp_path / "personality.md"
    personality.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality))

    def _build(llm):
        from src.agent.harness import load_harness

        return load_harness(str(personality), llm=llm)

    return _build


def _provider_exc(name, module="anthropic"):
    return type(name, (Exception,), {"__module__": module})("boom secret text")


def _client_error(code):
    cls = type("ClientError", (Exception,), {"__module__": "botocore.exceptions"})
    exc = cls("boom")
    exc.response = {"Error": {"Code": code}}
    return exc


async def test_empty_ai_message_is_no_response(build):
    from src.agent.harness import invoke_agent

    agent = build(ToolCapableFakeLLM(responses=[], queued_messages=[AIMessage(content="")]))
    with pytest.raises(AgentNoResponseError):
        await invoke_agent(agent, INCOMING)


async def test_loose_text_has_warning(build):
    from src.agent.harness import invoke_agent

    agent = build(ToolCapableFakeLLM(responses=["just text"]))
    result = await invoke_agent(agent, INCOMING)
    assert result["body"] == "just text"
    assert result["status_code"] == 200
    assert result["content_type"] == "text/plain"
    assert result["warning"]


async def test_request_text_never_returned(build):
    from src.agent.harness import invoke_agent

    agent = build(ToolCapableFakeLLM(responses=[""]))
    with pytest.raises(AgentNoResponseError):
        await invoke_agent(agent, INCOMING)


async def test_block_list_content_flattened(build):
    from src.agent.harness import invoke_agent

    msg = AIMessage(content=[{"type": "text", "text": "hello "}, {"type": "text", "text": "there"}])
    agent = build(ToolCapableFakeLLM(responses=[], queued_messages=[msg]))
    result = await invoke_agent(agent, INCOMING)
    assert result["body"] == "hello there"


async def test_timeout(build):
    from src.agent.harness import invoke_agent

    agent = build(SlowFakeLLM(responses=["x"], delay=5))
    start = time.monotonic()
    with pytest.raises(AgentTimeoutError):
        await invoke_agent(agent, INCOMING, timeout_seconds=0.1)
    assert time.monotonic() - start < 1.5


@pytest.mark.parametrize("name", ["APIConnectionError", "AuthenticationError", "RateLimitError"])
async def test_provider_errors_become_unavailable(build, name):
    from src.agent.harness import invoke_agent

    exc = _provider_exc(name)
    agent = build(RaisingFakeLLM(responses=[], exc=exc))
    with pytest.raises(LLMUnavailableError) as info:
        await invoke_agent(agent, INCOMING)
    assert info.value.__cause__ is exc


async def test_bedrock_throttling_unavailable(build):
    from src.agent.harness import invoke_agent

    agent = build(RaisingFakeLLM(responses=[], exc=_client_error("ThrottlingException")))
    with pytest.raises(LLMUnavailableError):
        await invoke_agent(agent, INCOMING)


async def test_bedrock_validation_error_propagates(build):
    from src.agent.harness import invoke_agent

    exc = _client_error("ValidationException")
    agent = build(RaisingFakeLLM(responses=[], exc=exc))
    with pytest.raises(type(exc)):
        await invoke_agent(agent, INCOMING)


async def test_unrelated_error_propagates(build):
    from src.agent.harness import invoke_agent

    agent = build(RaisingFakeLLM(responses=[], exc=ValueError("bug")))
    with pytest.raises(ValueError):
        await invoke_agent(agent, INCOMING)


async def test_loop_limit(build):
    from src.agent.harness import invoke_agent

    calls = [
        AIMessage(content="", tool_calls=[ToolCall(name="list_files", args={}, id=f"t{i}")])
        for i in range(60)
    ]
    agent = build(ToolCapableFakeLLM(responses=[], queued_messages=calls))
    with pytest.raises(AgentLoopLimitError):
        await invoke_agent(agent, INCOMING)


async def test_structured_respond_still_works(build):
    from src.agent.harness import invoke_agent

    msg = AIMessage(
        content="",
        tool_calls=[ToolCall(name="respond", args={"body": "hi", "status_code": 201}, id="r")],
    )
    agent = build(ToolCapableFakeLLM(responses=[], queued_messages=[msg]))
    result = await invoke_agent(agent, INCOMING)
    assert result["body"] == "hi"
    assert result["status_code"] == 201
    assert "warning" not in result


async def test_ai_text_that_is_structured_json(build):
    from src.agent.harness import invoke_agent

    payload = json.dumps(
        {"body": "x", "status_code": 202, "headers": {}, "content_type": "text/plain"}
    )
    agent = build(ToolCapableFakeLLM(responses=[], queued_messages=[AIMessage(content=payload)]))
    result = await invoke_agent(agent, INCOMING)
    assert result["status_code"] == 202
    assert "warning" not in result
