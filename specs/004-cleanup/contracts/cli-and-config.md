# Contract: `tokens` CLI and Configuration

## CLI

Invocation: `tokens <command>` (installed script) or `python -m src.cli.tokens <command>`. Global option `--db PATH` overrides the store path. Store path otherwise from `TOKENS_DB_PATH` (env or `.env`), default `data/tokens.db`. Needs no LLM settings and no running server.

| Command | Output | Exit |
|---------|--------|------|
| `create <name>` | `Created token #3 "mobile app"`, the full `sk_…` token on its own line, then `Store it now: it will not be shown again.` | 0; blank name → 2 (argparse) or 1 with message |
| `list` | table: `ID  NAME  PREFIX  CREATED AT  LAST USED  STATUS` for active user tokens; `--all` adds revoked rows (`STATUS` = `active`/`revoked`); `No tokens.` when empty | 0 |
| `revoke <id>` | `Revoked token #3.` | 0; unknown id → `Token #3 not found.` on stderr, exit 1 |
| `hash-password` | prompts `Password:` and `Repeat password:` (no echo), prints the `$argon2id$…` hash | 0; mismatch or empty → message on stderr, nothing on stdout, exit 1 |

## Settings (documented in `.env.example`)

| Variable | Default | Notes |
|----------|---------|-------|
| `ADMIN_USERNAME` | *(unset)* | Admin routes return 404 while unset |
| `ADMIN_PASSWORD_HASH` | *(unset)* | argon2 hash from `tokens hash-password`; never the plain password |
| `ADMIN_TOKEN_TTL_MINUTES` | `60` | > 0 |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `5` | > 0 |
| `TOKENS_DB_PATH` | `data/tokens.db` | `data/` is git-ignored |
| `AUTH_ENABLED` | `true` | `false` only for local development |
| ~~`DOPAMINE_ACCESS_KEY`~~ | — | removed |

## Startup messages

| Condition | Effect |
|-----------|--------|
| `ADMIN_PASSWORD_HASH` set but invalid | stderr `Configuration error: ADMIN_PASSWORD_HASH is not a valid argon2 hash`, exit 1 (value not printed) |
| Admin credentials blank | warning log `admin_routes_disabled` |
| `AUTH_ENABLED=false` | warning log `auth_disabled` |
| Tool with unknown role | stderr `Error: tool '<name>' declares unknown role '<role>'`, exit 1 |
