# Research: Cosmetic Features

All Technical Context items were resolvable from the existing codebase and installed versions (`langchain-core` 1.6.10, `langgraph` 1.2.0, `langgraph-prebuilt` 1.1.0, `pydantic` 2.13). No NEEDS CLARIFICATION remained.

## R1. Where personality resolution lives

- **Decision**: New module `src/config/personality.py` with `resolve_personality(settings) -> PersonalitySource` and `available_presets(directory) -> list[str]`. `create_app`'s lifespan calls it and passes the resolved path to `load_harness`, which keeps its current signature and missing-file check.
- **Rationale**: Resolution is configuration logic (inputs: two settings + a directory), unit-testable without the agent. `load_harness` already validates the path; keeping its signature means the existing tests that pass a path keep working.
- **Alternatives considered**: A pydantic `model_validator` on `Settings` (would touch the filesystem during settings construction and break the many tests that build `Settings` without a presets dir); resolving inside `load_harness` (mixes two responsibilities and changes its signature).

## R2. Settings shape for personality

- **Decision**: `personality: str = "default"`; `personality_path: str = ""` (was `"config/personality.md"`). Empty or whitespace `PERSONALITY_PATH` means unset. Name normalized with `.strip().lower()`. Names containing `/`, `\` or `..`, or not matching an available preset, exit via `print(..., file=sys.stderr)` + `sys.exit(1)`, the existing startup-failure convention.
- **Rationale**: Matches FR-002–FR-005. The presets directory is a module constant `PRESETS_DIR = Path("config/personalities")`, overridable in tests via a function argument, not a setting (YAGNI, spec assumption).
- **Alternatives considered**: `Literal[...]` for preset names (breaks FR-006: adding a file must not need code); a `PERSONALITIES_DIR` setting (not requested).

## R3. KV store design and concurrency

- **Decision**: `src/state/kv_store.py` with class `KVStore(max_value_bytes, max_keys, state_file: Path | None)` holding a `dict[str, JSONValue]` behind a `threading.Lock`. Methods: `set`, `get`, `list`, `delete`. Each mutation runs under the lock: validate → apply → save (if file) → on save failure, revert and raise.
- **Rationale**: LangGraph's `ToolNode` runs sync `_run` tools via `run_in_executor`, so concurrent requests mutate from different threads; a `threading.Lock` is correct for both sync and async callers. Revert-on-failure keeps the "store unchanged" guarantee. One process only (spec assumption).
- **Alternatives considered**: `asyncio.Lock` (does not protect thread-pool callers); SQLite (`sqlite3` is stdlib but adds schema and is more than a JSON file needs); LangGraph checkpointer/`InMemoryStore` (conversation-oriented, no size limits, no JSON-file persistence, harder to cap).

## R4. Atomic JSON persistence

- **Decision**: Serialize the whole map with `json.dumps(data, ensure_ascii=False)`, write to a temp file created with `tempfile.mkstemp(dir=state_file.parent, prefix=".<name>.", suffix=".tmp")`, `flush` + `os.fsync`, then `os.replace(tmp, state_file)`. Delete the temp file on any failure. Load at startup: missing file → empty; unreadable/invalid JSON/not an object/non-string keys → print error naming the file and `sys.exit(1)`, without modifying the file.
- **Rationale**: `os.replace` is atomic on POSIX and Windows when source and target are on the same filesystem (guaranteed by using the same directory). Whole-file rewrite is fine at the default cap (1000 keys × 64 KiB worst case ≈ 64 MiB; typical demo data is a few KB).
- **Alternatives considered**: Append-only log (needs compaction); writing in place (not atomic); `fsync` of the directory after replace (extra durability against power loss, unnecessary for a demo backend).

## R5. Value size and key rules

- **Decision**: Size = `len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))`. Keys: `str`, `1 <= len <= 256`. Defaults `KV_MAX_VALUE_BYTES=65536`, `KV_MAX_KEYS=1000`, both validated `> 0` with the existing `must_be_positive` validator. On load, a file exceeding current limits is accepted with a `kv_state_over_limit` warning log.
- **Rationale**: Compact UTF-8 JSON is the spec's stated measure and is what the file actually stores. Max key length is a constant (not configurable), as in the spec.
- **Alternatives considered**: `sys.getsizeof` (measures Python object overhead, not data).

## R6. How tool errors reach the agent

- **Decision**: KV tools are `BaseTool` subclasses with `handle_tool_error=True`; limit and key violations raise `ToolException` inside `_run`, which `BaseTool` turns into a `ToolMessage` with `status="error"` and the message text. Normal "not found" outcomes are returned as data (`{"found": false, ...}`), not errors.
- **Rationale**: In `langgraph-prebuilt` 1.1.0 the `ToolNode` default handler (`_default_handle_tool_errors`) only converts `ToolInvocationError` (bad arguments) and re-raises everything else, so a plain `ToolException` would abort the run with a 500 — violating FR-014. Verified: `ReadFileTool().invoke({"path": "nope"})` raises, `ReadFileTool(handle_tool_error=True)` returns `'File not found: nope'`.
- **Alternatives considered**: Passing `handle_tool_errors=True` to a custom `ToolNode` (changes behavior for all existing tools, out of scope); returning error dicts instead of raising (loses the `status="error"` signal to the model).
- **Note (out of scope)**: the existing file tools (`read_file`, `stat_file`, `respond_with_file`) have the same latent issue — a missing file aborts the request with 500. Recorded here; not fixed by this feature.

## R7. Tool registration with configured state

- **Decision**: `src/agent/registry.py` gains `build_tools(store: KVStore) -> list[BaseTool]` returning the existing tools plus `KVSetTool(store=store)`, `KVGetTool(...)`, `KVListTool(...)`, `KVDeleteTool(...)`. `TOOLS` stays as the store-less list for existing imports. `load_harness(personality_path, llm=None, store=None)` builds an in-memory `KVStore` from settings when `store` is not given, and passes `build_tools(store)` to `create_react_agent`. `create_app`'s lifespan builds the store from settings (`STATE_FILE`, limits) so a bad state file fails startup.
- **Rationale**: Tools need a store instance configured at startup; module-level singletons would make tests share state. Passing the store in keeps each test's app isolated.
- **Alternatives considered**: A global store in `kv_store.py` configured by `configure()` (hidden coupling, test leakage).

## R8. JSON-compatible value in the tool schema

- **Decision**: `value: str | int | float | bool | list | dict | None` in the `kv_set` args model.
- **Rationale**: Produces an explicit `anyOf` JSON schema that all three providers accept; `Any` yields an untyped property some providers handle poorly.
- **Alternatives considered**: Accept only strings and let the agent serialize (loses type preservation, FR-013).

## R9. Counting tokens and steps per request

- **Decision**: A per-request `UsageTracker` in `src/agent/usage.py`, subclassing `BaseCallbackHandler` with `run_inline = True`. `on_llm_end` reads each generation's `message.usage_metadata` (`input_tokens`, `output_tokens`, missing → 0) and adds `len(message.tool_calls)` to `steps`. `invoke_agent(agent, incoming, timeout, usage=None)` passes it via `config={"callbacks": [usage], ...}`.
- **Rationale**: Callbacks fire as each LLM call completes, so totals are known even when the run later times out, hits the step limit or the provider fails (spec scenario 8.6) — information the final `messages` list does not provide in those cases. A new instance per request isolates concurrent requests (8.8). `run_inline` keeps updates on the event loop thread, no lock needed. Counting `tool_calls` on the model's output counts every tool call the model made, including the final `respond` and calls whose arguments fail validation. Verified with `ToolCapableFakeLLM` emitting two messages with usage 100/20 and 150/30: tracker reports 250 / 50 / 2.
- **Alternatives considered**: Summing `usage_metadata` from `result["messages"]` (no data on timeout/loop/provider error); `on_tool_start` counting (misses tool calls rejected before the tool starts); LangChain's `UsageMetadataCallbackHandler` (keyed by model name, no step count; would still need a wrapper).

## R10. Attaching usage to success and error responses

- **Decision**: The catch-all route creates the tracker and stores it on `request.state.usage` before calling `invoke_agent`. A helper `apply_usage(request, response)` in `src/api/usage_headers.py` (a) removes any agent-set header whose lowercase name is one of the four `x-dopamine-*` usage names, (b) sets the system values, (c) computes cost when configured. The success path and the agent-failure handlers (`AgentNoResponseError`, `AgentTimeoutError`, `AgentLoopLimitError`, `LLMUnavailableError`, and the generic 500 handler when `request.state.usage` exists) call it. Guard rejections (413/401/429) happen before the tracker exists, so they get no usage headers.
- **Rationale**: `request.state` is the FastAPI-native way to share per-request data with exception handlers; one helper keeps header logic in one place.
- **Alternatives considered**: Catching agent errors in the route and building error responses there (duplicates `errors.py`); middleware (would also see guard rejections and `/health`, requiring exclusions).

## R11. Request log fields

- **Decision**: The `request` log event gains `tokens_in`, `tokens_out`, `steps` and, when prices are set, `cost_usd`. It is emitted on the success path (as today) and also by `apply_usage` on agent-failure paths, with the failure status.
- **Rationale**: FR-027 requires the numbers in the request log for every agent-handled request; today failures are not logged as `request` at all.

## R12. Cost computation

- **Decision**: Settings `llm_price_input_per_mtok: float | None = None`, `llm_price_output_per_mtok: float | None = None`. A `model_validator` requires both or neither and each `>= 0`. Cost computed with `decimal.Decimal(str(price))`, `tokens × price / 1_000_000`, quantized to `Decimal("0.000001")` with `ROUND_HALF_UP`, formatted as a plain string (e.g. `0.001500`).
- **Rationale**: Decimal avoids float artefacts at the 6th decimal (SC-009). No price table in code (FR-026).
- **Alternatives considered**: Per-model price map (explicitly rejected by the user: goes stale).

## R13. CORS exposure

- **Decision**: Add `expose_headers=["X-Dopamine-Tokens-In", "X-Dopamine-Tokens-Out", "X-Dopamine-Steps", "X-Dopamine-Cost-USD"]` to the existing `CORSMiddleware`.
- **Rationale**: Browsers hide non-safelisted response headers from cross-origin JS unless exposed (FR-028). The `website` preset makes browser clients realistic.

## R14. Preset content guidelines

- **Decision**: Each preset is 15–40 lines of English Markdown: a one-line identity, character/tone, the shape of its replies (status codes, content type, body style) phrased as preferences, a few concrete examples of tone, and no mention of tool names or instructions to output bare text. `shop` and `sarcastic` are told to keep their data consistent across requests (which the programmatic instructions map to the storage tools). `website` asks for complete HTML documents with `text/html`. `teapot` always prefers 418 with a philosophical body.
- **Rationale**: FR-008/FR-009 and constitution II ("character/tone only"). A structural test asserts every preset is non-empty and contains none of the forbidden phrases (e.g. "do not call respond", "reply in plain text without", "ignore previous instructions").
