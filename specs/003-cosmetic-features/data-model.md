# Data Model: Cosmetic Features

## Settings (additions and changes to `src/config/settings.py::Settings`)

| Field | Env var | Type | Default | Validation |
|-------|---------|------|---------|------------|
| `personality` | `PERSONALITY` | `str` | `"default"` | Normalized `strip().lower()` at resolution time; checked against available presets at startup (not in `Settings`) |
| `personality_path` | `PERSONALITY_PATH` | `str` | `""` (**changed** from `"config/personality.md"`) | Blank/whitespace = unset |
| `state_file` | `STATE_FILE` | `str` | `""` | Blank = in-memory only |
| `kv_max_value_bytes` | `KV_MAX_VALUE_BYTES` | `int` | `65536` | `> 0` |
| `kv_max_keys` | `KV_MAX_KEYS` | `int` | `1000` | `> 0` |
| `llm_price_input_per_mtok` | `LLM_PRICE_INPUT_PER_MTOK` | `float \| None` | `None` | `>= 0`; set together with output price |
| `llm_price_output_per_mtok` | `LLM_PRICE_OUTPUT_PER_MTOK` | `float \| None` | `None` | `>= 0`; set together with input price |

Invalid values exit at startup through the existing `load_settings()` path (`Configuration error: ...`, exit 1).

## PersonalitySource (`src/config/personality.py`)

Immutable result of startup resolution.

| Field | Type | Meaning |
|-------|------|---------|
| `path` | `Path` | File to load as the personality |
| `preset` | `str \| None` | Preset name, or `None` for a custom `PERSONALITY_PATH` |

Resolution rules (in order):

1. `personality_path.strip()` non-empty → `PersonalitySource(path=Path(personality_path), preset=None)`. Existence is checked by `load_harness` (unchanged error).
2. Else `name = personality.strip().lower()`; `available = sorted(stem for *.md in PRESETS_DIR)`.
3. `available` empty (directory missing or no `.md`) → exit 1: `Error: no personality presets found in config/personalities/`.
4. `name` contains `/`, `\`, or `..`, or `name not in available` → exit 1: `Error: unknown personality preset 'NAME'. Available presets: a, b, c`.
5. Else → `PersonalitySource(path=PRESETS_DIR / f"{name}.md", preset=name)`.

Startup log `harness_startup` gains `personality_preset` (name or `null`) alongside the existing `personality_path`; an empty file additionally logs `personality_empty` at warning level.

## Personality preset (files)

`config/personalities/<name>.md` — lowercase file name, UTF-8 Markdown, non-empty. Shipped: `default`, `shop`, `sarcastic`, `website`, `teapot`. `config/personality.md` is deleted; its content moves to `default.md`.

## KVStore (`src/state/kv_store.py`)

| Attribute | Type | Notes |
|-----------|------|-------|
| `max_value_bytes` | `int` | From settings |
| `max_keys` | `int` | From settings |
| `state_file` | `Path \| None` | `None` = in-memory |
| `_data` | `dict[str, JSONValue]` | `JSONValue = str \| int \| float \| bool \| None \| list \| dict` |
| `_lock` | `threading.Lock` | Guards `_data` and file writes |

Operations (all under `_lock`):

| Method | Returns | Errors (`KVError`, message for the agent) |
|--------|---------|-------------------------------------------|
| `set(key, value)` | `{"ok": true, "key": key, "created": bool}` | invalid key; value too large (`... exceeds KV_MAX_VALUE_BYTES (N bytes)`); store full on a new key (`... KV_MAX_KEYS (M) reached`); save failure (`storage write failed`) — store unchanged in all cases |
| `get(key)` | `{"found": true, "key": key, "value": v}` or `{"found": false, "key": key}` | invalid key |
| `list(prefix="")` | `{"prefix": p, "keys": [sorted keys starting with p]}` | — |
| `delete(key)` | `{"deleted": true, "key": key}` or `{"deleted": false, "key": key}` (not found) | invalid key; save failure (store unchanged) |

Key rule: `isinstance(key, str) and 1 <= len(key) <= 256`.

Lifecycle:

- `KVStore.from_settings(settings)` → if `state_file` set and the file exists, load it; parse error, non-object root, or non-string key → print `Error: invalid state file PATH: reason` and exit 1 (file untouched). Over-limit content loads with a `kv_state_over_limit` warning.
- Each successful `set`/`delete` with a `state_file` rewrites the whole file atomically (temp file in the same directory → `fsync` → `os.replace`) before returning. The file is created on the first write.

State file format: one JSON object, `{"<key>": <value>, ...}`, UTF-8.

## KV tools (`src/tools/kv.py`)

All four: `BaseTool` subclasses with a `store: KVStore` field, `handle_tool_error=True`, `return_direct=False`. Each `_run` calls the matching store method, converts `KVError` to `ToolException`, and returns the result dict serialized as a JSON string.

| Tool | Args model |
|------|-----------|
| `kv_set` | `key: str`, `value: str \| int \| float \| bool \| list \| dict \| None` |
| `kv_get` | `key: str` |
| `kv_list` | `prefix: str = ""` |
| `kv_delete` | `key: str` |

## UsageTracker (`src/agent/usage.py`)

Per-request callback handler (`BaseCallbackHandler`, `run_inline = True`).

| Field | Type | Update rule |
|-------|------|-------------|
| `tokens_in` | `int` | `+= usage_metadata.get("input_tokens", 0)` per generation in `on_llm_end` |
| `tokens_out` | `int` | `+= usage_metadata.get("output_tokens", 0)` |
| `steps` | `int` | `+= len(message.tool_calls)` |

Method `cost_usd(price_in, price_out) -> str | None`: `None` if prices unset, else Decimal computation quantized to 6 places.

Lifecycle: created in the catch-all route after guards pass → stored on `request.state.usage` → passed to `invoke_agent` → read by `apply_usage` on success or failure. Discarded with the request.

## Response usage headers

| Header | Value |
|--------|-------|
| `X-Dopamine-Tokens-In` | `tokens_in` (decimal integer) |
| `X-Dopamine-Tokens-Out` | `tokens_out` |
| `X-Dopamine-Steps` | `steps` |
| `X-Dopamine-Cost-USD` | 6-decimal string; only when both prices are set |

Full contract: [contracts/usage-headers.md](contracts/usage-headers.md).
