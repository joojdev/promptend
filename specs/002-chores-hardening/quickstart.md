# Quickstart: Validating Chores Hardening

## Prerequisites

- `uv sync` done; `.env` with `LLM_MODEL` and `LLM_API_KEY` (any value for tests).
- New optional settings (all have defaults): see `.env.example`.

## Automated validation

```bash
uv run pytest tests/unit tests/integration
uv run ruff check .
```

Expected: all pass; each spec scenario maps to one test. Rejection tests assert the fake LLM's call count is `0`.

## Manual smoke checks (real server)

Start with a low limit and a key:

```bash
RATE_LIMIT_PER_MINUTE=3 DOPAMINE_ACCESS_KEY=s3cret AGENT_VERBOSE=true uv run uvicorn src.api.app:app
```

1. No key → `curl -i localhost:8000/x` → `401`, no agent log line.
2. Wrong key → `curl -i -H 'X-Dopamine-Key: nope' localhost:8000/x` → `401`.
3. Right key, 4 quick calls → first 3 reach the agent, 4th returns `429 {"error":"rate_limited"}`.
4. `/health` stays `200` throughout, with or without the key.
5. Redaction: with verbose logging on, send `-H 'Authorization: Bearer abc' -H 'X-Custom-Token: t'` and confirm the logged agent input shows `[REDACTED]` for both and the real values appear nowhere.
6. Timeout: `AGENT_TIMEOUT_SECONDS=0.001` → `504 agent_timeout`.

Details: [contracts/http-errors.md](contracts/http-errors.md), [data-model.md](data-model.md).
