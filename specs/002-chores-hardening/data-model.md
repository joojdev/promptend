# Data Model: Chores Hardening

No persistent storage. All state is configuration or in-process memory.

## Settings (additions to `Settings`)

| Field | Env var | Type | Default | Validation |
|-------|---------|------|---------|------------|
| `rate_limit_per_minute` | `RATE_LIMIT_PER_MINUTE` | int | `20` | `> 0` |
| `dopamine_access_key` | `DOPAMINE_ACCESS_KEY` | str | `""` (disabled) | stripped; empty = no key required |
| `agent_timeout_seconds` | `AGENT_TIMEOUT_SECONDS` | float | `30` | `> 0` |
| `sensitive_header_names` | `SENSITIVE_HEADER_NAMES` | str (comma-separated) | `authorization,proxy-authorization,cookie,set-cookie,x-api-key` | lower-cased, blanks dropped |
| `sensitive_header_fragments` | `SENSITIVE_HEADER_FRAGMENTS` | str (comma-separated) | `token,secret,key` | lower-cased, blanks dropped |

Invalid values fail startup through the existing `load_settings()` error path.

## SensitiveHeaderRule

Derived from the two header settings.

- `names: frozenset[str]` — exact lower-case names.
- `fragments: tuple[str, ...]` — lower-case substrings.
- `is_sensitive(name) -> bool` — `name.lower() in names or any(f in name.lower() for f in fragments)`.

`redact_headers(headers, rule) -> dict[str, str]`: returns a new dict with the same keys; sensitive values replaced by `"[REDACTED]"`; `x-dopamine-key` omitted entirely.

## ClientQuota (inside `RateLimiter`)

- Key: client host string (`request.client.host`, `"unknown"` when absent).
- Value: `deque[float]` of monotonic timestamps within the last 60 s.
- Transition per request: purge timestamps older than 60 s → if `len >= limit` reject (429) → else append now and accept.
- Idle hosts (empty deque after purge) are removed when the dict is swept.

## AgentOutcome

Classification produced by `invoke_agent`:

| Outcome | Trigger | Result |
|---------|---------|--------|
| structured | `ToolMessage` parses as response dict | returned as today |
| loose_text | last `AIMessage` has text, no structured response | dict with `warning` key set → 200 + `X-Dopamine-Warning` |
| no_response | no structured response and no AI text | `AgentNoResponseError` → 502 |
| timeout | `asyncio.wait_for` expires | `AgentTimeoutError` → 504 |
| provider_unavailable | connection / auth / rate-limit exception from provider SDK | `LLMUnavailableError` → 503 |
| loop_limit | `GraphRecursionError` | `AgentLoopLimitError` → 500 |
| other exception | anything else | unchanged → generic 500 `internal_error` |

## Error types (`src/api/errors.py`)

`AgentNoResponseError`, `AgentTimeoutError`, `AgentLoopLimitError` — plain `Exception` subclasses, same style as `LLMUnavailableError`, each with a registered handler returning the JSON bodies in [contracts/http-errors.md](contracts/http-errors.md).
