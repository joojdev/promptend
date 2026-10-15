from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult


def _result(tokens_in=None, tokens_out=None, tool_calls=0):
    kwargs = {}
    if tokens_in is not None:
        kwargs["usage_metadata"] = {
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        }
    calls = [{"name": "respond", "args": {}, "id": f"c{i}"} for i in range(tool_calls)]
    message = AIMessage(content="", tool_calls=calls, **kwargs)
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def test_fresh_tracker_is_zero():
    from src.agent.usage import UsageTracker

    tracker = UsageTracker()
    assert (tracker.tokens_in, tracker.tokens_out, tracker.steps) == (0, 0, 0)


def test_sums_across_calls():
    from src.agent.usage import UsageTracker

    tracker = UsageTracker()
    tracker.on_llm_end(_result(100, 20, tool_calls=1))
    tracker.on_llm_end(_result(150, 30, tool_calls=1))
    assert (tracker.tokens_in, tracker.tokens_out, tracker.steps) == (250, 50, 2)


def test_missing_usage_counts_zero_tokens():
    from src.agent.usage import UsageTracker

    tracker = UsageTracker()
    tracker.on_llm_end(_result(tool_calls=1))
    assert (tracker.tokens_in, tracker.tokens_out, tracker.steps) == (0, 0, 1)


def test_each_tool_call_is_a_step():
    from src.agent.usage import UsageTracker

    tracker = UsageTracker()
    tracker.on_llm_end(_result(1, 1, tool_calls=2))
    assert tracker.steps == 2
