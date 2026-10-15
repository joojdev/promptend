from decimal import ROUND_HALF_UP, Decimal

from langchain_core.callbacks import BaseCallbackHandler

_MTOK = Decimal(1_000_000)
_MICRO = Decimal("0.000001")


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

    def cost_usd(self, price_in: float | None, price_out: float | None) -> str | None:
        """Estimated cost in USD with 6 decimals, or None when prices are not configured."""
        if price_in is None or price_out is None:
            return None
        cost = (
            self.tokens_in * Decimal(str(price_in)) + self.tokens_out * Decimal(str(price_out))
        ) / _MTOK
        return f"{cost.quantize(_MICRO, rounding=ROUND_HALF_UP):.6f}"
