# Research: Project Boilerplate

**Date**: 2026-05-19 | **Phase**: 0 | **Plan**: [plan.md](plan.md)

## 1. LangChain Agent Type

**Decision**: `create_react_agent` from `langgraph.prebuilt`

**Rationale**: As of LangChain 0.2+ and into 2025, `AgentExecutor` is in maintenance mode. The LangGraph-backed prebuilt ReAct agent is the recommended replacement. It provides a clean `invoke({"messages": [...]})` API, native system prompt injection, structured tool error handling, and better observability hooks — all without requiring a custom LangGraph `StateGraph`. For the harness pattern (every request → agent → tools → response), this is the correct scope.

**Alternatives considered**:
- `AgentExecutor`: deprecated path, less capable error handling, more boilerplate
- Custom `StateGraph`: correct abstraction but violates YAGNI for v1; the prebuilt agent handles arbitrary tool dispatch already
- LCEL `RunnableWithTools`: requires manual ReAct loop wiring — unnecessary complexity

---

## 2. HTTP Framework

**Decision**: FastAPI + uvicorn

**Rationale**: FastAPI provides raw request body access via `Request.body()` (returns `bytes`) with zero ceremony — required by FR-002. First-class `async` support means the blocking LLM call is awaited cleanly. Native Pydantic v2 integration makes `pydantic-settings` fit naturally into the dependency model. The catch-all route pattern (`/{full_path:path}`) is supported directly. Dominant choice for this pattern in 2025.

**Alternatives considered**:
- Starlette: FastAPI is built on Starlette; using it directly means re-implementing FastAPI's conveniences with no benefit at this scale
- Flask: Synchronous by default, weaker Pydantic integration, heavier boilerplate for raw body access — wrong fit for an async LLM-calling service

---

## 3. Structured Logging

**Decision**: `structlog` with `JSONRenderer` output processor

**Rationale**: Mature, production-grade structured logging for Python. Integrates with stdlib `logging` (captures third-party library output). Supports bound loggers — attach `request_id`, `method`, `path` once at request entry and every subsequent log line in that request context carries them automatically. Approximately 10 lines to configure a working JSON pipeline. Maps directly to FR-009's startup/per-request/event log requirements.

**Alternatives considered**:
- stdlib `logging` + `python-json-logger`: Works but verbose per-logger setup; no bound context propagation
- `loguru`: Better ergonomics for scripts; JSON output requires a custom serializer; stdlib interception is non-obvious for a service context

---

## 4. Tool Testing Isolation Pattern

**Decision**: Instantiate `BaseTool` subclass directly; call `tool.invoke({"arg": "value"})` in plain pytest; no LLM or agent involved

**Rationale**: LangChain `BaseTool` subclasses are plain Python objects. The isolation pattern: construct the tool, call `.invoke()` with a dict matching the tool's `args_schema`, assert on the return value. Test `ToolException` for error cases. For function-based (`@tool` decorator) tools, call the decorated function directly. This satisfies the constitution's mandate: tool contracts tested before agent wiring, with no LLM mock required.

**Alternatives considered**:
- Asserting agent calls the tool (via LLM mock): Tests wiring, not contract — wrong layer
- Full `AgentExecutor`/LangGraph invoke with mocked LLM in tool tests: Couples tool tests to agent architecture, violates isolation

---

## 5. pydantic-settings Startup Validation

**Decision**: `BaseSettings` subclass with required fields as bare type annotations (no default); instantiated at module level in `settings.py`; `ValidationError` caught at entry point and re-raised as `SystemExit` with formatted message

**Rationale**: `pydantic-settings` raises `ValidationError` at instantiation if any required field is absent or invalid. Instantiating at module level means the error surfaces at import time (startup). The entry point wraps the import in `try/except ValidationError`, calls `sys.exit(1)` with `error.errors()` output. Satisfies FR-007 (all config in BaseSettings), FR-008 (startup failure on missing values), and SC-003 (never starts misconfigured).

**Alternatives considered**:
- Lazy instantiation inside request handlers: Service appears healthy, crashes on first request — unacceptable
- Manual `os.environ` checks: Duplicates what `pydantic-settings` does; no type coercion; violates "all config in BaseSettings" rule
- `python-decouple` / raw `dotenv`: More boilerplate, no Pydantic integration
