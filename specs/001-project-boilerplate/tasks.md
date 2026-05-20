# Tasks: Project Boilerplate

**Input**: Design documents from `specs/001-project-boilerplate/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md

**Note**: Constitution Principle III (Test-First) is **NON-NEGOTIABLE**. Within every user story phase, test tasks MUST precede their implementation tasks. Tests MUST be confirmed failing before implementation begins.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization — directory structure, dependency manifest, configuration files.

- [x] T001 Create project directory structure: `src/agent/`, `src/api/`, `src/config/`, `src/tools/`, `tests/unit/tools/`, `tests/integration/`, `config/`
- [x] T002 Create `pyproject.toml` with runtime dependencies (fastapi, uvicorn[standard], langgraph, langchain-core, pydantic-settings, python-dotenv, structlog), dev dependencies (pytest, pytest-asyncio, httpx, ruff), and ruff + pytest configuration sections
- [x] T003 [P] Create `.env.example` listing all environment variables: required (LLM_API_KEY, LLM_MODEL) and optional with defaults (HOST, PORT, MAX_REQUEST_BODY_SIZE)
- [x] T004 [P] Create `config/personality.md` with a placeholder persona text so the service starts after a plain clone without manual configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Module scaffolding that MUST be in place before any user story can be implemented.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [x] T005 Create all `__init__.py` files: `src/agent/__init__.py`, `src/api/__init__.py`, `src/config/__init__.py`, `src/tools/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/tools/__init__.py`, `tests/integration/__init__.py`
- [x] T006 [P] Create `src/config/settings.py` stub — empty `BaseSettings` subclass (fields added in US1 implementation)
- [x] T007 [P] Create `src/api/errors.py` stub — empty module (handlers added in US1 implementation)

**Checkpoint**: Module stubs in place — user story phases can begin.

---

## Phase 3: User Story 1 — Developer First Run (Priority: P1) 🎯 MVP

**Goal**: Service starts, validates configuration, loads personality, initializes the LangGraph agent harness, serves `GET /health`, and routes all HTTP requests through the agent returning `{"reply": "..."}`.

**Independent Test**: `curl http://localhost:8000/health` → `{"status":"ok","agent":"ready"}`; `curl -X POST http://localhost:8000/hello -d "hi"` → `{"reply":"..."}`.

### Tests — Write and confirm FAILING before implementing (Constitution Principle III)

- [x] T008 [P] [US1] Write failing test: `GET /health` returns 200 with `{"status":"ok","agent":"ready"}` in `tests/integration/test_harness.py` (use FastAPI `TestClient`)
- [x] T009 [P] [US1] Write failing test: request to any path returns JSON body with `"reply"` key in `tests/integration/test_harness.py` (use `FakeListChatModel` from `langchain_core` configured to emit a `respond` tool call)
- [x] T010 [P] [US1] Write failing test: service startup raises `SystemExit` when a required environment variable is absent in `tests/unit/test_startup.py`
- [x] T011 [P] [US1] Write failing test: service startup raises `SystemExit` when `config/personality.md` is missing in `tests/unit/test_startup.py`
- [x] T012 [P] [US2] Write failing test: harness system prompt contains both the personality file content and the programmatic instruction block as distinct sections in `tests/unit/test_harness.py`
- [x] T013 [P] [US2] Write failing test: harness with an empty `config/personality.md` starts successfully and system prompt contains only the programmatic instruction block (no character section) in `tests/unit/test_harness.py`

### Implementation

- [x] T014 [US1] Implement `src/config/settings.py` — `BaseSettings` subclass with all fields from `data-model.md` (Settings entity), module-level instantiation, `try/except ValidationError` at entry point → `sys.exit(1)` with formatted error
- [x] T015 [US1] Implement `src/agent/registry.py` — module-level `TOOLS: list` (initially empty; respond tool added in US3)
- [x] T016 [US1] Implement `src/agent/harness.py` — load `config/personality.md` (raise `SystemExit` if missing; empty file is valid), assemble system prompt (personality content + programmatic instruction block as separate constant; programmatic block MUST instruct agent to always call `respond` when ready to reply), call `create_react_agent` from `langgraph.prebuilt` with model, tools from registry, and a `recursion_limit` hard ceiling
- [x] T017 [US1] Implement `src/api/errors.py` — FastAPI exception handlers for: `HTTPException(413)` → structured JSON `{"error":"request_too_large","message":"..."}`, LLM provider error → 503 structured JSON, unhandled `Exception` → 500 structured JSON; no raw stack traces in any response
- [x] T018 [US1] Implement `src/api/app.py` — FastAPI app factory with `lifespan` context manager (configure structlog JSON renderer, validate settings, load personality, initialize harness); register error handlers from `errors.py`; add `GET /health` endpoint
- [x] T019 [US1] Add catch-all route to `src/api/app.py` — `api_route("/{full_path:path}", methods=[...all methods])`, enforce `MAX_REQUEST_BODY_SIZE` before reading body (raise `HTTPException(status_code=413)` if exceeded), pass `IncomingRequest` (method, path, headers, raw body, query params) to harness, return `{"reply": agent_response}`; emit structlog event with method, path, and response status on every request

**Checkpoint**: US1 complete — `pytest tests/integration/test_harness.py tests/unit/test_startup.py tests/unit/test_harness.py` all green; service starts and routes requests through the agent.

---

## Phase 4: User Story 2 — Customizing Agent Personality (Priority: P2)

**Goal**: Changing only `config/personality.md` and restarting produces a different agent tone; programmatic behavioral constraints are always injected separately and never live in the personality file.

**Independent Test**: Edit `config/personality.md` to a distinct persona, restart service, send the same request — response tone reflects the new persona.

### Implementation

- [x] T020 [US2] Update `src/agent/harness.py` — extract programmatic instruction constant into a clearly named variable; document the assembly rule (`personality_content + "\n\n" + PROGRAMMATIC_INSTRUCTIONS`); add structured log line on startup indicating whether personality content was loaded or empty

**Checkpoint**: US2 complete — `pytest tests/unit/test_harness.py` green (tests written in Phase 3); personality swap verified manually per `specs/001-project-boilerplate/quickstart.md`.

---

## Phase 5: User Story 3 — Adding a New Tool (Priority: P3)

**Goal**: The respond tool demonstrates the complete TDD tool pattern: isolated contract test (no agent/LLM) → implementation → registration → agent invocation. `respond` is also the built-in agent exit point: when the agent calls it, the loop terminates and the reply is returned to the HTTP client.

**Independent Test**: `pytest tests/unit/tools/test_respond.py` passes with no LLM API calls; `curl -X POST http://localhost:8000/api/echo -d '{"repeat_this":"eat my shorts"}'` returns `{"reply":"eat my shorts"}`.

### Tests — Write and confirm FAILING before implementing (tool must not exist yet)

- [x] T021 [US3] Write failing test for respond tool contract in `tests/unit/tools/test_respond.py` — assert `tool.invoke({"reply": "hello"})` returns `"hello"`; assert `tool.invoke({"reply": ""})` raises `ToolException`; run test and confirm it fails because `src/tools/respond.py` does not exist

### Implementation

- [x] T022 [US3] Implement `src/tools/respond.py` — `BaseTool` subclass with `name="respond"`, `description`, `args_schema` (Pydantic model with `reply: str`), `return_direct=True`, `_run` method that returns the reply string; raises `ToolException` on empty reply
- [x] T023 [US3] Register respond tool in `src/agent/registry.py` — import `RespondTool` and add instance to the `TOOLS` list
- [x] T024 [US3] Write integration test in `tests/integration/test_harness.py` — using `FakeListChatModel` configured to emit a `respond` tool call with `reply="eat my shorts"`, send `POST /api/echo {"repeat_this":"eat my shorts"}` and verify the response is `{"reply":"eat my shorts"}`

**Checkpoint**: US3 complete — `pytest tests/unit/tools/test_respond.py` passes in full isolation (no LLM); respond tool reachable through running service.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T025 [P] Run `ruff check src/ tests/` and `ruff format src/ tests/`, fix all reported errors, and confirm both pass clean — this is the pre-commit check; document the single test command (`pytest`) in `pyproject.toml` scripts section
- [x] T026 Run full test suite `pytest` in a clean virtual environment and confirm all tests pass (SC-005)
- [x] T027 [P] Follow `specs/001-project-boilerplate/quickstart.md` from scratch in a new venv and confirm service starts and health check responds within 10 minutes (SC-001 validation)
- [x] T028 [P] Manual SC-006 validation: edit `config/personality.md` to a clearly distinct persona, restart service, send a request, confirm response tone reflects the new persona

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2; no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on US1 (`harness.py` must exist to implement personality assembly); US2 tests written in Phase 3
- **US3 (Phase 5)**: Depends on US1 (`registry.py` must exist); tool unit tests (T021–T022) are independently runnable once `BaseTool` import is available
- **Polish (Phase 6)**: Depends on all desired stories being complete

### User Story Dependencies

- **US1 (P1)**: No story dependencies — foundational harness and app
- **US2 (P2)**: Depends on US1 (`harness.py` exists); tests written in Phase 3 (red until T020)
- **US3 (P3)**: Depends on US1 (`registry.py` exists); tool unit tests are independent of the agent

### Within Each User Story

1. Write test(s) → confirm each fails (Red)
2. Execute implementation tasks in order
3. Confirm test(s) pass (Green)
4. Refactor if needed without changing behavior
5. Validate checkpoint before moving to next phase

### Parallel Opportunities

- T003, T004 (Setup): can run in parallel
- T006, T007 (Foundational stubs): can run in parallel
- T008, T009, T010, T011, T012, T013 (Phase 3 tests): all can be written in parallel
- T025, T027, T028 (Polish): can run in parallel

---

## Parallel Example: Phase 3 Tests

```bash
# Write all six Phase 3 failing tests simultaneously (different functions/files):
Task: "Write failing test T008: health check in tests/integration/test_harness.py"
Task: "Write failing test T009: agent catch-all route in tests/integration/test_harness.py"
Task: "Write failing test T010: missing env var startup failure in tests/unit/test_startup.py"
Task: "Write failing test T011: missing personality.md startup failure in tests/unit/test_startup.py"
Task: "Write failing test T012: system prompt sections in tests/unit/test_harness.py"
Task: "Write failing test T013: empty personality harness in tests/unit/test_harness.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 — tests first, then implementation
4. **STOP AND VALIDATE**: `pytest tests/integration/ tests/unit/`; start service; `curl /health`; `curl -X POST /any-path -d "hello"`
5. Service is live, all requests route through the agent — **MVP delivered**

### Incremental Delivery

1. Setup + Foundational → module stubs in place
2. **US1** → running service, agent harness active → MVP
3. **US2** → personality customization verified
4. **US3** → respond tool (agent exit point) complete, extensibility demonstrated
5. Polish → production-quality code style, validated quickstart

### TDD Constraint (NON-NEGOTIABLE per Constitution Principle III)

Red → Green → Refactor for every implementation unit. No production code without a prior failing test. Commit after each completed Red→Green→Refactor cycle.

---

## Notes

- `[P]` tasks operate on different files with no incomplete-task dependencies — safe to parallelize
- Tests are **mandatory**, not optional — Constitution Principle III applies to every phase
- `FakeListChatModel` (from `langchain_core.language_models.fake_chat_models`) allows testing LangGraph agent routes without real LLM calls; configure it to emit a `respond` tool call for integration tests
- `ToolException` (from `langchain_core.tools`) is the standard error type for tool contract failures
- The `respond` tool uses `return_direct=True` — LangGraph returns its output directly as the final agent response, terminating the loop
- `recursion_limit` on `create_react_agent` is the hard ceiling if the agent fails to call `respond`
- Commit after each task or logical group per constitution development workflow
- Stop at each checkpoint to independently validate the story before proceeding to the next
