# Promptend

A deliberately bad idea, built carefully: an HTTP backend with no routes of its own. Every
request goes to a LangGraph ReAct agent, which reads method/path/headers/body, uses tools,
and writes the response itself. The README sells the joke; this file is for working on it.

## Commands

```bash
uv sync --extra dev                         # install (add --extra openai / --extra bedrock for those providers)
uv run pytest                               # full suite; fake LLMs only, no API key needed
uv run ruff check . && uv run ruff format --check .
uv run uvicorn src.api.app:app              # run the server (needs LLM_MODEL / LLM_API_KEY)
uv run tokens --help                        # token CLI: create | list [--all] | revoke | hash-password
```

CI (`.github/workflows/ci.yml`) runs ruff check, ruff format --check and pytest on Python
3.11 and 3.12 with `uv sync --locked`. To check 3.11 locally without touching `.venv`:
`uv run --isolated --python 3.11 --extra dev pytest -q`.

## Architecture

Request flow in the catch-all (`src/api/app.py`), in this order:
body size (413) → bearer token auth (401) → per-client rate limit (429) → agent.
`/health` is public. `/_admin/*` is a separate router registered *before* the catch-all and
never calls the agent.

| Path | Role |
|------|------|
| `src/api/app.py` | `create_app()`: settings, startup checks, one agent per role, catch-all route. `app = create_app()` runs at import |
| `src/api/admin.py` | `/_admin/login` (argon2) and `/_admin/tokens` CRUD; 404 fallback; 404 everywhere when admin creds are unset |
| `src/api/auth.py` | `parse_bearer`, `authenticate` → `Principal(role, token_id)` |
| `src/api/guards.py` | header redaction (drops `authorization`/`x-api-key`, masks other sensitive headers), `RateLimiter` |
| `src/api/errors.py` | typed exceptions → JSON error bodies (401/404/429/502/503/504/500) |
| `src/api/usage_headers.py` | `apply_usage`: `X-Promptend-Tokens-In/-Out/-Steps/-Cost-USD` + request log line |
| `src/agent/harness.py` | `PROGRAMMATIC_INSTRUCTIONS`, `load_harness(..., role=)`, `invoke_agent` (timeout, outcome classification) |
| `src/agent/registry.py` | `build_tools(store)`: the tool list |
| `src/agent/roles.py` | `tools_for_role`: admin gets all tools, user gets `role == "user"` tools only |
| `src/agent/usage.py` | `UsageTracker` callback (tokens/steps per request), cost via `Decimal` |
| `src/auth/` | `passwords.py` (argon2, timing-safe verifier), `tokens.py` (`TokenStore`, SQLite, SHA-256 hashes) |
| `src/cli/tokens.py` | the `tokens` CLI; uses only `TOKENS_DB_PATH`, never needs LLM settings |
| `src/config/` | `settings.py` (all settings, pydantic-settings), `personality.py` (preset resolution) |
| `src/state/kv_store.py` | KV store behind the `kv_*` tools; in-memory or atomic JSON file (`STATE_FILE`) |
| `src/tools/` | agent tools: `respond`, `respond_with_file`, file sandbox (`files/`), `kv_*` |
| `config/personalities/*.md` | personality presets, selected with `PERSONALITY`; tone only, never tool names |

Settings and their defaults are documented in `.env.example`; keep it in sync when adding one.

## Rules that matter

From `.specify/memory/constitution.md` (v1.3.1). Read it before changing request handling.

- **Everything goes through the agent.** New behavior is a new tool in `build_tools()`, not
  logic in a route. The only exceptions: guards that *reject* (413/401/429) or report agent
  failures, `/health`, and the `/_admin/` control plane (login + token management only).
- **The agent must end by calling `respond` / `respond_with_file`.** Presets must not
  contradict this or name tools.
- **Admin-only tool**: add `role: str = "admin"` to the tool class and register it in
  `build_tools()`. Nothing else changes; user runs never see it.
- **Test first.** Tests use the fakes in `tests/conftest.py` (`make_queued_llm`,
  `ai_tool_call`, `CountingFakeLLM`, `SlowFakeLLM`, `RaisingFakeLLM`). Rejection paths must
  assert `llm.calls == 0`. The fake LLM cannot read tool output; assert on `llm.prompts`.
- **Auth in tests**: an autouse fixture sets `AUTH_ENABLED=false` and a temp `TOKENS_DB_PATH`.
  Use `enable_auth`, `admin_env`, `user_token`, `fast_hash` to test the authenticated path.
- **Secrets**: no plain passwords in config (only `ADMIN_PASSWORD_HASH`); tokens are stored
  only as hashes; credential headers never reach the agent. `TokenStore.__init__` must do no
  I/O (`create_app()` runs at import).
- **Errors from tools**: tools that can fail set `handle_tool_error=True`; otherwise a
  `ToolException` aborts the run with a 500 (langgraph-prebuilt only converts invocation errors).
- Python 3.11+, ruff (line length 100), all config via `Settings`, no hardcoded values.

## Workflow

- Features use Spec Kit: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`. Artifacts live in `specs/NNN-name/`; `specs/` and `.specify/` are
  kept as the project record (marked as docs/vendored in `.gitattributes`).
- One branch per feature, named like the spec directory (`004-cleanup`); merge into `main`
  with `--no-ff` after the suite and ruff pass.
- Commits are authored as the repository owner. Do not add `Co-Authored-By`,
  `Claude-Session` or any other AI attribution to commits or PRs.
- Real-LLM checks are expensive: run them once, at the end, and only when asked.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/004-cleanup/plan.md
<!-- SPECKIT END -->
