# Contract: Catch-all Authentication and Tool Roles

## Header

`Authorization: Bearer <token>` — scheme case-insensitive, exactly one non-empty token. `X-API-Key` is not an auth header.

## Decision table (catch-all, any method, any path except `/health` and `/_admin/...`)

| `AUTH_ENABLED` | Token | Result |
|----------------|-------|--------|
| true | valid user token | agent runs with **user** tools; token `last_used_at` updated |
| true | valid, unexpired admin token | agent runs with **admin** tools |
| true | missing, non-Bearer, empty, unknown, revoked user, expired admin | `401 {"error": "unauthorized"}`, agent not invoked, rate-limit budget not consumed |
| false | valid admin token | admin tools |
| false | anything else (including none) | user tools |

Guard order: body size (413) → auth (401) → rate limit (429) → agent.

`/health`: always public, no auth.

## Agent input

`Authorization` and `X-API-Key` are removed (name and value) from the headers sent to the agent in every case above. Other sensitive headers keep the existing `[REDACTED]` masking. `X-Dopamine-Key` has no special meaning any more.

## Tool roles

| Tool declares | Offered to admin runs | Offered to user runs |
|---------------|----------------------|----------------------|
| nothing | yes | yes |
| `role = "user"` | yes | yes |
| `role = "admin"` | yes | **no** (not in the model's tool list) |
| anything else | startup fails: `Error: tool '<name>' declares unknown role '<role>'` |

### Adding a role-restricted tool

1. Define a `BaseTool` subclass with `role: str = "admin"` (or `"user"`).
2. Add an instance to `build_tools()` in `src/agent/registry.py`.

No change to routes, auth or the harness.
