# Data Model: Cleanup

## Settings changes (`src/config/settings.py::Settings`)

| Field | Env var | Type | Default | Validation |
|-------|---------|------|---------|------------|
| `admin_username` | `ADMIN_USERNAME` | `str` | `""` | stripped; blank = admin routes disabled |
| `admin_password_hash` | `ADMIN_PASSWORD_HASH` | `str` | `""` | stripped; blank = disabled; format checked at startup outside pydantic so the value is never printed |
| `admin_token_ttl_minutes` | `ADMIN_TOKEN_TTL_MINUTES` | `int` | `60` | `> 0` |
| `login_rate_limit_per_minute` | `LOGIN_RATE_LIMIT_PER_MINUTE` | `int` | `5` | `> 0` |
| `tokens_db_path` | `TOKENS_DB_PATH` | `str` | `"data/tokens.db"` | non-empty |
| `auth_enabled` | `AUTH_ENABLED` | `bool` | `True` | — |
| ~~`dopamine_access_key`~~ | ~~`DOPAMINE_ACCESS_KEY`~~ | — | — | **removed** |

Property `admin_enabled -> bool`: both admin fields non-blank.

`TokenSettings(BaseSettings)` (CLI only, `src/cli/tokens.py`): `tokens_db_path: str = "data/tokens.db"`, same `.env` loading, `extra="ignore"`.

## Token record (SQLite table `tokens` in `TOKENS_DB_PATH`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | short, typed in the CLI |
| `role` | `TEXT NOT NULL CHECK (role IN ('admin','user'))` | |
| `name` | `TEXT NOT NULL` | user tokens: given name; admin tokens: `"admin login"` |
| `token_hash` | `TEXT NOT NULL UNIQUE` | SHA-256 hex of the full token |
| `prefix` | `TEXT NOT NULL` | first 8 chars, e.g. `sk_Ab3dE` |
| `created_at` | `TEXT NOT NULL` | UTC ISO-8601 |
| `last_used_at` | `TEXT` | NULL until first use (user tokens) |
| `expires_at` | `TEXT` | admin tokens only; NULL for user tokens |
| `revoked` | `INTEGER NOT NULL DEFAULT 0` | 0/1 |

Never stored: full tokens, the admin password.

### State transitions

User token: `active` → (`revoke`) → `revoked` (terminal; revoke again = no-op).
Admin token: `active` → (time passes `expires_at`) → `expired` → purged on the next login.

## TokenStore (`src/auth/tokens.py`)

| Method | Returns | Notes |
|--------|---------|-------|
| `create_user_token(name)` | `IssuedToken(id, name, prefix, token, created_at)` | blank name → `ValueError` |
| `issue_admin_token(ttl_minutes)` | `IssuedToken(..., expires_at)` | purges expired admin rows first |
| `authenticate(token)` | `TokenRecord \| None` | valid = known hash, not revoked, not expired; updates `last_used_at` for user tokens |
| `list_user_tokens(include_revoked=True)` | `list[TokenRecord]` | no hash, no full token; ordered by id |
| `revoke_user_token(id)` | `bool` | False when no user token has that id |

`TokenRecord`: `id, role, name, prefix, created_at, last_used_at, expires_at, revoked` (frozen dataclass, `to_public_dict()` for JSON).

## AdminCredentials (`src/auth/passwords.py`)

| Member | Notes |
|--------|-------|
| `validate_hash(hash) -> None` | raises `InvalidAdminHash` (no value in the message) |
| `hash_password(password) -> str` | argon2id encoded |
| `AdminVerifier(username, password_hash)` | holds the dummy hash; `verify(username, password) -> bool` constant-shape per R2 |

## Principal (`src/api/auth.py`)

`Principal(role: "admin" | "user", token_id: int | None)`; anonymous user (auth disabled, no token) has `token_id=None`.

## Tool role (`src/agent/roles.py`)

`ROLES = ("user", "admin")`. A tool's role is `getattr(tool, "role", "user")`. `tools_for_role(tools, role) -> list[BaseTool]`:

| Caller role | Offered tools |
|-------------|---------------|
| `admin` | all registered tools |
| `user` | tools whose role is `user` |

Unknown tool role → exit 1 at startup.

## Agents per role (`src/api/app.py`)

`_agents: dict[str, CompiledGraph]` built in the lifespan, one per entry of `ROLES`, sharing the LLM, KV store and system prompt. The catch-all uses `_agents[principal.role]`.
