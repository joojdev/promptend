# Research: Cleanup

Context checked against the repo at the start of planning: FastAPI 0.136 / Starlette 1.0, pydantic 2.13, langgraph 1.2 (`create_react_agent`), Python ≥ 3.11 (local venv 3.13). `argon2-cffi` 25.1.0 resolves through the proxy. `sqlite3` (SQLite 3.45) is in the stdlib. `uv run ruff check .` reports 5 findings, all in `.specify/scripts/python/`. No NEEDS CLARIFICATION remained.

## Part A — Admin login, user tokens, role-scoped tools

### R1. Password hashing for the admin

- **Decision**: `argon2-cffi`'s `PasswordHasher` with library defaults (argon2id). `ADMIN_PASSWORD_HASH` must be the encoded form (`$argon2id$v=19$m=...,t=...,p=...$salt$hash`). Validation at startup uses `argon2.extract_parameters(hash)`; on `InvalidHashError` the app prints `Configuration error: ADMIN_PASSWORD_HASH is not a valid argon2 hash` and exits 1, without echoing the value. Verification runs `PasswordHasher().verify(hash, password)` in a worker thread (`run_in_threadpool`) because it costs ~50 ms of CPU.
- **Rationale**: User chose argon2. `argon2-cffi` is the reference Python binding, ships wheels, and is the one new runtime dependency the spec allows (FR-022).
- **Alternatives considered**: `passlib` (unmaintained, extra layer); stdlib `hashlib.scrypt` (not what the user asked for).

### R2. Timing-safe failure for wrong username

- **Decision**: At startup build a dummy argon2 hash of a random string with the same hasher. On login, compare the username with `hmac.compare_digest`; verify the password against the real hash when the username matches and against the dummy hash otherwise; succeed only if both checks pass. Every failure returns the same 401 body.
- **Rationale**: Without the dummy verify, a wrong username returns in microseconds and a wrong password in ~50 ms, leaking which one was wrong (FR-003).

### R3. Token format and hashing

- **Decision**: User token = `"sk_" + secrets.token_urlsafe(32)`; admin token = `"adm_" + secrets.token_urlsafe(32)` (256 bits of entropy each). Stored hash = SHA-256 hex of the full token. Lookup is `WHERE token_hash = ?` on a UNIQUE index. Prefix = first 8 characters of the token.
- **Rationale**: High-entropy random tokens do not need a slow hash; brute-forcing a 256-bit secret is infeasible, and a fast hash keeps per-request auth cheap. Lookup by hash avoids comparing secrets in Python at all, so no timing side channel on the secret.
- **Alternatives considered**: argon2 for tokens (needs a scan or a separate lookup id, adds ~50 ms per request); signed stateless admin tokens with a JWT/HMAC secret (needs an extra secret setting, cannot be purged/revoked; rejected in spec assumptions).

### R4. Token store engine

- **Decision**: SQLite file at `TOKENS_DB_PATH` (default `data/tokens.db`) via stdlib `sqlite3`. One connection per operation (`sqlite3.connect(path, timeout=5)`), `PRAGMA journal_mode=WAL` set at schema creation, `PRAGMA busy_timeout` via the connect timeout. Schema created with `CREATE TABLE IF NOT EXISTS` on first use; parent directory created with `mkdir(parents=True, exist_ok=True)`. Class `TokenStore(path)` in `src/auth/tokens.py`.
- **Rationale**: Spec requires a local single-file database shared by the server and the CLI with concurrent access (edge case). SQLite handles cross-process locking; WAL lets the CLI write while the server reads. Per-operation connections avoid sharing connections across threads (FastAPI runs sync work in a thread pool).
- **Alternatives considered**: JSON file like the KV store (no cross-process locking); a long-lived shared connection with `check_same_thread=False` (needs a lock, no real benefit at this load).

### R5. Admin token lifetime and purge

- **Decision**: `expires_at = now + ADMIN_TOKEN_TTL_MINUTES`. Validity check: `revoked = 0 AND (expires_at IS NULL OR expires_at > now)`. Issuing an admin token first runs `DELETE FROM tokens WHERE role = 'admin' AND expires_at <= now`. Timestamps are UTC ISO-8601 with seconds and a `+00:00` offset (`datetime.now(UTC).isoformat(timespec="seconds")`), so string comparison in SQL is chronological.
- **Rationale**: Matches FR-004 and the "expired admin tokens accumulate" edge case without a background job.

### R6. Where auth runs and in what order

- **Decision**: Catch-all order stays: body size (413) → **token auth (401)** → rate limit (429) → agent. Auth is a plain function `authenticate(request, store, settings) -> Principal | None` in `src/api/auth.py`, where `Principal(role: "admin" | "user", token_id: int)`. It parses `Authorization: Bearer <token>` (scheme case-insensitive, exactly one space-separated token, non-empty), looks the hash up, rejects revoked/expired, and on a user token updates `last_used_at`. With `AUTH_ENABLED=false`, a missing or invalid token yields the anonymous `user` principal and a valid admin token still yields `admin`.
- **Rationale**: Keeps the existing guard ordering (spec edge case) and one header for both roles (spec assumption).

### R7. Admin routes and the reserved prefix

- **Decision**: `src/api/admin.py` exposes `build_admin_router(store, settings) -> APIRouter` mounted at `/_admin`, included before the catch-all:
  - `POST /_admin/login`, `POST /_admin/tokens`, `GET /_admin/tokens`, `DELETE /_admin/tokens/{id}`.
  - A final `/_admin/{rest:path}` route for all methods returns 404 `{"error": "not_found"}`, so unknown sub-paths and methods never fall through to the catch-all (FR-008).
  - When admin credentials are unset/blank, a router-level dependency returns 404 for every route, and `create_app` logs `admin_routes_disabled` once.
  - Login has its own `RateLimiter(settings.login_rate_limit_per_minute)` keyed by client host, checked before verification (FR-005).
  - Request bodies are pydantic models with `Field(min_length=1)` so a missing or empty field gives FastAPI's 422.
- **Rationale**: Starlette matches routes in order; registering the router (including its fallback) before `/{full_path:path}` guarantees the precedence. `/_adminx` does not match `/_admin/...` and still reaches the catch-all, as the spec requires.

### R8. Error bodies

- **Decision**: The 401 handler body becomes exactly `{"error": "unauthorized"}` (today it also has a `message`). Add `NotFoundError` → 404 `{"error": "not_found"}`. 429 stays `{"error": "rate_limited"}`.
- **Rationale**: FR-014 fixes the 401 body. One handler serves the catch-all and the admin routes.

### R9. Removing credentials from the agent input

- **Decision**: `redact_headers` drops `authorization` and `x-api-key` entirely (replacing the current special case for `x-dopamine-key`), then masks the rest as today. `ACCESS_KEY_HEADER` and `check_access_key` are deleted together with the `dopamine_access_key` setting and its tests (FR-025). The defaults of `SENSITIVE_HEADER_NAMES` stay unchanged (the two dropped names in it become no-ops).
- **Rationale**: FR-016; keeping the defaults avoids touching unrelated settings tests.

### R10. Role-scoped tools

- **Decision**: Roles are `("user", "admin")` in `src/agent/roles.py`. A tool declares its role with a class field `role: str = "admin"`; no field means `user` (read with `getattr(tool, "role", "user")`). `tools_for_role(tools, role)` returns all tools for `admin` and only `user` tools for `user`, and exits 1 with `Error: tool '<name>' declares unknown role '<role>'` for any other value. `load_harness` gains `role: str = "user"` and passes `tools_for_role(build_tools(store), role)` to `create_react_agent`. `create_app`'s lifespan builds one agent per role (same LLM, store and prompt) into `_agents: dict[str, agent]`; the catch-all picks `_agents[principal.role]`.
- **Rationale**: `create_react_agent` binds tools at build time, so per-role tool sets need one compiled agent per role. Two agents are cheap (shared LLM client and store). Filtering before binding means the model never sees disallowed tools (FR-019, prompt-injection edge case). Adding an admin tool = set `role = "admin"` on the class and add it to `build_tools` (FR-020).
- **Alternatives considered**: Filtering at call time inside `ToolNode` (model still sees the tool and can be tricked into trying it); rebuilding the agent per request (wasteful).

### R11. Command-line tool

- **Decision**: `src/cli/tokens.py` with `argparse` subcommands `create <name>`, `list [--all]`, `revoke <id>`, `hash-password`, plus a global `--db PATH`. DB path resolution: `--db`, else `TOKENS_DB_PATH` from the environment or `.env` via a small `TokenSettings(BaseSettings)` with only that field, else `data/tokens.db`. `hash-password` uses `getpass.getpass` twice. Entry points: `python -m src.cli.tokens` and `[project.scripts] tokens = "src.cli.tokens:main"`. Exit codes: 0 success, 1 not found / mismatch.
- **Rationale**: The CLI must not require LLM settings (the main `Settings` demands `LLM_MODEL`), must work with the server stopped (FR-021), and shares `TokenStore` and the hasher with the HTTP routes (FR-022).

### R12. Tests with auth on by default

- **Decision**: An autouse fixture in `tests/conftest.py` sets `TOKENS_DB_PATH` to a per-test `tmp_path` file and `AUTH_ENABLED=false`, so existing integration tests keep passing unchanged. Auth tests set `AUTH_ENABLED=true` and use helpers `make_user_token(path)` and `admin_env(monkeypatch, username, password)` (which generates a real argon2 hash with low-cost parameters for speed). `tests/unit/test_access_key.py` and the access-key cases in `tests/integration/test_guards_http.py` are removed.
- **Rationale**: FR-026 allows "a shared test fixture that either provisions a user token or disables authentication". Disabling by default keeps the diff small; dedicated tests cover the enabled path.

## Part B — CI and repository hygiene

### R13. CI workflow

- **Decision**: `.github/workflows/ci.yml`, on `push` and `pull_request`, matrix `python-version: ["3.11", "3.12"]`, steps: checkout → `astral-sh/setup-uv` (pinned major version) with `python-version` → `uv sync --locked --extra dev` → `uv run ruff check .` → `uv run ruff format --check .` → `uv run pytest`. No secrets; tests use fake LLMs, and `LLM_MODEL`/`LLM_API_KEY` are set to dummy values in the job env because `create_app` reads settings.
- **Rationale**: FR-027. `--locked` fails if `uv.lock` is stale.

### R14. Ruff scope

- **Decision**: Add `extend-exclude = [".specify", ".claude"]` to `[tool.ruff]`, then `ruff check .` and `ruff format --check .` must be clean; run `ruff format` on any project file it flags.
- **Rationale**: Spec assumption: the findings are vendored Spec Kit code, consistent with marking it vendored for GitHub.

### R15. Attributes, license, metadata

- **Decision**: `.gitattributes` with `.specify/** linguist-vendored`, `.claude/** linguist-vendored`, `specs/** linguist-documentation`. `LICENSE` = MIT text, `Copyright (c) 2026 João Vitor Piovezan`. `pyproject.toml`: `license = "MIT"`, `license-files = ["LICENSE"]`, build requirement bumped to `setuptools>=77` (SPDX license expressions). Add `data/` to `.gitignore`.
- **Rationale**: FR-029–FR-031 and US6 scenario 4.

## Part C — README

### R16. README source of truth

- **Decision**: Write `README.md` last, after Parts A and B are merged in the branch, generating the configuration table from `Settings.model_fields` (name → env var uppercase, default) and listing presets from `config/personalities/` and tools from `build_tools`. LLM-output examples are `<!-- TODO: paste output of ... -->` blocks. A unit test (`tests/unit/test_readme.py`) asserts every `Settings` field's env name appears in the README table and no unknown `UPPER_SNAKE` setting-looking name appears in it.
- **Rationale**: FR-033 / SC-009 are about the README matching the code; a test keeps it honest after future changes.
