from langchain_core.callbacks import BaseCallbackHandler


class UsageTracker(BaseCallbackHandler):
    """Per-request totals of provider-reported tokens and model tool calls.

    Updated as each LLM call ends, so the numbers are known even if the run later
    times out or fails.
    """

    run_inline = True

    def __init__(self) -> None:
        self.tokens_in = 0
        self.tokens_out = 0
        self.steps = 0

    def on_llm_end(self, response, **kwargs) -> None:
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if message is None:
                    continue
                usage = getattr(message, "usage_metadata", None) or {}
                self.tokens_in += usage.get("input_tokens", 0) or 0
                self.tokens_out += usage.get("output_tokens", 0) or 0
                self.steps += len(getattr(message, "tool_calls", None) or [])
