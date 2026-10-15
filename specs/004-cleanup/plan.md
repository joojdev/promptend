# Implementation Plan: Cleanup

**Branch**: `004-cleanup` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-cleanup/spec.md`

## Summary

Three independent parts:

1. **Admin login, user tokens, role-scoped tools (A)**: a new `src/auth/` package with an argon2 admin verifier (timing-safe for wrong usernames) and a SQLite `TokenStore` (SHA-256-hashed `sk_` user tokens and expiring `adm_` admin tokens), shared by a new `/_admin/` router (login, create/list/revoke tokens, 404 fallback) and a `tokens` CLI. The catch-all authenticates `Authorization: Bearer` before the rate limit and picks one of two pre-built agents by role; tools declare `role = "admin"`, and only admin runs are offered them. The shared `DOPAMINE_ACCESS_KEY` is removed, and `Authorization`/`X-API-Key` are stripped from the agent input.
2. **CI and hygiene (B)**: a GitHub Actions matrix (3.11, 3.12) running `ruff check`, `ruff format --check` and `pytest` with uv; ruff excludes the vendored `.specify/` and `.claude/`; `.gitattributes`, MIT `LICENSE`, license metadata, `data/` ignored.
3. **README (C)**: an English README built from the code, with a test that keeps its configuration table in sync with `Settings`.

Constitution amended to v1.3.0 (control-plane routes, role-scoped tools) before design.

## Technical Context

**Language/Version**: Python 3.11+ (CI 3.11 and 3.12; local venv 3.13)

**Primary Dependencies**: existing (`fastapi`, `langgraph`, `langchain-core`, `pydantic-settings`, `structlog`) plus **`argon2-cffi>=25.1`** (only new runtime dependency). Stdlib: `sqlite3`, `secrets`, `hashlib`, `hmac`, `getpass`, `argparse`.

**Storage**: SQLite file `TOKENS_DB_PATH` (default `data/tokens.db`, WAL mode); existing KV store unchanged.

**Testing**: `pytest`, `TestClient`, `CountingFakeLLM` / `make_queued_llm` from `tests/conftest.py`, `capsys` for the CLI, `tmp_path` stores. Argon2 hashes in tests use low-cost parameters for speed.

**Target Platform**: Linux server, single process; CLI on the same host.

**Project Type**: Web service + small CLI.

**Performance Goals**: Per-request token check = one indexed SQLite read (+ one write for `last_used_at` on user tokens); login ~50 ms argon2, off the event loop.

**Constraints**: No agent call on any `/_admin/` route or any 401. No plain password in config. No project name in Part A artifacts. Existing tests keep passing via a shared fixture.

**Scale/Scope**: One admin, tens of user tokens.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution **v1.3.0** (amended in this plan). Under v1.2.0 the `/_admin/` 2xx responses violated Principle I ("guards MUST NOT generate successful responses"), and per-role tool sets had no basis; v1.3.0 adds the "Control plane" and "Role-scoped tools" paragraphs.

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Every request through the agent | ✅ PASS (v1.3.0) | Only `/health` and `/_admin/` (control plane: login + token management) answer without the agent; tests assert zero LLM calls. Catch-all 401 is an existing-style guard. |
| I. Tools are the only extension point | ✅ PASS | No agent behavior added outside tools; role only filters which tools are bound. |
| I. Role-scoped tools | ✅ PASS (v1.3.0) | Role declared on the tool; filtering before binding; no routing/auth change to add a tool. |
| II. Customizable Personality | ✅ PASS | Untouched; both role agents share the resolved personality. |
| III. Test-First | ✅ PASS | Tasks order failing tests first; `TokenStore`, verifier and `tools_for_role` tested in isolation. |
| IV. Simplicity / YAGNI | ✅ PASS | Stdlib SQLite, no ORM, no JWT library, no logout/refresh, no shipped admin tool. Two agents instead of a custom graph. |
| Config: `BaseSettings`, `.env`, ruff, 3.11+ | ✅ PASS | Six settings added, one removed; CLI uses a minimal `BaseSettings`. CI enforces ruff on 3.11/3.12. |
| Config: no conversation memory | ✅ PASS | Unchanged. |

**Post-Design Re-check**: ✅ All gates pass under v1.3.0. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/004-cleanup/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── admin-api.md
│   ├── catch-all-auth.md
│   └── cli-and-config.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
src/
├── auth/                    # NEW
│   ├── __init__.py
│   ├── passwords.py         # validate_hash, hash_password, AdminVerifier (argon2, dummy hash)
│   └── tokens.py            # TokenStore (SQLite), IssuedToken, TokenRecord
├── agent/
│   ├── roles.py             # NEW: ROLES, tool_role, tools_for_role
│   ├── registry.py          # build_tools unchanged in shape; doc comment on role
│   └── harness.py           # load_harness(..., role="user") → tools_for_role(build_tools(store), role)
├── api/
│   ├── admin.py             # NEW: build_admin_router (login, tokens CRUD, 404 fallback, disabled gate)
│   ├── auth.py              # NEW: Principal, parse_bearer, authenticate
│   ├── app.py               # include admin router first; agents per role; auth before rate limit;
│   │                        #   startup checks (hash validity, warnings); access-key check removed
│   ├── errors.py            # 401 body {"error":"unauthorized"}; + NotFoundError → 404
│   └── guards.py            # redact_headers drops authorization/x-api-key; check_access_key removed
├── cli/                     # NEW
│   ├── __init__.py
│   └── tokens.py            # argparse: create / list [--all] / revoke / hash-password; --db
└── config/
    └── settings.py          # + admin_*, login_rate_limit_per_minute, tokens_db_path, auth_enabled;
                             #   − dopamine_access_key

tests/
├── conftest.py              # autouse: TOKENS_DB_PATH=tmp, AUTH_ENABLED=false; admin/user token helpers
├── unit/
│   ├── test_passwords.py
│   ├── test_token_store.py
│   ├── test_roles.py
│   ├── test_cli_tokens.py
│   ├── test_readme.py
│   ├── test_redaction.py    # updated (removal of authorization/x-api-key)
│   ├── test_startup.py      # updated settings
│   └── test_access_key.py   # DELETED
└── integration/
    ├── test_admin_http.py
    ├── test_auth_http.py
    ├── test_tool_roles_http.py
    └── test_guards_http.py  # access-key cases removed

.github/workflows/ci.yml     # NEW
.gitattributes               # NEW
LICENSE                      # NEW (MIT, João Vitor Piovezan, 2026)
README.md                    # NEW
pyproject.toml               # argon2-cffi, [project.scripts] tokens, license, ruff extend-exclude, setuptools>=77
uv.lock                      # regenerated by `uv add`
.gitignore                   # + data/
.env.example                 # + auth settings, − DOPAMINE_ACCESS_KEY
```

**Structure Decision**: Single project. Credential logic lives once in `src/auth/` (FR-022) and is imported by both `src/api/admin.py` and `src/cli/tokens.py`. Role logic is a tiny `src/agent/roles.py` so the harness change stays one line. No module or setting name contains the project name.

## Complexity Tracking

No violations. The two Principle I extensions were resolved by the v1.3.0 amendment.
