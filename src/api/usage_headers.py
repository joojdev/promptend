import structlog
from fastapi import Request
from fastapi.responses import Response

log = structlog.get_logger()

USAGE_HEADERS = (
    "X-Promptend-Tokens-In",
    "X-Promptend-Tokens-Out",
    "X-Promptend-Steps",
    "X-Promptend-Cost-USD",
)
_USAGE_LOWER = frozenset(h.lower() for h in USAGE_HEADERS)


def apply_usage(request: Request, response: Response, *, method: str, path: str) -> Response:
    """Stamp the request's usage on an agent-run response and log it.

    Responses for requests that never reached the agent (no tracker) are returned unchanged.
    """
    usage = getattr(request.state, "usage", None)
    if usage is None:
        return response

    for name in {k for k in response.headers.keys() if k.lower() in _USAGE_LOWER}:
        del response.headers[name]
    response.headers["X-Promptend-Tokens-In"] = str(usage.tokens_in)
    response.headers["X-Promptend-Tokens-Out"] = str(usage.tokens_out)
    response.headers["X-Promptend-Steps"] = str(usage.steps)

    fields = {"tokens_in": usage.tokens_in, "tokens_out": usage.tokens_out, "steps": usage.steps}
    price_in, price_out = getattr(request.app.state, "llm_prices", (None, None))
    cost = usage.cost_usd(price_in, price_out)
    if cost is not None:
        response.headers["X-Promptend-Cost-USD"] = cost
        fields["cost_usd"] = cost

    log.info("request", method=method, path=path, status=response.status_code, **fields)
    return response
