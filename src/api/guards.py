import hmac
import time
from collections import deque
from collections.abc import Mapping

REDACTED = "[REDACTED]"
ACCESS_KEY_HEADER = "x-dopamine-key"
WINDOW_SECONDS = 60.0
_SWEEP_THRESHOLD = 256


def redact_headers(
    headers: Mapping[str, str], names: frozenset[str], fragments: tuple[str, ...]
) -> dict[str, str]:
    """Copy headers for the agent: sensitive values masked, the access key dropped."""
    out: dict[str, str] = {}
    for name, value in headers.items():
        lowered = name.lower()
        if lowered == ACCESS_KEY_HEADER:
            continue
        if lowered in names or any(f in lowered for f in fragments):
            out[name] = REDACTED
        else:
            out[name] = value
    return out


class RateLimiter:
    """Per-host sliding-window limiter held in process memory."""

    def __init__(self, limit: int):
        self.limit = limit
        self._hits: dict[str, deque[float]] = {}

    def check(self, host: str) -> bool:
        now = time.monotonic()
        if len(self._hits) > _SWEEP_THRESHOLD:
            self._sweep(now)
        hits = self._hits.setdefault(host, deque())
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def _sweep(self, now: float) -> None:
        for host in [h for h, q in self._hits.items() if not q or now - q[-1] >= WINDOW_SECONDS]:
            del self._hits[host]


def check_access_key(provided: str | None, expected: str) -> bool:
    if not expected:
        return True
    if provided is None:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
