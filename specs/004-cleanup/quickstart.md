# Quickstart: Validating Cleanup

## Prerequisites

- `uv sync --extra dev` (pulls `argon2-cffi`).
- `.env` with `LLM_MODEL` and `LLM_API_KEY` (any values for automated tests).

## Automated validation

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

| Part | What the tests prove |
|------|----------------------|
| A | login success/failure/422/429/disabled-404/invalid hash; admin token expiry; token create/list/revoke over HTTP and CLI against one store; user token rejected on admin routes; catch-all decision table ([contracts/catch-all-auth.md](contracts/catch-all-auth.md)) with zero LLM calls on 401; `Authorization`/`X-API-Key` absent from the agent prompt; raw DB file contains no full token; admin-only test tool offered to admin runs only; unknown tool role exits 1 |
| B | `ruff` clean; `.gitattributes`, `LICENSE`, `data/` ignore present |
| C | every `Settings` env name appears in the README configuration table |

## Manual smoke (real server, optional real LLM)

```bash
uv run tokens hash-password                 # paste result into .env as ADMIN_PASSWORD_HASH
# .env: ADMIN_USERNAME=admin
uv run uvicorn src.api.app:app

curl -s -X POST localhost:8000/_admin/login -H 'content-type: application/json' \
     -d '{"username":"admin","password":"<pw>"}'                    # → {"token":"adm_…"}
curl -s -X POST localhost:8000/_admin/tokens -H "authorization: Bearer $ADM" \
     -H 'content-type: application/json' -d '{"name":"me"}'          # → {"token":"sk_…"}
curl -i localhost:8000/hello                                        # → 401
curl -i localhost:8000/hello -H "authorization: Bearer $SK"         # → agent reply
uv run tokens list
uv run tokens revoke 1 && curl -i localhost:8000/hello -H "authorization: Bearer $SK"   # → 401
```

CI: push the branch and check the "CI" workflow is green on 3.11 and 3.12.

Details: [contracts/admin-api.md](contracts/admin-api.md), [contracts/cli-and-config.md](contracts/cli-and-config.md), [data-model.md](data-model.md).
