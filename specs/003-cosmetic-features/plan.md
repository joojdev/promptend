# Implementation Plan: Cosmetic Features

**Branch**: `003-cosmetic-features` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-cosmetic-features/spec.md`

## Summary

Three independent slices on the existing FastAPI + LangGraph harness:

1. **Personality presets (A)**: ship five Markdown presets in `config/personalities/`. A new resolver turns `PERSONALITY` (default `default`) into a file path, unless `PERSONALITY_PATH` is set. Unknown or unsafe names exit at startup listing the presets. `config/personality.md` moves to `default.md`.
2. **Agent state (B)**: a thread-safe `KVStore`, in memory or mirrored to `STATE_FILE` with atomic temp-file + `os.replace` writes, bounded by `KV_MAX_VALUE_BYTES` / `KV_MAX_KEYS`. Four tools (`kv_set`, `kv_get`, `kv_list`, `kv_delete`) with `handle_tool_error=True`, built per app by `build_tools(store)`. `PROGRAMMATIC_INSTRUCTIONS` gains a Storage section.
3. **Usage reporting (C)**: a per-request `UsageTracker` callback sums `usage_metadata` and counts tool calls as each LLM call ends, so totals exist even on timeout or failure. One helper writes `X-Dopamine-Tokens-In/-Out/-Steps` (+ `-Cost-USD` when both prices are set) on success and agent-failure responses, overrides agent-set copies, and logs the same numbers. Headers are CORS-exposed.

Constitution amended to v1.2.0 (presets allowed, bounded storage tools allowed, response metadata allowed) before design.

## Technical Context

**Language/Version**: Python 3.11+ (venv runs 3.14)

**Primary Dependencies**: existing only — `fastapi`, `langgraph` 1.2 / `langgraph-prebuilt` 1.1 (`create_react_agent`), `langchain-core` 1.6 (`BaseTool`, `ToolException`, `BaseCallbackHandler`), `pydantic-settings`, `structlog`. Stdlib: `json`, `os`, `tempfile`, `threading`, `decimal`, `pathlib`. No new packages.

**Storage**: In-process dict; optional single JSON file (`STATE_FILE`) rewritten atomically per mutation.

**Testing**: `pytest` + `pytest-asyncio`, `fastapi.testclient.TestClient`, `tests/conftest.py` fakes (`ToolCapableFakeLLM` emitting `AIMessage`s with `tool_calls` and `usage_metadata`; existing `SlowFakeLLM` / `RaisingFakeLLM` for failure paths). `tmp_path` for presets dirs and state files; `monkeypatch` on `os.replace` to simulate interrupted saves.

**Target Platform**: Linux server, single process.

**Project Type**: Web service (existing).

**Performance Goals**: Storage ops O(1) except `kv_list` O(n log n) on ≤ `KV_MAX_KEYS`; whole-file save per mutation acceptable at demo scale. Usage tracking adds a few integer adds per LLM call.

**Constraints**: No hardcoded price table. Storage errors and limit violations must never abort a request. Usage headers must not change the agent's status/body. Guard rejections stay agent-free and header-free.

**Scale/Scope**: One process, small data (default caps 1000 keys × 64 KiB).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v1.2.0** (amended in this plan; see Sync Impact Report in `.specify/memory/constitution.md`). Under v1.1.0 Part A violated Principle II ("No pre-defined personality presets") and Part B violated the "No long-term memory" standard; the amendment resolves both.

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Agent-as-Harness: every request through the agent | ✅ PASS | No new bypass. Usage headers annotate agent-run responses only, never change status/body (v1.2.0 "Response metadata"). Guards unchanged. |
| I. Tools are the only extension point | ✅ PASS | State is added as four registered tools; route logic only measures and annotates. |
| II. Customizable Personality | ✅ PASS (v1.2.0) | Presets in `config/personalities/`, `PERSONALITY_PATH` override, startup failure on missing file or unknown preset, discovery by file. Presets are tone-only; a test rejects bypass wording. |
| II. Instructions separate from personality | ✅ PASS | Storage guidance goes into `PROGRAMMATIC_INSTRUCTIONS`, not presets. |
| III. Test-First | ✅ PASS | Tasks will put failing tests first; each KV tool's contract is tested directly before registration. |
| IV. Simplicity / YAGNI | ✅ PASS | Dict + lock + JSON file instead of a DB; one callback class instead of a metrics library; no configurable presets dir; no price table. |
| Config: `BaseSettings`, `.env`, ruff, Python 3.11+ | ✅ PASS | Seven settings added/changed in `Settings`, documented in `.env.example`. |
| Config: no conversation memory; bounded storage tools only | ✅ PASS (v1.2.0) | `checkpointer=None` kept; storage has value-size and key-count caps. |

**Post-Design Re-check**: ✅ All gates pass under v1.2.0. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-cosmetic-features/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── configuration.md
│   ├── kv-tools.md
│   └── usage-headers.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
config/
├── personality.md       # DELETED (content → personalities/default.md)
└── personalities/       # NEW
    ├── default.md
    ├── shop.md
    ├── sarcastic.md
    ├── website.md
    └── teapot.md

src/
├── agent/
│   ├── harness.py       # Storage section in PROGRAMMATIC_INSTRUCTIONS; load_harness(path, llm, store, preset);
│   │                    #   invoke_agent(..., usage=None) passes callbacks
│   ├── registry.py      # + build_tools(store); TOOLS kept
│   └── usage.py         # NEW: UsageTracker callback + cost_usd
├── api/
│   ├── app.py           # lifespan: resolve_personality + KVStore.from_settings; route: tracker on request.state,
│   │                    #   apply_usage on success; CORS expose_headers
│   ├── errors.py        # agent-failure + generic handlers call apply_usage when request.state.usage exists
│   └── usage_headers.py # NEW: apply_usage(request, response, settings) — override, headers, log
├── config/
│   ├── settings.py      # + personality, state_file, kv_max_*, llm_price_*; personality_path default ""
│   └── personality.py   # NEW: available_presets, resolve_personality, PersonalitySource
├── state/               # NEW package
│   ├── __init__.py
│   └── kv_store.py      # KVStore, KVError, atomic save, load/validate
└── tools/
    └── kv.py            # NEW: KVSetTool, KVGetTool, KVListTool, KVDeleteTool

tests/
├── conftest.py          # helper to build AIMessage with tool_calls + usage_metadata
├── unit/
│   ├── test_personality.py   # resolution + errors + shipped preset checks
│   ├── test_kv_store.py      # store contract, limits, persistence, atomic save, bad file
│   ├── tools/test_kv_tools.py
│   ├── test_usage.py         # tracker sums, steps, missing usage, cost rounding
│   └── test_startup.py       # + new settings defaults/validation
└── integration/
    ├── test_kv_http.py       # kv_set in request 1, kv_get in request 2 (fake LLM)
    ├── test_usage_http.py    # headers, override, failures, guards, log, CORS
    └── test_personality_http.py  # app with PERSONALITY=shop → system prompt starts with preset

.env.example                              # document new settings
specs/001-project-boilerplate/quickstart.md   # personality section → presets
```

**Structure Decision**: Single-project layout kept. Three new modules each hold one slice's pure logic (`config/personality.py`, `state/kv_store.py`, `agent/usage.py`) so they are unit-testable without the app; `tools/kv.py` and `api/usage_headers.py` are thin adapters. Existing tests that pass `PERSONALITY_PATH` keep working unchanged.

## Complexity Tracking

No violations. The Principle II and storage conflicts were resolved by the v1.2.0 constitution amendment, not by exception.
