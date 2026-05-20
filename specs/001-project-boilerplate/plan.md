# Implementation Plan: Project Boilerplate

**Branch**: `001-project-boilerplate` | **Date**: 2026-05-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-project-boilerplate/spec.md`

## Summary

Establish a minimal, runnable backend service where a LangGraph ReAct agent IS the HTTP request harness. Every incoming HTTP request (all methods, all paths) is forwarded — including method, path, headers, and raw body — to the agent, which decides which registered tools to invoke and constructs the final response. The boilerplate includes startup validation (personality file, required env vars), structured JSON logging, a health check endpoint, one example tool with isolated tests, and a developer setup guide.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- `fastapi` + `uvicorn` — HTTP server; catch-all route with raw body access
- `langgraph` (`create_react_agent`) — prebuilt ReAct agent; replaces legacy `AgentExecutor`
- `langchain-core` — `BaseTool`, `ToolException`, message types
- `pydantic-settings` — `BaseSettings` subclass for all configuration
- `python-dotenv` — `.env` file loading
- `structlog` — structured JSON logging with bound request context

**Storage**: N/A — agent is stateless per request; no persistence in scope

**Testing**: `pytest` + `pytest-asyncio`

**Target Platform**: Linux server (local development first)

**Project Type**: Web service (HTTP backend)

**Performance Goals**: Standard interactive response times; no high-throughput target for v1

**Constraints**: LLM API call latency dominates; no sub-100ms SLA required for v1

**Scale/Scope**: Single developer/small team local use; no horizontal scaling in v1 scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent-as-Harness: every request routes through agent, no bypasses | ✅ PASS | Catch-all FastAPI route feeds 100% of requests to `create_react_agent` |
| I. Tools are the only extension point | ✅ PASS | No logic in route handlers; behavior added only as registered tools |
| II. Customizable Personality: `config/personality.md` loaded at startup as system prompt | ✅ PASS | Loaded in lifespan, injected per-request; missing file → startup failure |
| II. Personality file is character/tone only; behavioral constraints injected separately | ✅ PASS | System prompt = personality content + programmatic tool/constraint injection |
| III. Test-First: tools tested in isolation before agent wiring | ✅ PASS | `BaseTool.invoke()` called directly in unit tests; no agent/LLM required |
| IV. Simplicity/YAGNI: no speculative abstractions | ✅ PASS | Prebuilt `create_react_agent` chosen over custom LangGraph graph; no over-engineering |
| Config: pydantic-settings BaseSettings, python-dotenv, ruff | ✅ PASS | All three mandated; hardcoded values forbidden |
| Config: Python 3.11+ | ✅ PASS | |

**Post-Design Re-check**: ✅ All gates pass. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-project-boilerplate/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── http-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
├── agent/
│   ├── __init__.py
│   ├── harness.py       # create_react_agent setup, system prompt assembly
│   └── registry.py      # Tool registration
├── api/
│   ├── __init__.py
│   ├── app.py           # FastAPI app factory, lifespan, catch-all route, health check
│   └── errors.py        # Global error handlers → structured JSON responses
├── config/
│   ├── __init__.py
│   └── settings.py      # BaseSettings subclass; all env-backed config
└── tools/
    ├── __init__.py
    └── respond.py       # Built-in respond tool (return_direct=True) — agent exit point

tests/
├── unit/
│   ├── test_startup.py      # Startup failure tests (missing env var, missing personality)
│   ├── test_harness.py      # System prompt assembly tests
│   └── tools/
│       └── test_respond.py  # Respond tool contract test (isolated, no agent)
└── integration/
    └── test_harness.py      # Agent + route integration test

config/
└── personality.md       # User-editable personality/tone file (checked into repo)

.env.example             # Required environment variable template
pyproject.toml           # Dependencies, ruff config, pytest config
```

**Structure Decision**: Single project layout. No frontend; no multi-service split. All source under `src/`; all tests under `tests/`. Config files (personality, env template) at repo root level under `config/`.

## Complexity Tracking

> No constitution violations detected. Table intentionally empty.
