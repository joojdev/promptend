---

description: "Task list for Cosmetic Features"
---

# Tasks: Cosmetic Features

**Input**: Design documents from `specs/003-cosmetic-features/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/configuration.md, contracts/kv-tools.md, contracts/usage-headers.md

**Tests**: REQUIRED. The spec (FR-030) lists the required automated tests and the constitution (Principle III) mandates test-first. Within each story, write the tests first and confirm they FAIL before implementing. No test calls a real LLM; use the fakes in `tests/conftest.py`.

**Organization**: Grouped by user story, phases in priority order (P1: US1, US2, US5 → P2: US3, US4, US6, US7, US8 → P3: US9). The three parts are independent of each other: Part A = US1–US4, Part B = US5–US7, Part C = US8–US9. Inside a part, later stories build on earlier ones (US2/US3 extend the US1 resolver; US6/US7 extend the US5 store; US9 extends US8).

**Shared files** (do not edit concurrently): `src/config/settings.py` (Phase 2 only), `src/agent/harness.py` (US1, US5, US8), `src/api/app.py` (US1, US5, US8), `src/api/errors.py` (US8), `tests/conftest.py` (Phase 2 only).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 … US9 (spec.md user stories)

---

## Phase 1: Setup

**Purpose**: Confirm the baseline and create empty packages.

- [X] T001 Run `uv sync --extra dev`, `uv run pytest` and `uv run ruff check src tests` from repo root; record that the baseline is green (fix nothing here; if red, stop and report)
- [X] T002 [P] Create package `src/state/` with an empty `src/state/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Settings and test helpers shared by all parts.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add unit tests in `tests/unit/test_startup.py` for the new settings (see contracts/configuration.md): defaults `personality == "default"`, `personality_path == ""`, `state_file == ""`, `kv_max_value_bytes == 65536`, `kv_max_keys == 1000`, both prices `None`; env overrides for each; `kv_max_value_bytes` / `kv_max_keys` of `0` and `-1` rejected; only one price set rejected (both directions); negative price rejected; both prices `0` accepted. Clear the new env vars with `monkeypatch.delenv` like `test_hardening_setting_defaults`. Confirm they FAIL before T004
- [X] T004 Add fields to `src/config/settings.py` per data-model.md: `personality: str = "default"`, change `personality_path` default to `""`, `state_file: str = ""`, `kv_max_value_bytes: int = 65536`, `kv_max_keys: int = 1000` (add both to the existing `must_be_positive` validator), `llm_price_input_per_mtok: float | None = None`, `llm_price_output_per_mtok: float | None = None`, and a `model_validator(mode="after")` requiring both prices or neither and each `>= 0` with messages naming the env vars
- [X] T005 [P] Add a helper to `tests/conftest.py`: `def ai_tool_call(name: str, args: dict, *, tokens_in: int = 0, tokens_out: int = 0, call_id: str | None = None) -> AIMessage` returning an `AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id or <unique>}], usage_metadata={"input_tokens": tokens_in, "output_tokens": tokens_out, "total_tokens": tokens_in + tokens_out})`; and `def make_queued_llm(*messages) -> CountingFakeLLM` that returns a fresh `CountingFakeLLM(responses=[""])` with `queued_messages=list(messages)`, `calls=0`, `prompts=[]` (fresh lists per instance)
- [X] T006 [P] Document the seven settings in `.env.example` with one-line comments: `# PERSONALITY=default` (list the presets: default, shop, sarcastic, website, teapot), `# PERSONALITY_PATH=` (custom file, wins over PERSONALITY), `# STATE_FILE=` (unset = in-memory), `KV_MAX_VALUE_BYTES=65536`, `KV_MAX_KEYS=1000`, `# LLM_PRICE_INPUT_PER_MTOK=` and `# LLM_PRICE_OUTPUT_PER_MTOK=` (USD per 1M tokens, set both to get X-Dopamine-Cost-USD; no defaults shipped)

**Checkpoint**: Settings and helpers ready; existing suite still green (`uv run pytest`). Existing tests set `PERSONALITY_PATH`, so the changed default does not affect them.

---

## Phase 3: User Story 1 - Pick a ready-made personality by name (Priority: P1) 🎯 MVP

**Goal**: `PERSONALITY=<name>` (default `default`) selects `config/personalities/<name>.md`, normalized, logged at startup.

**Independent Test**: With a fake LLM and `PERSONALITY=shop`, the system prompt the model receives starts with the shop preset content followed by the programmatic instructions.

### Tests for User Story 1 (write first, confirm FAIL)

- [X] T007 [P] [US1] Unit tests in `tests/unit/test_personality.py` for `resolve_personality(settings, presets_dir=tmp_dir)` using a `tmp_path` presets dir with `default.md` and `shop.md`: unset `PERSONALITY` → `PersonalitySource(path=<dir>/default.md, preset="default")`; `personality="shop"` → shop; `"Shop"` and `" shop "` → shop; `available_presets(dir)` returns sorted stems of `*.md` only (ignores `.gitkeep`, `notes.txt`, subdirectories)
- [X] T008 [P] [US1] Integration test in `tests/integration/test_personality_http.py`: set env `LLM_API_KEY`, `LLM_MODEL`, `PERSONALITY=shop`, delete `PERSONALITY_PATH`; build the app with `make_queued_llm(ai_tool_call("respond", {"body": "ok"}))` via `create_app(llm=...)` inside `TestClient`; send one request; assert `llm.prompts[0]` starts with the stripped content of `config/personalities/shop.md` and contains `## Role & Context`. Also assert the `harness_startup` log (use `structlog.testing.capture_logs`) has `personality_preset == "shop"` and `personality_path` ending in `config/personalities/shop.md`

### Implementation for User Story 1

- [X] T009 [US1] Move `config/personality.md` to `config/personalities/default.md` with `git mv`, keeping its neutral helpful-assistant content (FR-010). Create minimal placeholder files `config/personalities/shop.md`, `sarcastic.md`, `website.md`, `teapot.md` containing one identity line each (full content in US4) so resolution and tests work
- [X] T010 [US1] Create `src/config/personality.py` per data-model.md: `PRESETS_DIR = Path("config/personalities")`; frozen dataclass `PersonalitySource(path: Path, preset: str | None)`; `available_presets(directory: Path = PRESETS_DIR) -> list[str]` (sorted stems of regular `*.md` files, `[]` if the directory is missing); `resolve_personality(settings, presets_dir: Path = PRESETS_DIR) -> PersonalitySource` implementing rules 2 and 5 (normalize, return preset path). Leave clear hook points for rule 1 (US2) and rules 3–4 (US3); for now an unknown name may raise `SystemExit(1)` without a message
- [X] T011 [US1] In `src/agent/harness.py` `load_harness`, add keyword `personality_preset: str | None = None` and include `personality_preset=personality_preset` in the `harness_startup` log; when the personality file is empty, also log `personality_empty` at warning level. Keep the existing missing-file check and signature order
- [X] T012 [US1] In `src/api/app.py` lifespan, call `source = resolve_personality(settings)` and pass `str(source.path)` and `personality_preset=source.preset` to `load_harness`
- [X] T013 [US1] Update `tests/unit/test_startup.py::test_missing_personality_file_raises_system_exit` only if needed so it still passes (it calls `load_harness` with a path, which is unchanged); run the full suite

**Checkpoint**: `PERSONALITY` selects presets; default works with no settings.

---

## Phase 4: User Story 2 - A custom personality file still wins (Priority: P1)

**Goal**: Non-empty `PERSONALITY_PATH` overrides `PERSONALITY`; missing file still fails startup.

**Independent Test**: `PERSONALITY=teapot` + `PERSONALITY_PATH=<tmp file>` → tmp file content is the prompt.

### Tests for User Story 2 (write first, confirm FAIL)

- [X] T014 [P] [US2] Add to `tests/unit/test_personality.py`: `personality_path=str(tmp_file)` + `personality="teapot"` → `PersonalitySource(path=Path(tmp_file), preset=None)`; `personality_path="   "` → treated as unset (default preset); `personality_path` pointing to a missing file → resolver returns that path (no exit) and `load_harness(str(path))` raises `SystemExit` (existing message `personality file not found`)
- [X] T015 [P] [US2] Add to `tests/integration/test_personality_http.py`: env `PERSONALITY=teapot` and `PERSONALITY_PATH=<tmp file "Custom persona.">`; assert `llm.prompts[0]` starts with `Custom persona.` and the startup log has `personality_preset is None`

### Implementation for User Story 2

- [X] T016 [US2] Implement rule 1 in `src/config/personality.py::resolve_personality`: `if settings.personality_path.strip(): return PersonalitySource(path=Path(settings.personality_path.strip()), preset=None)` before any preset logic

**Checkpoint**: Existing integration tests (which set `PERSONALITY_PATH`) and the new ones pass.

---

## Phase 5: User Story 5 - The fake backend remembers what you created (Priority: P1)

**Goal**: Shared in-memory KV store with four agent tools, registered per app, explained in the programmatic instructions.

**Independent Test**: Fake LLM does `kv_set` in request 1 and `kv_get` in request 2; request 2's response contains the stored value. Each tool is tested directly.

### Tests for User Story 5 (write first, confirm FAIL)

- [X] T017 [P] [US5] Unit tests in `tests/unit/test_kv_store.py` for `KVStore(max_value_bytes=65536, max_keys=1000, state_file=None)` per contracts/kv-tools.md: `set` new → `{"ok": True, "key": k, "created": True}`, overwrite → `created False`; `get` present/missing; values of every JSON type (str, int, float, bool, None, list, dict) round-trip with type preserved; `list("users/")` sorted and filtered, `list("")` all keys; `delete` present → `deleted True` then `get` not found, missing → `deleted False`; invalid keys (`""`, 257 chars, non-str) raise `KVError` for `set`/`get`/`delete` and leave the store unchanged; 20 threads × 50 `set`s on distinct keys end with exactly 1000 keys (no lost updates)
- [X] T018 [P] [US5] Unit tests in `tests/unit/tools/test_kv_tools.py`: build the four tools on one store; `invoke` each with dict args and `json.loads` the string result to compare with the contract; a `KVError` path (e.g. `kv_get` with `""`) returns the error text instead of raising (because `handle_tool_error=True`); tool `name`s are exactly `kv_set`, `kv_get`, `kv_list`, `kv_delete`; `kv_set`'s args schema accepts an object, a list, a number and `null` as `value`
- [X] T019 [P] [US5] Unit test in `tests/unit/test_harness.py`: `build_tools(store)` contains the existing five tool names plus the four kv names; `PROGRAMMATIC_INSTRUCTIONS` contains a `## Storage` section mentioning `kv_set`, `kv_get`, `kv_list`, `kv_delete` and `<collection>/<id>`
- [X] T020 [P] [US5] Integration test in `tests/integration/test_kv_http.py`: env with `PERSONALITY_PATH` to a tmp persona and no `STATE_FILE`; `make_queued_llm(ai_tool_call("kv_set", {"key": "users/1", "value": {"name": "Ana"}}), ai_tool_call("respond", {"body": {"created": True}, "status_code": 201}), ai_tool_call("kv_get", {"key": "users/1"}), <respond step>)`. For the 4th message the fake cannot see tool output, so assert instead on the model's input: after request 2, `llm.prompts[-1]` (the prompt of the call that follows `kv_get`) contains `"name": "Ana"`. Request 1 → 201; request 2 → 200. Also assert two separate `create_app` instances do not share data (new app, `kv_get` → `"found": false` in the prompt)

### Implementation for User Story 5

- [X] T021 [US5] Create `src/state/kv_store.py`: `JSONValue` alias, `class KVError(Exception)`, `MAX_KEY_LENGTH = 256`, `class KVStore` with `__init__(self, max_value_bytes: int, max_keys: int, state_file: Path | None = None, data: dict | None = None)`, a `threading.Lock`, and methods `set`, `get`, `list`, `delete` returning the dicts in contracts/kv-tools.md; key validation per data-model.md. Limits and persistence are added in US7/US6 — for now `set` stores without checking size/count and nothing is written to disk
- [X] T022 [US5] Create `src/tools/kv.py` with `KVSetTool`, `KVGetTool`, `KVListTool`, `KVDeleteTool` (`BaseTool`, field `store: KVStore`, `handle_tool_error: bool = True`, pydantic args models per data-model.md with `value: str | int | float | bool | list | dict | None`). Each `_run` calls the store, converts `KVError` to `ToolException(str(exc))`, returns `json.dumps(result, ensure_ascii=False)`. Descriptions say what each tool does in one or two sentences (shared across requests; key shape `<collection>/<id>`)
- [X] T023 [US5] In `src/agent/registry.py` add `build_tools(store: KVStore) -> list[BaseTool]` returning fresh instances of the five existing tools plus the four kv tools bound to `store`; keep `TOOLS` unchanged
- [X] T024 [US5] In `src/agent/harness.py`: add the `## Storage` section to `PROGRAMMATIC_INSTRUCTIONS` with the six bullets from contracts/kv-tools.md ("Programmatic instructions"), placed after the respond/respond_with_file section; change `load_harness` to accept `store: KVStore | None = None` (when `None`, build `KVStore(settings.kv_max_value_bytes, settings.kv_max_keys)`), pass `build_tools(store)` instead of `TOOLS` to `create_react_agent`, and add `kv_keys=len(store.list()["keys"])` to the startup log
- [X] T025 [US5] In `src/api/app.py` lifespan, create the store (`KVStore(settings.kv_max_value_bytes, settings.kv_max_keys)` for now; US6 switches to `KVStore.from_settings`) and pass it to `load_harness`

**Checkpoint**: Request 1 writes, request 2 reads, in memory. Part B MVP.

---

## Phase 6: User Story 3 - A typo in the preset name fails loudly and helpfully (Priority: P2)

**Goal**: Unknown or unsafe preset names and an empty presets dir fail startup with a clear message.

**Independent Test**: `PERSONALITY=nope` → `SystemExit(1)` and stderr lists every preset.

### Tests for User Story 3 (write first, confirm FAIL)

- [X] T026 [P] [US3] Add to `tests/unit/test_personality.py` (use `capsys`): `personality="nope"` → `SystemExit` with code 1 and stderr containing `unknown personality preset 'nope'` and `Available presets: default, shop` (sorted, comma-separated); `"../secrets"`, `"a/b"`, `"a\\b"`, `".."` → same failure even if a matching file exists outside the dir (create `tmp/secrets.md` next to the presets dir to prove it is not read); empty dir and missing dir → `SystemExit(1)` with `no personality presets found in <dir>`

### Implementation for User Story 3

- [X] T027 [US3] Implement rules 3–4 in `src/config/personality.py::resolve_personality` with the exact messages from contracts/configuration.md, printed to `sys.stderr` followed by `sys.exit(1)`; check for `/`, `\` and `..` before the membership test

**Checkpoint**: All preset error paths covered.

---

## Phase 7: User Story 4 - Presets are funny and stay inside the rules (Priority: P2)

**Goal**: Five real presets with distinct characters that never contradict the programmatic instructions.

**Independent Test**: Structural test over every shipped preset; tone is checked manually at the end.

### Tests for User Story 4 (write first, confirm FAIL)

- [X] T028 [P] [US4] Add to `tests/unit/test_personality.py`: `available_presets()` on the real `config/personalities/` includes `default`, `shop`, `sarcastic`, `website`, `teapot`; every preset file is non-empty after strip, has at least 10 lines except `default`, and contains none of these case-insensitive phrases: `without calling`, `plain text reply`, `bare text`, `ignore previous`, `ignore the instructions`, `do not use respond`, `don't use respond`, `respond(`, `respond_with_file`, `kv_` (presets must not name tools)

### Implementation for User Story 4

- [X] T029 [P] [US4] Write `config/personalities/shop.md` (research R14): online store "selling" absurd invented products (name, description, price with currency, stock count); REST-consistent JSON (collections as arrays, item lookup by id, 201 on create with the created resource, 404 for unknown ids, 409 when out of stock); keeps catalog and orders consistent across requests; cheerful upselling tone in descriptions only, never in field names
- [X] T030 [P] [US4] Write `config/personalities/sarcastic.md`: data and status codes always correct and REST-like; every human-readable `message` field passive-aggressive (sighs, "as documented", "again"); never refuses valid requests; 4xx messages blame the caller politely-but-not-really
- [X] T031 [P] [US4] Write `config/personalities/website.md`: every path is a page of an imaginary website; replies are complete HTML5 documents (`<!doctype html>`, `<head>` with title and inline CSS, navigation linking to other invented paths) with content type `text/html`; non-GET methods get an HTML page too (form results); 404 pages are themed
- [X] T032 [P] [US4] Write `config/personalities/teapot.md`: answers 418 I'm a teapot to everything, in JSON with a short philosophical justification tied to the request (method/path/body), quoting invented philosophers; occasionally suggests tea; never actually performs the request
- [X] T033 [P] [US4] Review `config/personalities/default.md`: neutral, helpful API; keep it short and tone-only (no tool names)

**Checkpoint**: Part A complete.

---

## Phase 8: User Story 6 - State survives a restart when the operator wants it to (Priority: P2)

**Goal**: Optional `STATE_FILE` persistence with atomic saves and strict loading.

**Independent Test**: Write via one store/app, read via a second one on the same file; simulate an interrupted save.

### Tests for User Story 6 (write first, confirm FAIL)

- [X] T034 [P] [US6] Add to `tests/unit/test_kv_store.py` using `tmp_path`: `state_file` unset → no file created after `set`; missing file → `KVStore.from_settings` starts empty and the file appears after the first `set` containing a JSON object; `set` then a new store from the same file → value readable (all JSON types preserved); `delete` persisted; monkeypatch `os.replace` in `src.state.kv_store` to raise `OSError` → `set` raises `KVError("storage write failed")`, the in-memory store is unchanged, the on-disk file still holds the previous complete state, and no `*.tmp` file is left in the directory; invalid file contents (`not json`, `[]`, `"x"`) → `SystemExit(1)` with stderr `invalid state file <path>` and file bytes unchanged; file holding more keys than `max_keys` loads with a `kv_state_over_limit` warning (use `structlog.testing.capture_logs`)
- [X] T035 [P] [US6] Add to `tests/integration/test_kv_http.py`: with `STATE_FILE=<tmp>/state.json`, app 1 runs a `kv_set` request; a second `create_app` (new `TestClient`) runs a `kv_get` request; assert the follow-up prompt contains the stored value

### Implementation for User Story 6

- [X] T036 [US6] In `src/state/kv_store.py` add `KVStore.from_settings(settings) -> KVStore` (load and validate per research R4 / data-model.md, exit 1 with the contract message on invalid file, warn `kv_state_over_limit` when over limits) and a private `_save()` (temp file in the same dir via `tempfile.mkstemp`, `json.dump(..., ensure_ascii=False)`, `flush`, `os.fsync`, `os.replace`; remove temp file on failure). Make `set` and `delete` call `_save()` under the lock when `state_file` is set, reverting the in-memory change and raising `KVError("storage write failed")` (logging `kv_save_failed` with the exception class) if saving fails
- [X] T037 [US6] In `src/api/app.py` lifespan, replace the direct `KVStore(...)` with `KVStore.from_settings(settings)`; in `src/agent/harness.py` add `state_file=` (path or `None`) to the `harness_startup` log

**Checkpoint**: Persistence and reload work; interrupted saves are safe.

---

## Phase 9: User Story 7 - The agent cannot fill up memory or disk (Priority: P2)

**Goal**: Value-size and key-count limits enforced by `kv_set`, reported to the agent without aborting the request.

**Independent Test**: Small limits; oversized value and one-key-too-many are rejected and the store is unchanged.

### Tests for User Story 7 (write first, confirm FAIL)

- [X] T038 [P] [US7] Add to `tests/unit/test_kv_store.py`: `max_value_bytes=10` → `set("k", "x" * 20)` raises `KVError` whose message contains `KV_MAX_VALUE_BYTES (10)`; size measured as compact UTF-8 JSON (a value of exactly 10 bytes, e.g. `"12345678"` = 10 bytes with quotes, is accepted; multibyte characters counted in bytes); `max_keys=2` with 2 keys → new key raises with `KV_MAX_KEYS (2)`, overwriting an existing key succeeds; store unchanged after each rejection
- [X] T039 [P] [US7] Add to `tests/integration/test_kv_http.py`: env `KV_MAX_VALUE_BYTES=10`; fake LLM calls `kv_set` with a large value then `respond` with status 413; assert the HTTP response is 413 (the request was not aborted with 500) and the prompt of the second LLM call contains `value too large`

### Implementation for User Story 7

- [X] T040 [US7] In `src/state/kv_store.py::KVStore.set`, before mutating: compute the compact UTF-8 JSON size and raise `KVError` with the contract message if it exceeds `max_value_bytes`; if the key is new and `len(_data) >= max_keys`, raise the store-full message

**Checkpoint**: Part B complete.

---

## Phase 10: User Story 8 - Every response shows what it cost (Priority: P2)

**Goal**: Per-request token and step totals in headers (success and agent failures) and in the request log.

**Independent Test**: Fake LLM with usage 100/20 and 150/30 across two tool calls → headers 250 / 50 / 2 and the same numbers in the `request` log.

### Tests for User Story 8 (write first, confirm FAIL)

- [X] T041 [P] [US8] Unit tests in `tests/unit/test_usage.py` for `UsageTracker`: feed `on_llm_end` an `LLMResult(generations=[[ChatGeneration(message=AIMessage(..., usage_metadata=..., tool_calls=[...]))]])` twice and check sums and steps; a message without `usage_metadata` adds 0 tokens; a message with two tool calls adds 2 steps; a fresh tracker starts at 0/0/0
- [X] T042 [P] [US8] Integration tests in `tests/integration/test_usage_http.py` (env as other integration tests, `PERSONALITY_PATH` to a tmp persona): (a) `make_queued_llm(ai_tool_call("list_files", {}, tokens_in=100, tokens_out=20), ai_tool_call("respond", {"body": "hi"}, tokens_in=150, tokens_out=30))` → headers `x-dopamine-tokens-in: 250`, `x-dopamine-tokens-out: 50`, `x-dopamine-steps: 2`, no `x-dopamine-cost-usd`; (b) agent `respond` sets `headers={"X-Dopamine-Steps": "999", "x-dopamine-tokens-in": "1"}` → system values win and appear once; (c) `respond_with_file` reply also carries the headers (create a file under `files/` via `tmp_path` + `monkeypatch.chdir` or reuse an existing one); (d) loose-text reply (AIMessage with text, no tool call, tokens 10/5) → headers 10 / 5 / 0 alongside `X-Dopamine-Warning`; (e) `RaisingFakeLLM` with a provider-like error → 503 with headers present (0/0/0); (f) `SlowFakeLLM` with `AGENT_TIMEOUT_SECONDS=0.05` → 504 with headers; (g) with `DOPAMINE_ACCESS_KEY` set and no key → 401 without usage headers; rate limit exceeded → 429 without usage headers; `/health` without usage headers; (h) `structlog.testing.capture_logs` shows one `request` event with `tokens_in=250`, `tokens_out=50`, `steps=2` for case (a) and a `request` event with `status=504` for case (f); (i) a CORS request with `Origin: http://example.com` gets `access-control-expose-headers` listing the four header names

### Implementation for User Story 8

- [X] T043 [P] [US8] Create `src/agent/usage.py` with `class UsageTracker(BaseCallbackHandler)`: `run_inline = True`, fields `tokens_in`, `tokens_out`, `steps` (start at 0), `on_llm_end(self, response, **kwargs)` per research R9
- [X] T044 [US8] In `src/agent/harness.py::invoke_agent`, add `usage: UsageTracker | None = None` and pass `config={"recursion_limit": 25, "callbacks": [usage]}` when given (unchanged config otherwise)
- [X] T045 [US8] Create `src/api/usage_headers.py` with `USAGE_HEADERS = ("X-Dopamine-Tokens-In", "X-Dopamine-Tokens-Out", "X-Dopamine-Steps", "X-Dopamine-Cost-USD")` and `apply_usage(request, response, *, method: str, path: str) -> Response`: if `request.state` has no `usage`, return `response` unchanged; else delete every response header whose lowercase name matches a `USAGE_HEADERS` entry, set the three count headers as strings, and log `request` with `method`, `path`, `status=response.status_code`, `tokens_in`, `tokens_out`, `steps` (cost is added in US9)
- [X] T046 [US8] In `src/api/app.py` catch-all: after the guards, create `usage = UsageTracker()`, set `request.state.usage = usage`, pass `usage=usage` to `invoke_agent`; build the response as today, replace the existing `log.info("request", ...)` with `return apply_usage(request, response, method=request.method, path=f"/{full_path}")`. Add `expose_headers=list(USAGE_HEADERS)` to `CORSMiddleware`
- [X] T047 [US8] In `src/api/errors.py`, make the `LLMUnavailableError`, `AgentNoResponseError`, `AgentTimeoutError`, `AgentLoopLimitError` and generic `Exception` handlers build their `JSONResponse` as today and `return apply_usage(request, response, method=request.method, path=request.url.path)`. Leave the 413, 401 and 429 handlers unchanged

**Checkpoint**: Usage headers and log fields on every agent-run response.

---

## Phase 11: User Story 9 - Estimated cost in dollars, with the operator's prices (Priority: P3)

**Goal**: `X-Dopamine-Cost-USD` and `cost_usd` log field when both prices are configured.

**Independent Test**: Prices 3 / 15 and usage 250 / 50 → `X-Dopamine-Cost-USD: 0.001500`; no prices → no header.

### Tests for User Story 9 (write first, confirm FAIL)

- [X] T048 [P] [US9] Add to `tests/unit/test_usage.py`: `tracker.cost_usd(None, None) is None`; 250/50 with 3.0/15.0 → `"0.001500"`; 0 prices → `"0.000000"`; half-up rounding at the 7th decimal (e.g. 1 token at 0.5 per Mtok = 0.0000005 → `"0.000001"`); 1,000,000 in at 3.0 → `"3.000000"`
- [X] T049 [P] [US9] Add to `tests/integration/test_usage_http.py`: env `LLM_PRICE_INPUT_PER_MTOK=3`, `LLM_PRICE_OUTPUT_PER_MTOK=15` with case (a) → `x-dopamine-cost-usd: 0.001500` and `cost_usd="0.001500"` in the `request` log; agent-set `X-Dopamine-Cost-USD` is replaced; without prices an agent-set `X-Dopamine-Cost-USD` is removed

### Implementation for User Story 9

- [X] T050 [US9] Add `cost_usd(self, price_in: float | None, price_out: float | None) -> str | None` to `src/agent/usage.py` per research R12 (`Decimal(str(price))`, quantize `Decimal("0.000001")`, `ROUND_HALF_UP`, format with `f"{value:.6f}"`)
- [X] T051 [US9] In `src/api/usage_headers.py::apply_usage`, read prices from `load_settings()` once per call (or accept them as arguments from the caller), set `X-Dopamine-Cost-USD` and add `cost_usd` to the log when not `None`

**Checkpoint**: Part C complete.

---

## Phase 12: Polish & Cross-Cutting Concerns

- [X] T052 [P] Update `specs/001-project-boilerplate/quickstart.md` section "5. Configure the agent personality" to describe presets (`PERSONALITY`, the five names, `PERSONALITY_PATH` override, adding a file to `config/personalities/`) instead of editing `config/personality.md`
- [X] T053 [P] Grep the repo for remaining references to `config/personality.md` (`grep -rn "config/personality.md" --exclude-dir=.git --exclude-dir=specs`) and update any outside historical spec docs
- [X] T054 Run `uv run ruff check src tests`, `uv run ruff format --check src tests` and `uv run pytest`; fix any failures
- [X] T055 Run the automated part of `specs/003-cosmetic-features/quickstart.md` and tick each row; mark completed tasks `[X]` in this file
- [X] T056 Manual smoke run with a real LLM (only if `LLM_API_KEY` is available; one short pass to save tokens): `PERSONALITY=teapot` one request, `PERSONALITY=shop STATE_FILE=<tmp>` POST then GET, and check the `x-dopamine-*` headers; record results in the completion report — **Not run**: no `LLM_API_KEY` in the implementation environment; run manually per quickstart.md "Manual smoke checks"

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → all story phases.
- **Part A**: US1 (Phase 3) → US2 (Phase 4) and US3 (Phase 6) both edit `src/config/personality.py`, run them sequentially; US4 (Phase 7) needs only T009 (files exist) and can run in parallel with US2/US3.
- **Part B**: US5 (Phase 5) → US6 (Phase 8) and US7 (Phase 9), both edit `src/state/kv_store.py`, run them sequentially.
- **Part C**: US8 (Phase 10) → US9 (Phase 11).
- Parts A, B and C are independent, but US1 T011–T012, US5 T024–T025 and US8 T044/T046 touch `harness.py` / `app.py`: do not run those tasks concurrently.
- **Polish (Phase 12)** after the stories you intend to ship.

### Within each story

Tests first (confirm FAIL) → core module → wiring into harness/app → story checkpoint.

### Parallel opportunities

- Phase 2: T005 and T006 in parallel with each other (T003 → T004 sequential).
- US1: T007 ∥ T008; US5: T017 ∥ T018 ∥ T019 ∥ T020; US8: T041 ∥ T042, T043 in parallel with the tests.
- US4: T029–T033 all in parallel (separate files).
- Across parts: Part A, Part B and Part C core modules (`personality.py`, `kv_store.py` / `kv.py`, `usage.py` / `usage_headers.py`) can be built by different people at once.

## Parallel Example: User Story 5

```text
Task: "T017 Unit tests for KVStore in tests/unit/test_kv_store.py"
Task: "T018 Unit tests for kv tools in tests/unit/tools/test_kv_tools.py"
Task: "T019 build_tools + Storage section test in tests/unit/test_harness.py"
Task: "T020 kv_set → kv_get HTTP test in tests/integration/test_kv_http.py"
```

## Parallel Example: User Story 4

```text
Task: "T029 config/personalities/shop.md"
Task: "T030 config/personalities/sarcastic.md"
Task: "T031 config/personalities/website.md"
Task: "T032 config/personalities/teapot.md"
```

## Implementation Strategy

### MVP first

1. Phases 1–2.
2. Phase 3 (US1): presets selectable → stop and validate (`PERSONALITY=shop` test).
3. Phase 5 (US5): in-memory state → stop and validate (kv_set → kv_get test).

### Incremental delivery

- Part A: US1 → US2 → US3 → US4 (presets usable from US1; content lands in US4).
- Part B: US5 → US6 → US7.
- Part C: US8 → US9.
- Each checkpoint leaves the full suite green; commit after each story.

### Notes

- A test that would need the real LLM is out of scope (spec: "LLM behavior is not tested"); the only real-LLM step is T056.
- The fake LLM cannot read tool output, so storage integration tests assert on the prompt of the LLM call that follows the tool call (`CountingFakeLLM.prompts`).
