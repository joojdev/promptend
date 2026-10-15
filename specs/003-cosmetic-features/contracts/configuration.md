# Contract: Configuration and Startup

New and changed environment settings. All are read through `Settings` (`.env` supported) and documented in `.env.example`.

| Variable | Default | Effect |
|----------|---------|--------|
| `PERSONALITY` | `default` | Preset name → `config/personalities/<name>.md`. Case-insensitive, trimmed. |
| `PERSONALITY_PATH` | *(unset)* | Custom personality file. When non-empty, wins over `PERSONALITY`. **Default changed** from `config/personality.md`. |
| `STATE_FILE` | *(unset)* | JSON file for the KV store. Unset = in-memory. |
| `KV_MAX_VALUE_BYTES` | `65536` | Max compact-UTF-8-JSON size of one value. Must be > 0. |
| `KV_MAX_KEYS` | `1000` | Max number of keys. Must be > 0. |
| `LLM_PRICE_INPUT_PER_MTOK` | *(unset)* | USD per 1M input tokens. ≥ 0. Requires the output price. |
| `LLM_PRICE_OUTPUT_PER_MTOK` | *(unset)* | USD per 1M output tokens. ≥ 0. Requires the input price. |

## Startup failures (exit code 1, message on stderr)

| Condition | Message |
|-----------|---------|
| `PERSONALITY_PATH` set, file missing | `Error: personality file not found: <path>` (unchanged) |
| Unknown preset or name with `/`, `\`, `..` | `Error: unknown personality preset '<name>'. Available presets: default, sarcastic, shop, teapot, website` |
| No `.md` presets in `config/personalities/` (and no `PERSONALITY_PATH`) | `Error: no personality presets found in config/personalities/` |
| `STATE_FILE` exists but is not a JSON object with string keys | `Error: invalid state file <path>: <reason>` |
| `KV_MAX_*` ≤ 0, only one price set, negative price | `Configuration error: ...` (existing pydantic path) |

## Startup log

`harness_startup` event fields: `personality_loaded`, `personality_path`, `personality_preset` (new; `null` for a custom path), `verbose`, plus `state_file` (new; `null` when in-memory) and `kv_keys` (new; number of keys loaded).
