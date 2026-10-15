# Quickstart: Validating Cosmetic Features

## Prerequisites

- `uv sync --extra dev`
- `.env` with `LLM_MODEL` and `LLM_API_KEY` (any value works for the automated tests; a real key is needed only for the manual checks).
- New settings and defaults: [contracts/configuration.md](contracts/configuration.md).

## Automated validation

```bash
uv run pytest
uv run ruff check src tests && uv run ruff format --check src tests
```

Expected: all tests pass. Coverage by part:

| Part | What the tests prove |
|------|----------------------|
| A — presets | default/named/normalized resolution, `PERSONALITY_PATH` priority, unknown name and `../x` exit 1 listing presets, empty presets dir, every shipped preset non-empty and free of forbidden phrases |
| B — storage | each tool's contract and errors ([contracts/kv-tools.md](contracts/kv-tools.md)), limits, key rule, reload from `STATE_FILE`, atomic save leaves old file on simulated failure, invalid state file exits 1, fake-LLM HTTP test: request 1 `kv_set`, request 2 `kv_get` returns the value |
| C — usage | fake LLM with known `usage_metadata` → exact headers, override of agent-set headers, headers on 502/504, none on 401/429, cost with prices, no cost without, log fields ([contracts/usage-headers.md](contracts/usage-headers.md)) |

## Manual smoke checks (real LLM)

1. **Presets**
   ```bash
   PERSONALITY=teapot uv run uvicorn src.api.app:app
   curl -i localhost:8000/coffee          # 418 + philosophy
   PERSONALITY=website uv run uvicorn src.api.app:app
   curl -i localhost:8000/about           # text/html, full page
   PERSONALITY=sarcatic uv run uvicorn src.api.app:app   # exits 1, lists presets
   ```
2. **State**
   ```bash
   PERSONALITY=shop STATE_FILE=./state.json uv run uvicorn src.api.app:app
   curl -i -X POST localhost:8000/products -d '{"name":"Self-aware toaster"}'
   curl -i localhost:8000/products        # includes the toaster
   # restart the server with the same STATE_FILE, repeat the GET: still there
   ```
3. **Usage**
   ```bash
   LLM_PRICE_INPUT_PER_MTOK=3 LLM_PRICE_OUTPUT_PER_MTOK=15 uv run uvicorn src.api.app:app
   curl -si localhost:8000/hello | grep -i x-dopamine
   ```
   Expect `x-dopamine-tokens-in`, `-tokens-out`, `-steps`, `-cost-usd`, and the same numbers in the `request` log line.

Details: [data-model.md](data-model.md), [research.md](research.md).
