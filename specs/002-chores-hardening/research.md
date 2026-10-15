# Research: Chores Hardening

No `NEEDS CLARIFICATION` items remained after the spec. The items below are design choices that needed checking against the code.

## R1. Where do guards run?

- **Decision**: Inline in the catch-all route, in this order: body-size check (existing), access key, rate limit, then agent. `/health` is a separate route and is therefore naturally exempt.
- **Rationale**: Matches the spec's order of checks; no middleware stack to reason about; exempting `/health` needs no path matching.
- **Alternatives**: Starlette middleware (would need explicit `/health` bypass and runs for CORS preflight too); FastAPI `Depends` (runs before the body size check, reversing the spec's order).

## R2. Rate-limit algorithm and library

- **Decision**: Sliding-window log: `dict[str, deque[float]]` of monotonic timestamps per client host; drop entries older than 60 s on each hit; reject when the deque already holds `limit` entries. Idle hosts are pruned opportunistically when the dict grows.
- **Rationale**: ~30 lines, exact, no dependency, memory bounded by hosts × limit. A limiter instance is created per `create_app` so tests do not share state.
- **Alternatives**: `slowapi` / `limits` (extra dependency for one rule, pulls in extra machinery); fixed window counter (allows 2× bursts at window edges); token bucket (more state than needed).
- **Client identity**: `request.client.host`. `X-Forwarded-For` is deliberately ignored — trusting it unconditionally lets an attacker evade the limit by forging it.

## R3. Access-key comparison

- **Decision**: `hmac.compare_digest` over UTF-8 bytes of the configured key and the header value; missing header counts as mismatch. Key comes from `DOPAMINE_ACCESS_KEY`; empty/unset disables the check.
- **Rationale**: Constant-time (FR-011) with stdlib.
- **Note**: `X-Dopamine-Key` is removed from the header dict handed to the agent in every case, including when no key is configured.

## R4. Header redaction configuration

- **Decision**: Two comma-separated settings: `SENSITIVE_HEADER_NAMES` (exact, default `authorization,proxy-authorization,cookie,set-cookie,x-api-key`) and `SENSITIVE_HEADER_FRAGMENTS` (substring, default `token,secret,key`). Lower-cased at load. A header is sensitive if its lower-cased name is in the first set or contains any fragment from the second.
- **Rationale**: The default rule has two different match kinds, so one flat list cannot express it. Plain strings avoid pydantic-settings' JSON-only parsing for `list[str]` env values.
- **Alternatives**: Single list with `*key*` glob syntax (more parsing logic, harder to document); regex setting (footgun).
- **Starlette detail**: `request.headers` is already lower-case; repeated headers collapse in `dict(request.headers)` as today (behavior unchanged).

## R5. Provider error mapping (FR-016)

- **Decision**: In `invoke_agent`, catch `Exception` from `ainvoke` and classify by walking `type(exc).__mro__` class names (`APIConnectionError`, `APITimeoutError`, `AuthenticationError`, `PermissionDeniedError`, `RateLimitError`, `InternalServerError`, `OverloadedError`, `ServiceUnavailableError`, `EndpointConnectionError`, `ConnectTimeoutError`, `NoCredentialsError`, `ConnectError`) whose defining module starts with `anthropic`, `openai`, `botocore`, `httpx` or `httpcore`. Matches raise `LLMUnavailableError` (chained with `from exc`); anything else re-raises unchanged.
- **Rationale**: `openai` and `langchain-aws` are optional extras, so they cannot be imported unconditionally. Matching on name and module needs no optional imports and covers all three providers. The original exception is logged (class name only, no message) and chained, never sent to the client.
- **Alternatives**: Import each SDK lazily in try blocks (verbose, import cost); treat every exception as 503 (hides real bugs, violates the "unexpected = 500" distinction); catch `ClientError` from botocore broadly (also covers validation errors, too wide).
- **Verified**: `anthropic 1.14.0` exposes `APIConnectionError`, `AuthenticationError`, `RateLimitError` etc.; `openai` is not installed in this venv, so tests build stand-in exception classes with the same names/modules instead of importing it.

## R6. Agent outcome classification (FR-013, FR-014, FR-017)

- **Finding**: the current loop iterates `reversed(messages)` and returns the first message with truthy content. The first message in the list is the user's own request, so an agent that emits nothing returns the *request text* as a 200 `text/plain` echo instead of the empty fallback. This is a latent bug adjacent to the reported one.
- **Decision**: Walk messages in reverse. A `ToolMessage` whose content parses as a structured response wins. Otherwise the last `AIMessage` with non-empty text is loose text (`warning` set on the result). Human messages are ignored. If neither exists, raise `AgentNoResponseError`. `GraphRecursionError` is caught and raised as `AgentLoopLimitError`.
- **Content shape**: `AIMessage.content` can be a list of blocks for some providers; non-string content is flattened to its text blocks before the emptiness check.
- **Rationale**: Matches the spec's three result classes without changing the structured-response path.

## R7. Timeout (FR-015)

- **Decision**: `asyncio.wait_for(agent.ainvoke(...), timeout=settings.agent_timeout_seconds)`; `TimeoutError` becomes `AgentTimeoutError` (504). Settings validator requires `> 0`.
- **Rationale**: Cancels the awaiting coroutine on expiry, so the caller is released promptly.
- **Caveat**: a provider call running in a thread executor cannot be force-killed; it is abandoned. Acceptable for v1; noted in Assumptions of the spec ("run is abandoned").
- **Test approach**: fake LLM with an async `_agenerate` that sleeps, timeout set to a fraction of a second in test settings.

## R8. Loop-limit status code

- **Decision**: 500 with error code `agent_loop_limit` (carried from the spec). 508 rejected as WebDAV-specific and poorly handled by intermediaries.

## R9. Dead try/except in `app.py`

- **Decision**: delete the `try/except LLMUnavailableError: raise / except Exception: raise` wrapper; call `invoke_agent` directly. Registered exception handlers already cover both types, so behavior is identical.
