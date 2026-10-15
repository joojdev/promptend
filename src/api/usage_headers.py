import structlog
from fastapi import Request
from fastapi.responses import Response

log = structlog.get_logger()

USAGE_HEADERS = (
    "X-Dopamine-Tokens-In",
    "X-Dopamine-Tokens-Out",
    "X-Dopamine-Steps",
    "X-Dopamine-Cost-USD",
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
    response.headers["X-Dopamine-Tokens-In"] = str(usage.tokens_in)
    response.headers["X-Dopamine-Tokens-Out"] = str(usage.tokens_out)
    response.headers["X-Dopamine-Steps"] = str(usage.steps)

    log.info(
        "request",
        method=method,
        path=path,
        status=response.status_code,
        tokens_in=usage.tokens_in,
        tokens_out=usage.tokens_out,
        steps=usage.steps,
    )
    return response
