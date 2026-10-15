---

description: "Task list for Chores Hardening"
---

# Tasks: Chores Hardening

**Input**: Design documents from `specs/002-chores-hardening/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-errors.md

**Tests**: REQUIRED. The spec (FR-020) demands one automated test per scenario with a fake LLM, and the constitution (Principle III) mandates test-first. Within each story, write the tests first and confirm they fail before implementing.

**Organization**: Grouped by user story. Stories are independent; US1 → US2 → US3 is priority order, not a dependency chain, except that US1 and US2 both add functions to `src/api/guards.py` and US2/US3 both edit `src/api/app.py`, so do not run those edits concurrently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1, US2, US3

## Phase 1: Setup

**Purpose**: Confirm baseline before changing anything.

- [X] T001 Run `uv run pytest` and `uv run ruff check .` from repo root and record that the baseline is green (fix nothing here; if red, stop and report)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Settings, error types and test helpers shared by all stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add unit tests for the new settings in `tests/unit/test_startup.py`: defaults, env override, non-positive `RATE_LIMIT_PER_MINUTE` / `AGENT_TIMEOUT_SECONDS` rejected, header lists lower-cased with blanks dropped, confirm they FAIL before T003
- [X] T003 Add settings fields to `src/config/settings.py`: `rate_limit_per_minute: int = 20` (> 0), `dopamine_access_key: str = ""` (stripped), `agent_timeout_seconds: float = 30` (> 0), `sensitive_header_names: str = "authorization,proxy-authorization,cookie,set-cookie,x-api-key"`, `sensitive_header_fragments: str = "token,secret,key"`. Add validators for the two `> 0` fields in the style of `size_positive`. Add a `sensitive_header_rule` helper (property or function) returning lower-cased `(frozenset names, tuple fragments)` with blanks dropped, per data-model.md
- [X] T004 [P] Add exception classes `AgentNoResponseError`, `AgentTimeoutError`, `AgentLoopLimitError` and their handlers in `src/api/errors.py` returning the status codes and JSON bodies from `contracts/http-errors.md` (502 `agent_no_response`, 504 `agent_timeout`, 500 `agent_loop_limit`). Add handlers for a new `UnauthorizedError` (401 `unauthorized`) and `RateLimitedError` (429, body exactly `{"error": "rate_limited"}`) in the same file
- [X] T005 [P] Add test helpers to `tests/conftest.py`: a `SlowFakeLLM` (extends `ToolCapableFakeLLM`, async `_agenerate` that `await asyncio.sleep(...)`), a `RaisingFakeLLM` (raises a configurable exception from `_generate` / `_agenerate`), and a `CountingFakeLLM` (or counter on `ToolCapableFakeLLM`) exposing how many times the model was invoked
- [X] T006 [P] Document the five new settings in `.env.example` under the "Optional (defaults shown)" block: `RATE_LIMIT_PER_MINUTE=20`, `# DOPAMINE_ACCESS_KEY=` (commented, optional), `AGENT_TIMEOUT_SECONDS=30`, `SENSITIVE_HEADER_NAMES=...`, `SENSITIVE_HEADER_FRAGMENTS=token,secret,key`, with one-line comments (FR-012)

**Checkpoint**: Settings, error types, test fakes and docs ready; stories can start.

---

## Phase 3: User Story 1 - Client credentials never reach the LLM provider (Priority: P1) 🎯 MVP

**Goal**: Sensitive header values are replaced by `[REDACTED]` before the agent sees them; ordinary headers pass unchanged; the list is configurable.

**Independent Test**: Send a request with `Authorization`, `Cookie`, `X-Custom-Token` and `User-Agent` to the app with a fake LLM and inspect the agent input.

### Tests for User Story 1 (write first, confirm FAIL)

- [X] T007 [P] [US1] Unit tests in `tests/unit/test_redaction.py` for `redact_headers`: default exact names (`authorization`, `proxy-authorization`, `cookie`, `set-cookie`, `x-api-key`) become `[REDACTED]`; fragment matches in mixed case (`X-Auth-Token`, `X-CLIENT-SECRET`, `My-Key-Id`) become `[REDACTED]`; `content-type` and `user-agent` unchanged; header names remain present; `x-dopamine-key` is omitted entirely; custom names/fragments override the defaults (spec scenarios 1–5)
- [X] T008 [P] [US1] Integration test in `tests/integration/test_redaction_http.py`: patch or wrap the fake LLM to capture the user message text; POST with `Authorization: Bearer abc123`, `Cookie: sid=zzz`, `X-Custom-Token: tok`, `User-Agent: ua-test`; assert the captured prompt contains `[REDACTED]` for the three secrets, contains none of `abc123`, `sid=zzz`, `tok`, and still contains `ua-test`

### Implementation for User Story 1

- [X] T009 [US1] Create `src/api/guards.py` with `redact_headers(headers: Mapping[str, str], names: frozenset[str], fragments: tuple[str, ...]) -> dict[str, str]` per data-model.md (case-insensitive match, `[REDACTED]` constant, drop `x-dopamine-key`)
- [X] T010 [US1] In `src/api/app.py` catch-all, replace `"headers": dict(request.headers)` with `redact_headers(request.headers, *settings.sensitive_header_rule)`; the real headers stay available to the route for later checks

**Checkpoint**: US1 complete and independently testable (T007, T008 pass).

---

## Phase 4: User Story 2 - Unwanted traffic cannot burn LLM budget (Priority: P2)

**Goal**: Per-IP rate limit (429) and optional access key (401), both before any agent call; `/health` exempt.

**Independent Test**: With a call-counting fake LLM, exceed the limit from one client and send missing/wrong keys; verify 429/401 responses and zero LLM calls for rejected requests.

### Tests for User Story 2 (write first, confirm FAIL)

- [X] T011 [P] [US2] Unit tests in `tests/unit/test_rate_limiter.py` for `RateLimiter`: first N hits allowed and N+1 rejected; separate hosts have independent quotas; after advancing a patched monotonic clock past 60 s the host is allowed again; idle hosts are pruned (dict does not grow without bound)
- [X] T012 [P] [US2] Unit tests in `tests/unit/test_access_key.py` for `check_access_key`: disabled when key is empty (any/none header passes); correct key passes; missing and wrong keys (including different length) fail; uses `hmac.compare_digest` (assert via monkeypatch spy)
- [X] T013 [P] [US2] Integration tests in `tests/integration/test_guards_http.py` using the counting fake LLM, one test per spec scenario: (a) N+1th request gets 429 with body exactly `{"error": "rate_limited"}` and LLM count stays at N; (b) two clients independent (use `TestClient(app, client=("1.2.3.4", 50000))` for different hosts); (c) window elapsed allows again; (d) key set + no header → 401, count 0; (e) key set + wrong header → 401, count 0; (f) key set + correct header → 200 and captured prompt does not contain `x-dopamine-key` or the key value; (g) no key configured → 200 as before; (h) `/health` returns 200 with limit exhausted and with key configured and no header; (i) oversized body still returns 413 and count 0; (j) limit exhausted for a client and key configured: a wrong-key request returns 401 (not 429) and does not advance that client's counter

### Implementation for User Story 2

- [X] T014 [US2] In `src/api/guards.py` add `RateLimiter` (sliding-window log per host with `time.monotonic`, window 60 s, `check(host) -> bool`, opportunistic pruning of idle hosts) and `check_access_key(provided: str | None, expected: str) -> bool` using `hmac.compare_digest` on UTF-8 bytes; empty `expected` returns `True`
- [X] T015 [US2] In `src/api/app.py` `create_app`, instantiate one `RateLimiter(settings.rate_limit_per_minute)` per app. In the catch-all, after the existing body-size check and before building `incoming`, run: access key (raise `UnauthorizedError` on failure, reading `request.headers.get("x-dopamine-key")`), then rate limit (raise `RateLimitedError` using `request.client.host if request.client else "unknown"`). Order per contract: 413 → 401 → 429 → agent
- [X] T016 [US2] Verify `.env.example` entries from T006 match the final setting names and defaults; no code change expected

**Checkpoint**: US1 and US2 both work (T011–T013 pass, zero LLM calls on rejections).

---

## Phase 5: User Story 3 - Agent failures are reported honestly (Priority: P3)

**Goal**: Distinct, honest responses for no-answer, loose text, timeout, provider outage and loop limit; dead code removed.

**Independent Test**: One request per scenario against a scripted fake LLM; check status, error code, headers.

### Tests for User Story 3 (write first, confirm FAIL)

- [X] T017 [P] [US3] Unit tests in `tests/unit/test_agent_outcomes.py` for `invoke_agent` / its helpers, one per scenario: (a) fake emits empty `AIMessage` and no tool call → `AgentNoResponseError`; (b) fake emits plain text `AIMessage` and no tool call → result dict with `body` = text, `status_code` 200, `content_type` `text/plain` and a non-empty warning; (c) user's own request text is never returned as a response (regression for R6); (d) list-of-blocks `AIMessage.content` is flattened; (e) slow fake with timeout 0.1 → `AgentTimeoutError` within ~1 s; (f) fake raising stand-in classes named `APIConnectionError`, `AuthenticationError`, `RateLimitError` (defined in a module whose name starts with `anthropic`, e.g. via `type(..., {"__module__": "anthropic"})`) → `LLMUnavailableError` with `__cause__` set; (g2) stand-in botocore `ClientError` with code `ThrottlingException` → `LLMUnavailableError`, with code `ValidationException` → propagates unchanged; (g) fake raising an unrelated `ValueError` → propagates unchanged; (h) fake that keeps calling a non-terminal tool until the recursion limit → `AgentLoopLimitError`; (i) structured `respond` tool call still returns the structured dict (regression); (j) `AIMessage` whose text is valid structured-response JSON is returned as structured, with no warning
- [X] T018 [P] [US3] Integration tests in `tests/integration/test_agent_outcomes_http.py`, one HTTP test per scenario with `TestClient`: no response → 502 `agent_no_response`; loose text → 200 `text/plain` with `X-Dopamine-Warning` header; timeout (`AGENT_TIMEOUT_SECONDS=0.2`, slow fake) → 504 `agent_timeout`; provider connection error → 503 `llm_unavailable`; provider auth error → 503; provider rate-limit error → 503; loop limit → 500 `agent_loop_limit`; for every error body assert no stack trace, provider message text or secret appears (FR-018)

### Implementation for User Story 3

- [X] T019 [US3] In `src/agent/harness.py` rewrite the tail of `invoke_agent` per research R6: ignore human messages; structured `ToolMessage` wins, and `AIMessage` text that itself parses as a structured response (via `_parse_tool_response`) is also treated as structured (spec edge case); otherwise last `AIMessage` with non-empty (flattened) text is loose text returned with a `warning` key (`"agent did not use a response tool"`); else raise `AgentNoResponseError`. Remove `_FALLBACK_RESPONSE`. Import the error types from `src.api.errors` (check for circular imports; if one appears, move the error classes to a new `src/errors.py` and re-export from `src/api/errors.py`)
- [X] T020 [US3] In `src/agent/harness.py` wrap `agent.ainvoke` in `asyncio.wait_for(..., timeout=timeout_seconds)`, add a `timeout_seconds` parameter to `invoke_agent`, convert `TimeoutError` to `AgentTimeoutError`, convert `langgraph.errors.GraphRecursionError` to `AgentLoopLimitError`, and add a private `_is_provider_unavailable(exc)` implementing the class-name/module allowlist from research R5; also treat botocore `ClientError` as unavailable when its error code is one of `ThrottlingException`, `AccessDeniedException`, `ExpiredTokenException`, `UnrecognizedClientException` (Bedrock); matching exceptions raise `LLMUnavailableError from exc` (log class name only), others re-raise unchanged
- [X] T021 [US3] In `src/api/app.py` pass `settings.agent_timeout_seconds` to `invoke_agent`, delete the redundant `try/except LLMUnavailableError: raise / except Exception: raise` wrapper (FR-019), and when `result` contains `warning` add header `X-Dopamine-Warning` to the response (drop the key from the result before building the response)

**Checkpoint**: All three stories work; every spec scenario has a passing test.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T022 [P] Run `uv run ruff check .` and `uv run ruff format --check .`; fix issues in the files touched by this feature only
- [X] T023 Run the full suite `uv run pytest` and confirm no regressions in the existing `tests/unit/test_harness.py` and `tests/integration/test_harness.py` (update expectations only where the old fallback / echo behavior was asserted, and say so in the commit message)
- [X] T024 Walk through `specs/002-chores-hardening/quickstart.md` manual smoke checks 1–6 against a running server and note any mismatch with `contracts/http-errors.md`
- [X] T025 [P] Confirm constitution v1.1.0 (Principle I guard exception) is in `.specify/memory/constitution.md` and plan.md Constitution Check shows PASS; no code change

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (T001)** first.
- **Phase 2 (T002–T006)** blocks all stories. T002 (tests) before T003 (settings) for strict TDD; T004–T006 are parallel with each other and with T003.
- **Phases 3–5** can start after Phase 2. Recommended order is P1 → P2 → P3. Parallel work across stories is possible for the test tasks, but implementation tasks touching `src/api/guards.py` (T009, T014) and `src/api/app.py` (T010, T015, T021) must be serialized.
- **Phase 6** after the desired stories are done.

### Within each story

- Tests (marked [P]) first, confirm they fail, then implementation, then re-run.
- US1: T007, T008 → T009 → T010.
- US2: T011, T012, T013 → T014 → T015 → T016.
- US3: T017, T018 → T019 → T020 → T021 (T019–T021 share `harness.py` / `app.py`; sequential).

## Parallel Examples

```text
# Phase 2 after T002:
T003, T004, T005, T006 together

# US1 tests together:
T007, T008

# US2 tests together:
T011, T012, T013

# US3 tests together:
T017, T018
```

## Implementation Strategy

### MVP first (User Story 1)

1. T001, Phase 2, Phase 3 (US1). Stop and validate: no credential reaches the LLM prompt. This alone removes the data leak.

### Incremental delivery

1. Foundation → US1 (stop the leak) → US2 (stop the budget burn) → US3 (honest errors). Each increment is shippable and leaves earlier tests green.

## Notes

- Test file split differs slightly from plan.md (which listed `test_guards.py` and `test_hardening.py`): tests are split per story so they can be written in parallel without file conflicts. The plan's structure listing is otherwise unchanged.
- Never import `openai` or `botocore` in tests; use stand-in exceptions (research R5).
- Rejected-request tests must assert the LLM call count, not just the status code (SC-002).
- Commit after each task or logical group.
