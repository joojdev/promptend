# Implementation Plan: Chores Hardening

**Branch**: `002-chores-hardening` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-chores-hardening/spec.md`

## Summary

Three small hardening slices on the existing FastAPI + LangGraph harness:

1. **Header redaction (P1)**: build the agent's `headers` dict through a redaction function driven by two new settings (exact names, name fragments). `X-Dopamine-Key` is always dropped.
2. **Guards (P2)**: a per-IP in-memory sliding-window rate limiter and an optional constant-time access-key check, both run in the catch-all route before the agent. No new dependency.
3. **Agent outcomes (P3)**: `invoke_agent` classifies the run (structured / loose text / no response / timeout / provider outage / loop limit) and raises typed errors that the existing error-handler module maps to 502 / 504 / 503 / 500. Loose text is returned with `X-Dopamine-Warning`. The no-op try/except in `app.py` is removed.

Every scenario is tested with the existing `ToolCapableFakeLLM`; rejected requests assert zero agent invocations.

## Technical Context

**Language/Version**: Python 3.11+ (venv currently runs 3.14)

**Primary Dependencies**: existing only — `fastapi`, `langgraph` (`GraphRecursionError` from `langgraph.errors`), `langchain-core`, `pydantic-settings`, `structlog`. Stdlib: `asyncio`, `hmac`, `time`, `collections.deque`. No new packages.

**Storage**: N/A — rate-limit counters live in process memory and reset on restart.

**Testing**: `pytest` + `pytest-asyncio`, `fastapi.testclient.TestClient`, `tests/conftest.py::ToolCapableFakeLLM` (plus a small slow/raising fake added to conftest).

**Target Platform**: Linux server, single process.

**Project Type**: Web service (existing).

**Performance Goals**: Guard overhead negligible relative to LLM latency; limiter operations O(1) amortized.

**Constraints**: Added timeout bound: caller waits at most `AGENT_TIMEOUT_SECONDS` + 2 s. Rejections (401/429) must not call the LLM. Error bodies must not leak provider text or stack traces.

**Scale/Scope**: Single developer / small team; one process; limiter memory bounded by (distinct IPs × limit) and pruned of idle IPs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent-as-Harness: no handler may produce a response that bypasses the agent | ✅ PASS | 401 / 429 / 502 / 504 / 500-loop are infrastructure guards, allowed by the v1.1.0 exception (protect the LLM from cost/abuse, or report agent-run failures). No 2xx is produced by guards; rejection tests assert zero agent calls. |
| I. Tools are the only extension point | ✅ PASS | No new agent capability; guards and error mapping are infrastructure, not behavior the agent could provide. |
| II. Customizable Personality | ✅ PASS | Personality loading untouched. Redaction does not alter the prompt template. |
| III. Test-First | ✅ PASS | Tasks will order failing tests before implementation; one test per scenario with fake LLM. |
| IV. Simplicity / YAGNI | ✅ PASS | Hand-rolled ~30-line limiter instead of a library; no distributed store; no proxy-header handling. |
| Config: `BaseSettings`, `.env`, ruff, Python 3.11+ | ✅ PASS | All new knobs are `Settings` fields documented in `.env.example`. |

**Post-Design Re-check**: ✅ All gates pass under constitution v1.1.0. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-chores-hardening/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── http-errors.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
src/
├── agent/
│   └── harness.py       # invoke_agent: outcome classification, timeout, provider-error mapping
├── api/
│   ├── app.py           # catch-all: guards, header redaction, warning header; dead try/except removed
│   ├── errors.py        # + AgentNoResponseError, AgentTimeoutError, AgentLoopLimitError and handlers
│   └── guards.py        # NEW: RateLimiter, check_access_key, redact_headers
└── config/
    └── settings.py      # + rate_limit_per_minute, dopamine_access_key, agent_timeout_seconds,
                         #   sensitive_header_names, sensitive_header_fragments

tests/
├── conftest.py          # + slow / raising fake LLM helpers
├── unit/
│   ├── test_guards.py   # redaction, limiter, key compare
│   └── test_agent_outcomes.py
└── integration/
    └── test_hardening.py  # per-scenario HTTP tests with fake LLM
.env.example             # document new settings
```

**Structure Decision**: Single-project layout kept. One new module (`src/api/guards.py`) holds the three pure helpers so they are unit-testable without the app; everything else edits existing files.

## Complexity Tracking

No violations. The Principle I guard behavior was codified in constitution v1.1.0.
