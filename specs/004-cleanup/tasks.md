---

description: "Task list for Cleanup"
---

# Tasks: Cleanup

**Input**: Design documents from `specs/004-cleanup/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-api.md, contracts/catch-all-auth.md, contracts/cli-and-config.md

**Tests**: REQUIRED for Part A (spec SC-001/SC-004/SC-005/SC-006a call for tests with a call-counting fake LLM; constitution Principle III mandates test-first). Within each story write the tests first and confirm they FAIL before implementing. No test calls a real LLM.

**Organization**: Grouped by user story. Priority order P1 (US1, US2, US3, US6) → P2 (US4, US5, US7, US8) → P3 (US9) → US10 (P2, but last because the README must describe what Parts A and B actually built).

- Part A = US1–US7, Part B = US8–US9, Part C = US10.
- Parts A and B are independent. Part C depends on both.

**Shared files** (do not edit concurrently): `src/api/app.py` (US1, US2/US3, US4, US7), `src/config/settings.py` (Phase 2 only), `tests/conftest.py` (Phase 2 only), `pyproject.toml` (T001, US5, US8, US9).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 … US10 (spec.md user stories)

---

## Phase 1: Setup

**Purpose**: Baseline and dependency.

- [X] T001 Run `uv run pytest` and `uv run ruff check src tests` and record a green baseline (fix nothing; if red, stop and report). Then `uv add "argon2-cffi>=25.1"` so `pyproject.toml` and `uv.lock` are updated; confirm `uv run python -c "import argon2"` works
- [X] T002 [P] Create empty packages `src/auth/__init__.py` and `src/cli/__init__.py`
- [X] T003 [P] Add `data/` to `.gitignore` (token store directory, FR-007 / US6 scenario 4)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Settings, token store, password hashing, error bodies and test fixtures used by every Part A story.

**⚠️ CRITICAL**: No Part A story can begin until this phase is complete. Part B (US8, US9) does not depend on it.

### Tests (write first, confirm FAIL)

- [X] T004 [P] Update `tests/unit/test_startup.py`: add tests for the new settings per data-model.md: defaults (`admin_username == ""`, `admin_password_hash == ""`, `admin_token_ttl_minutes == 60`, `login_rate_limit_per_minute == 5`, `tokens_db_path == "data/tokens.db"`, `auth_enabled is True`), env overrides, `0`/`-1` rejected for the two ints, values stripped, `admin_enabled` true only when both admin fields are non-blank
- [X] T005 [P] Unit tests in `tests/unit/test_token_store.py` for `TokenStore(tmp_path / "sub" / "tokens.db")` per data-model.md: parent dir and schema created on first use; `create_user_token("app")` returns `IssuedToken` whose `token` starts with `sk_`, `prefix == token[:8]`, `id` is an int; blank name raises `ValueError`; `authenticate(token)` returns a record with `role == "user"` and sets `last_used_at`; unknown token → `None`; `revoke_user_token(id)` → `True`, then `authenticate` → `None`, revoking again → `True` and stays revoked; unknown id → `False`; `issue_admin_token(ttl_minutes=60)` returns `adm_` token with `expires_at` ≈ now + 60 min and `authenticate` gives `role == "admin"`; an admin token whose `expires_at` is in the past (monkeypatch the module's `_now()` helper) → `None`; issuing a new admin token deletes expired admin rows; `revoke_user_token(<admin id>)` → `False`; `list_user_tokens()` excludes admin tokens, orders by id, includes revoked, and records have no `token`/`token_hash` attribute; two `TokenStore` instances on the same file see each other's writes; constructing `TokenStore(path)` alone creates neither the file nor its parent directory
- [X] T006 [P] Unit tests in `tests/unit/test_passwords.py`: `hash_password("pw")` starts with `$argon2id$` and `validate_hash` accepts it; `validate_hash("not-a-hash")` and `validate_hash("$2b$12$…")` raise `InvalidAdminHash` whose message does not contain the input; `AdminVerifier("admin", h).verify("admin", "pw")` → True; wrong password, wrong username, username with different case → False; with a wrong username the real hash is not verified but a verify call still happens (patch the hasher's `verify` and assert it was called once with the dummy hash)

### Implementation

- [X] T007 Edit `src/config/settings.py` per data-model.md: add `admin_username: str = ""`, `admin_password_hash: str = ""` (both stripped by a validator), `admin_token_ttl_minutes: int = 60`, `login_rate_limit_per_minute: int = 5` (add both to the existing `must_be_positive` validator), `tokens_db_path: str = "data/tokens.db"`, `auth_enabled: bool = True`, and property `admin_enabled`. Do NOT validate the hash format here (pydantic errors print the input). Do NOT remove `dopamine_access_key` yet: `src/api/app.py` still reads it until T018
- [X] T008 [P] Create `src/auth/passwords.py`: module-level `_hasher = argon2.PasswordHasher()`; `class InvalidAdminHash(ValueError)`; `validate_hash(h)` using `argon2.extract_parameters` (map any argon2 exception to `InvalidAdminHash("ADMIN_PASSWORD_HASH is not a valid argon2 hash")`); `hash_password(pw) -> str`; `class AdminVerifier(username, password_hash, hasher=_hasher)` that builds a dummy hash of `secrets.token_urlsafe(16)` in `__init__` and implements `verify(username, password) -> bool` per research R2 (`hmac.compare_digest` on UTF-8 usernames; verify against real or dummy hash; catch `argon2.exceptions.VerifyMismatchError`/`VerificationError`/`InvalidHashError` → False)
- [X] T009 [P] Create `src/auth/tokens.py` per data-model.md and research R3–R5: `USER_PREFIX = "sk_"`, `ADMIN_PREFIX = "adm_"`, `PREFIX_LEN = 8`; `_now()` returning `datetime.now(UTC)`; `_iso(dt)`; `_hash(token)` = SHA-256 hex; frozen dataclasses `IssuedToken(id, name, prefix, token, created_at, expires_at=None)` and `TokenRecord(id, role, name, prefix, created_at, last_used_at, expires_at, revoked)` with `to_public_dict()` (`id, name, prefix, created_at, last_used_at, revoked` as bool); `class TokenStore(path)` with `_connect()` (mkdir parents, `sqlite3.connect(path, timeout=5)`, row factory, `CREATE TABLE IF NOT EXISTS tokens (...)` with the columns/CHECK/UNIQUE from data-model.md, `PRAGMA journal_mode=WAL` once), and methods `create_user_token`, `issue_admin_token`, `authenticate`, `list_user_tokens(include_revoked=True)`, `revoke_user_token`. `__init__` MUST do no I/O (only store the path): `create_app()` runs at import of `src.api.app`, so an eager connect would create `data/tokens.db` in the repo on every import. Generate secrets with `secrets.token_urlsafe(32)`. Use one connection per method inside `with closing(...)` + `with conn:` for transactions
- [X] T010 [P] Edit `src/api/errors.py`: the `UnauthorizedError` handler body becomes exactly `{"error": "unauthorized"}`; add `class NotFoundError(Exception)` with a handler returning `404 {"error": "not_found"}`
- [X] T011 Edit `tests/conftest.py`: add an autouse fixture `_auth_defaults(monkeypatch, tmp_path)` that sets `TOKENS_DB_PATH` to `str(tmp_path / "tokens.db")` and `AUTH_ENABLED=false`, and deletes `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` from the env; add helpers `fast_hash(password) -> str` (argon2 `PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash`), `enable_auth(monkeypatch)` (sets `AUTH_ENABLED=true`), `admin_env(monkeypatch, username="admin", password="pw")` (sets both admin vars using `fast_hash`), and `user_token(db_path, name="test") -> str` (creates via `TokenStore`)

**Checkpoint**: Full suite green (`uv run pytest`). The shared access key still exists; it is removed atomically in US1 (T015 + T018).

---

## Phase 3: User Story 1 - Only token holders can make the agent answer (Priority: P1) 🎯 MVP

**Goal**: The catch-all requires `Authorization: Bearer` with a valid user or admin token before the rate limit; credentials never reach the agent; the shared access key is gone.

**Independent Test**: Fake LLM + store with one user token: no token / malformed / unknown / revoked / expired-admin → 401 with zero LLM calls; valid user and valid admin tokens → agent reply.

### Tests for User Story 1 (write first, confirm FAIL)

- [X] T012 [P] [US1] Unit tests in `tests/unit/test_auth.py` for `parse_bearer(header)` and `authenticate(...)` per contracts/catch-all-auth.md: `None`, `""`, `"Basic x"`, `"Bearer"`, `"Bearer "`, `"Bearer a b"` → no token; `"bearer TOKEN"` and `"Bearer TOKEN"` → `"TOKEN"`; with auth enabled, valid user token → `Principal("user", id)`, valid admin → `Principal("admin", id)`, invalid → `None`
- [X] T013 [P] [US1] Update `tests/unit/test_redaction.py`: replace `test_access_key_header_omitted` with a test that `authorization` and `x-api-key` (any case) are absent from the output while `x-dopamine-key` is now treated like any other header (masked because its name contains `key`)
- [X] T014 [P] [US1] Integration tests in `tests/integration/test_auth_http.py` using `make_queued_llm`, `enable_auth`, `user_token` and the `TOKENS_DB_PATH` from the autouse fixture: (a) no header, `Basic x`, `Bearer` with empty token, unknown token, revoked token → each 401 body exactly `{"error": "unauthorized"}` and `llm.calls == 0`; (b) valid user token → 200 agent reply, and `last_used_at` set in the store; (c) admin token issued via `TokenStore.issue_admin_token` → 200; expired admin token (monkeypatch `src.auth.tokens._now`) → 401; (d) `/health` without token → 200; (e) with `RATE_LIMIT_PER_MINUTE=1`, two unauthenticated requests then one authenticated → the authenticated one is 200 (401s did not consume budget); (f) a request with `Authorization: Bearer <valid>` and `X-API-Key: zzz` → `llm.prompts[0]` contains neither `authorization`, `x-api-key`, the token nor `zzz` (case-insensitive)
- [X] T015 [P] [US1] Remove access-key tests: in `tests/unit/test_startup.py` remove every `DOPAMINE_ACCESS_KEY` / `dopamine_access_key` assertion and env name; delete `tests/unit/test_access_key.py`; in `tests/integration/test_guards_http.py` remove the `DOPAMINE_ACCESS_KEY` parameter/cases and keep the body-size and rate-limit tests working with auth disabled (autouse fixture); in `tests/integration/test_usage_http.py` replace the 401 case that used `DOPAMINE_ACCESS_KEY="s3cret"` with `enable_auth` + no token, and drop `DOPAMINE_ACCESS_KEY` from its env list

### Implementation for User Story 1

- [X] T016 [US1] Edit `src/api/guards.py`: delete `ACCESS_KEY_HEADER` and `check_access_key`; in `redact_headers` drop headers whose lowercase name is `authorization` or `x-api-key` (constant `_DROPPED = frozenset({"authorization", "x-api-key"})`), mask the rest as today; update the docstring
- [X] T017 [US1] Create `src/api/auth.py`: frozen dataclass `Principal(role: str, token_id: int | None)`; `ANONYMOUS_USER = Principal("user", None)`; `parse_bearer(header: str | None) -> str | None`; `authenticate(header, store: TokenStore, auth_enabled: bool) -> Principal | None` implementing the decision table (enabled: valid → principal, else `None`; disabled: valid admin → admin, anything else → `ANONYMOUS_USER`)
- [X] T018 [US1] Remove the shared access key in one step: delete `dopamine_access_key` and its `strip_access_key` validator from `src/config/settings.py`, and in `src/api/app.py` remove the `check_access_key` import and check; create `token_store = TokenStore(settings.tokens_db_path)` in `create_app`; in the catch-all after the body-size check call `principal = authenticate(request.headers.get("authorization"), token_store, settings.auth_enabled)` and `raise UnauthorizedError()` when `None`, before `limiter.check`; store `request.state.principal = principal` (used by US4)
- [X] T019 [P] [US1] Edit `.env.example`: remove the `DOPAMINE_ACCESS_KEY` lines; add `# AUTH_ENABLED=true` (comment: set false only for local development) and `# TOKENS_DB_PATH=data/tokens.db`

**Checkpoint**: Full suite green; 401 paths make zero LLM calls. Tokens can be provisioned only by code/tests until US2/US3/US5.

---

## Phase 4: User Story 2 - The admin logs in with a username and password (Priority: P1)

**Goal**: `POST /_admin/login` with argon2-verified credentials returns an expiring `adm_` token; rate-limited; `/_admin/` 404 when credentials are unset; invalid hash fails startup.

**Independent Test**: With `admin_env`, login succeeds and fails as per contracts/admin-api.md; LLM never called.

### Tests for User Story 2 (write first, confirm FAIL)

- [ ] T020 [P] [US2] Integration tests in `tests/integration/test_admin_http.py` (login part) with `admin_env` and `make_queued_llm()`: correct credentials → 200, `token` starts with `adm_`, `token_type == "bearer"`, `expires_at` parses as an aware datetime ≈ now + `ADMIN_TOKEN_TTL_MINUTES`; wrong password and wrong username → 401 with identical bodies `{"error": "unauthorized"}`; missing field / empty string / non-JSON → 422; with `LOGIN_RATE_LIMIT_PER_MINUTE=2`, the 3rd attempt (even with correct credentials) → 429; without admin env: `POST /_admin/login`, `GET /_admin/tokens`, `GET /_admin/anything` → 404 `{"error": "not_found"}` and `capture_logs` shows `admin_routes_disabled` at startup; `GET /_adminx` with auth disabled reaches the agent (catch-all); without admin env but with `enable_auth` and a valid `sk_` token from `user_token(...)`, the catch-all still returns 200 (FR-013); `llm.calls == 0` for every `/_admin/` request
- [ ] T021 [P] [US2] Add to `tests/unit/test_startup.py`: `create_app(llm=...)` with `ADMIN_USERNAME=admin` and `ADMIN_PASSWORD_HASH=not-a-hash` raises `SystemExit(1)` and stderr contains `ADMIN_PASSWORD_HASH is not a valid argon2 hash` but not `not-a-hash`

### Implementation for User Story 2

- [ ] T022 [US2] Create `src/api/admin.py` with `build_admin_router(store: TokenStore, settings) -> APIRouter` (prefix `/_admin`): a router-level dependency raising `NotFoundError` when `not settings.admin_enabled`; `LoginRequest(BaseModel)` with `username`/`password: str = Field(min_length=1)`; `POST /login` that checks a dedicated `RateLimiter(settings.login_rate_limit_per_minute)` keyed by client host (raise `RateLimitedError`), then `await run_in_threadpool(verifier.verify, ...)` with an `AdminVerifier(settings.admin_username, settings.admin_password_hash)` built once when enabled, raising `UnauthorizedError` on failure, else `store.issue_admin_token(settings.admin_token_ttl_minutes)` → `{"token", "token_type": "bearer", "expires_at"}`; a final `@router.api_route("/{rest:path}", methods=[...all...])` raising `NotFoundError`
- [ ] T023 [US2] Edit `src/api/app.py`: before building the app, when `settings.admin_password_hash` is set call `validate_hash` and on `InvalidAdminHash` print `Configuration error: <message>` to stderr and `sys.exit(1)`; log `admin_routes_disabled` (warning) when not `settings.admin_enabled`; `app.include_router(build_admin_router(token_store, settings))` BEFORE the catch-all route is declared

**Checkpoint**: Admin can obtain a token; nothing under `/_admin/` reaches the agent.

---

## Phase 5: User Story 3 - The admin manages user tokens over HTTP (Priority: P1)

**Goal**: Create / list / revoke user tokens with the admin token.

**Independent Test**: Login → create → list → revoke → revoked token gets 401 on the catch-all; user token on admin routes → 401.

### Tests for User Story 3 (write first, confirm FAIL)

- [ ] T024 [P] [US3] Add to `tests/integration/test_admin_http.py` (with `admin_env`, `enable_auth`): login, `POST /_admin/tokens {"name": "app"}` → 201 with `id, name, prefix, token (sk_…), created_at`; empty name → 422; `GET /_admin/tokens` → list containing that id with `revoked: false`, no `token`/`token_hash` keys, no admin rows; catch-all with the new `sk_` token → 200; `DELETE /_admin/tokens/{id}` → 204, again → 204; catch-all with it → 401; `DELETE /_admin/tokens/999` → 404; `DELETE /_admin/tokens/<admin token id>` → 404; token routes with no header, a user token, an unknown token, or an expired admin token (monkeypatch `_now`) → 401; `PUT /_admin/tokens` → 404 or 405; `llm.calls` only counts the catch-all requests

### Implementation for User Story 3

- [ ] T025 [US3] Add to `src/api/admin.py`: dependency `require_admin(request)` = `authenticate(header, store, auth_enabled=True)` must return a `Principal` with role `admin`, else `UnauthorizedError`; `CreateTokenRequest(name: str = Field(min_length=1))`; `POST /tokens` (201, `IssuedToken` fields), `GET /tokens` (`[r.to_public_dict() for r in store.list_user_tokens()]`), `DELETE /tokens/{token_id}` (`int` path param; 204 `Response`, or `NotFoundError`). Declare these routes before the `/{rest:path}` fallback

**Checkpoint**: Full HTTP token lifecycle works; Part A MVP (US1–US3) complete.

---

## Phase 6: User Story 6 - Tokens can never be recovered from storage (Priority: P1)

**Goal**: Prove no full token or plain password is stored or retrievable.

**Independent Test**: Issue tokens, scan the raw DB bytes.

### Tests for User Story 6 (write first, confirm FAIL where applicable)

- [ ] T026 [P] [US6] Add to `tests/unit/test_token_store.py`: create 3 user tokens and 1 admin token, then read the DB file bytes (and any `-wal` file) and assert none of the 4 full tokens appears, while each `prefix` does; assert the table has exactly the columns in data-model.md (`PRAGMA table_info(tokens)`)
- [ ] T027 [P] [US6] Add to `tests/unit/test_startup.py`: `Settings` has no field whose name contains `password` other than `admin_password_hash`; add to `tests/unit/test_repo_files.py` (new): `.gitignore` lists `data/`

### Implementation for User Story 6

- [ ] T028 [US6] Fix anything T026–T027 expose (expected: nothing beyond Phase 2 / T003); if the WAL file holds plaintext, it cannot (only hashes are written) — document the result in the checkpoint

**Checkpoint**: Storage audit passes.

---

## Phase 7: User Story 4 - Some tools are only for the admin (Priority: P2)

**Goal**: Tools declare `role`; admin runs get all tools, user runs only `user` tools; unknown role fails startup.

**Independent Test**: Register a test admin tool; inspect which tools each role's agent is offered.

### Tests for User Story 4 (write first, confirm FAIL)

- [ ] T029 [P] [US4] Unit tests in `tests/unit/test_roles.py`: a `BaseTool` subclass without `role` → `tool_role(t) == "user"`; `tools_for_role([user_tool, admin_tool], "admin")` → both; `"user"` → only `user_tool`; a tool with `role = "root"` → `SystemExit(1)` and stderr `tool '<name>' declares unknown role 'root'`; every tool in `build_tools(KVStore(...))` is `user`
- [ ] T030 [P] [US4] Integration tests in `tests/integration/test_tool_roles_http.py`: define `AdminOnlyTool(BaseTool)` with `name = "admin_only"`, `role: str = "admin"`; monkeypatch `src.agent.harness.build_tools` to return the real tools plus `AdminOnlyTool()`; use a fake LLM subclass that records the tool names passed to `bind_tools` per agent build; with `enable_auth`, an admin token request and a user token request each get a reply; assert the admin agent's bound tools include `admin_only` and the user agent's do not; with auth disabled and no token the user agent is used; with auth disabled and a valid admin token (from `TokenStore.issue_admin_token`) the admin agent is used (US7 scenario 4)

### Implementation for User Story 4

- [ ] T031 [P] [US4] Create `src/agent/roles.py`: `ROLES = ("user", "admin")`, `tool_role(tool) -> str` (`getattr(tool, "role", "user")`), `tools_for_role(tools, role) -> list[BaseTool]` per contracts/catch-all-auth.md (validate every tool's role first; print `Error: tool '<name>' declares unknown role '<role>'` and `sys.exit(1)` on an unknown one)
- [ ] T032 [US4] Edit `src/agent/harness.py::load_harness`: add keyword `role: str = "user"`; pass `tools_for_role(build_tools(store), role)` to `create_react_agent`; add `role=role` and `tools=[t.name for t in tools]` to the `harness_startup` log
- [ ] T033 [US4] Edit `src/api/app.py`: in the lifespan build `_agents = {role: load_harness(..., role=role) for role in ROLES}` sharing one `store` and the same `llm`; in the catch-all call `invoke_agent(_agents[principal.role], ...)`; remove the module-level `_agent` (no test references it)
- [ ] T034 [P] [US4] Add a comment block above `build_tools` in `src/agent/registry.py` explaining how to add a role-restricted tool (two steps from contracts/catch-all-auth.md)

**Checkpoint**: Role-scoped tools work; existing tools unchanged for both roles.

---

## Phase 8: User Story 5 - The owner manages user tokens from the command line (Priority: P2)

**Goal**: `tokens create | list [--all] | revoke | hash-password`, sharing `TokenStore` and the hasher.

**Independent Test**: Run each command against a tmp store and check output and DB state; a CLI-created token works over HTTP.

### Tests for User Story 5 (write first, confirm FAIL)

- [ ] T035 [P] [US5] Unit tests in `tests/unit/test_cli_tokens.py` calling `main(argv)` with `--db <tmp>` and `capsys`: `create app` prints a line starting with `sk_` and the "will not be shown again" warning, exit 0; `list` shows header `ID  NAME  PREFIX  CREATED AT  LAST USED  STATUS` and the row; after `revoke <id>`, `list` hides it and `list --all` shows `revoked`; `revoke 999` → exit 1 with `not found` on stderr; empty store → `No tokens.`; `hash-password` with `getpass` monkeypatched to return `pw`, `pw` → prints `$argon2id$…` that `AdminVerifier("a", h).verify("a", "pw")` accepts; mismatch → exit 1, empty stdout; without `--db`, `TOKENS_DB_PATH` env is used; a token created by the CLI authenticates via `TokenStore(...).authenticate`; the CLI works with no `LLM_MODEL` in the env (delete it)
- [ ] T036 [P] [US5] Add to `tests/integration/test_admin_http.py`: a token created with the CLI (`main(["--db", path, "create", "cli"])`) appears in `GET /_admin/tokens`, and one created over HTTP appears in `main([... "list"])` output

### Implementation for User Story 5

- [ ] T037 [US5] Create `src/cli/tokens.py` per contracts/cli-and-config.md and research R11: `TokenSettings(BaseSettings)` (`tokens_db_path: str = "data/tokens.db"`, `env_file=".env"`, `extra="ignore"`); `main(argv: list[str] | None = None) -> int` with argparse subcommands and global `--db`; plain-text table with fixed-width columns; `hash-password` uses `getpass.getpass` twice and `hash_password`; `if __name__ == "__main__": sys.exit(main())`
- [ ] T038 [US5] Add `[project.scripts] tokens = "src.cli.tokens:main"` to `pyproject.toml` and run `uv sync --extra dev`; verify `uv run tokens --help` and `uv run python -m src.cli.tokens --help`
- [ ] T039 [P] [US5] Edit `.env.example`: add `# ADMIN_USERNAME=admin`, `# ADMIN_PASSWORD_HASH=` (comment: generate with `uv run tokens hash-password`; never put the plain password here), `# ADMIN_TOKEN_TTL_MINUTES=60`, `# LOGIN_RATE_LIMIT_PER_MINUTE=5`

**Checkpoint**: CLI and HTTP manage the same tokens.

---

## Phase 9: User Story 7 - Local development without tokens (Priority: P2)

**Goal**: `AUTH_ENABLED=false` lets token-less requests through (user tools) with a startup warning; admin tokens still select admin tools.

**Independent Test**: Start with `AUTH_ENABLED=false`, request without token → agent; warning logged.

### Tests for User Story 7 (write first, confirm FAIL)

- [ ] T040 [P] [US7] Add to `tests/integration/test_auth_http.py`: with `AUTH_ENABLED=false` (the autouse default) a token-less request → 200 and `capture_logs` shows `auth_disabled` warning at startup; an invalid bearer token → 200 (user role); `Authorization` still absent from `llm.prompts[0]`; `AUTH_ENABLED` unset (delenv) → token-less request → 401

### Implementation for User Story 7

- [ ] T041 [US7] Edit `src/api/app.py`: log `auth_disabled` at warning level in `create_app` when `not settings.auth_enabled` (the decision table itself is already in `authenticate` from T017)

**Checkpoint**: Part A complete.

---

## Phase 10: User Story 8 - Every push is checked automatically (Priority: P2)

**Goal**: CI on 3.11/3.12 with ruff check, ruff format --check and pytest via uv; ruff clean.

**Independent Test**: Local `ruff check .` / `ruff format --check .` clean; workflow file valid; push shows green jobs.

- [ ] T042 [US8] Edit `pyproject.toml` `[tool.ruff]`: add `extend-exclude = [".specify", ".claude"]`; run `uv run ruff check .` and `uv run ruff format --check .`; fix any finding in project files (run `uv run ruff format .` if only formatting)
- [ ] T043 [P] [US8] Create `.github/workflows/ci.yml` per research R13: name `CI`; `on: [push, pull_request]`; job `test` on `ubuntu-latest`, `strategy.matrix.python-version: ["3.11", "3.12"]`; env `LLM_MODEL: test-model`, `LLM_API_KEY: test-key`; steps `actions/checkout@v4`, `astral-sh/setup-uv@v6` with `python-version: ${{ matrix.python-version }}`, `uv sync --locked --extra dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`
- [ ] T044 [US8] Verify the code runs on Python 3.11: `uv run --isolated --python 3.11 --extra dev pytest -q` (`--isolated` keeps the project's `.venv` untouched; uv installs 3.11 if needed); fix any 3.12+-only syntax found

**Checkpoint**: CI config ready; confirm green after push.

---

## Phase 11: User Story 9 - The repository presents itself honestly (Priority: P3)

**Goal**: Vendored/documentation attributes, MIT license, license metadata.

**Independent Test**: Files exist with the required content; `.specify/` and `specs/` still present.

- [ ] T045 [P] [US9] Add to `tests/unit/test_repo_files.py`: `.gitattributes` contains `.specify/** linguist-vendored`, `.claude/** linguist-vendored`, `specs/** linguist-documentation`; `LICENSE` starts with `MIT License` and contains `Copyright (c) 2026 João Vitor Piovezan`; `pyproject.toml` declares `license = "MIT"`; directories `.specify/` and `specs/` exist
- [ ] T046 [P] [US9] Create `.gitattributes` with the three lines above
- [ ] T047 [P] [US9] Create `LICENSE` with the standard MIT text, year 2026, holder `João Vitor Piovezan`
- [ ] T048 [US9] Edit `pyproject.toml`: `license = "MIT"`, `license-files = ["LICENSE"]`, `[build-system] requires = ["setuptools>=77"]`; run `uv lock` if needed and `uv sync --extra dev`

**Checkpoint**: Part B complete.

---

## Phase 12: User Story 10 - A README that is funny and technically honest (Priority: P2)

**Goal**: English README in the required section order, built from the code, with TODO placeholders for real LLM output.

**Independent Test**: Cross-check README against code; a test keeps the configuration table in sync with `Settings`.

- [ ] T049 [P] [US10] Unit test `tests/unit/test_readme.py`: every `Settings.model_fields` name, uppercased, appears in the README's "Configuration" table; every `UPPER_SNAKE` token in the first column of that table is a real setting; the H2 headings appear in the order from spec Story 10 scenario 1; every preset in `available_presets()` is mentioned; the README contains no `DOPAMINE_ACCESS_KEY`
- [ ] T050 [US10] Write `README.md` per spec Story 10 and research R16: title + tagline + badges (CI workflow badge for `joojdev/dopamine`, Python 3.11+, MIT); demo (GIF placeholder + curl example using a bearer token, real output as `<!-- TODO -->`); "What is this?"; "How it works" (Mermaid: request → catch-all → auth → agent → tools → respond → HTTP response; tool list from `build_tools`, with roles); "Quickstart" (≤3 commands: `uv sync`, `cp .env.example .env` + provider choice, `uv run uvicorn src.api.app:app`) plus admin/token steps; "Configuration" table generated from `Settings` (env var, default, description); "Personalities" (each preset with a one-line joke, how to add one); "Why you should never use this in production" (six risks, each with the real mitigation or "none"); "How it was built" (Spec Kit, link to `specs/`); "Contributing"; "License"
- [ ] T051 [US10] Compare the user's README brief with the code and list every difference found (to report in the completion summary per FR-036)

**Checkpoint**: Part C complete.

---

## Phase 13: Polish & Cross-Cutting Concerns

- [ ] T052 [P] Grep Part A artifacts for the project name: `grep -rin dopamine src/auth src/cli src/api/admin.py src/api/auth.py src/agent/roles.py` must return nothing; check the diff of modified Part A files adds no new occurrence (SC-006)
- [ ] T053 [P] Update `specs/003-cosmetic-features/quickstart.md` and `specs/001-project-boilerplate/quickstart.md` only where they tell users to set `DOPAMINE_ACCESS_KEY` (replace with token instructions)
- [ ] T054 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`; fix failures
- [ ] T055 Run the automated part of `specs/004-cleanup/quickstart.md`; mark completed tasks `[X]` in this file
- [ ] T056 Manual smoke with a real LLM only if `LLM_API_KEY` is available (one short pass): hash-password → login → create token → one catch-all request; record results; list the README TODO commands for the user

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (Phase 1) → Foundational (Phase 2) → Part A stories.
- **Part A**: US1 → US2 → US3 (US3 needs the admin token from US2 and the router from T022). US6 after US3 (audits issued tokens). US4 after US1 (needs `request.state.principal`). US5 after Phase 2 (only needs `TokenStore`/`hash_password`; T036 needs US3). US7 after US1.
- **Part B**: US8 and US9 depend only on Phase 1 (T001 for `uv.lock`); they can run in parallel with Part A, but `pyproject.toml` edits (T038, T042, T048) must be sequential.
- **Part C**: US10 after Parts A and B.
- Polish last.

### Within each story

Tests first (confirm FAIL) → modules → wiring into `app.py` → checkpoint.

### Parallel opportunities

- Phase 2: T004, T005, T006 together; then T008, T009, T010 together (T007 and T011 sequential).
- US1: T012–T015 together; T019 alongside implementation.
- US4: T029, T030, T031, T034 together.
- US9: T045–T047 together.
- Across parts: Part B (US8, US9) can be done by someone else while Part A is in progress.

## Parallel Example: Phase 2

```text
Task: "T005 TokenStore unit tests in tests/unit/test_token_store.py"
Task: "T006 password unit tests in tests/unit/test_passwords.py"
Task: "T008 src/auth/passwords.py"
Task: "T009 src/auth/tokens.py"
```

## Parallel Example: User Story 1

```text
Task: "T012 tests/unit/test_auth.py"
Task: "T013 tests/unit/test_redaction.py"
Task: "T014 tests/integration/test_auth_http.py"
Task: "T015 remove access-key tests"
```

## Implementation Strategy

### MVP first

1. Phases 1–2.
2. US1 (catch-all protected; tokens provisioned by code) → validate.
3. US2 + US3 (login and HTTP token management) → validate: the owner can issue tokens without touching code.

### Incremental delivery

- Part A: US1 → US2 → US3 → US6 → US4 → US5 → US7.
- Part B: US8 → US9 (any time after T001).
- Part C: US10 last.
- Commit after each story with the suite green.

### Notes

- Use low-cost argon2 parameters only in tests (`fast_hash`); production uses library defaults.
- The fake LLM cannot see tool lists through `bind_tools` unless recorded; T030 adds that recording in the test file, not in `conftest.py`.
