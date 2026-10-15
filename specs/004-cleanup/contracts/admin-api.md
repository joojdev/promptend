# Contract: Admin API (`/_admin/`)

All routes: JSON in/out, never invoke the agent, no usage headers. When `ADMIN_USERNAME` or `ADMIN_PASSWORD_HASH` is blank, **every** path under `/_admin/` returns `404 {"error": "not_found"}`.

## `POST /_admin/login`

Request: `{"username": "<str, min 1>", "password": "<str, min 1>"}`

| Case | Status | Body |
|------|--------|------|
| Correct credentials | 200 | `{"token": "adm_…", "token_type": "bearer", "expires_at": "2026-10-15T13:00:00+00:00"}` |
| Wrong username or password | 401 | `{"error": "unauthorized"}` |
| Missing/empty field, bad JSON | 422 | FastAPI validation body |
| More than `LOGIN_RATE_LIMIT_PER_MINUTE` attempts from one client in 60 s | 429 | `{"error": "rate_limited"}` (credentials not checked) |

## Token management — `Authorization: Bearer <admin token>` required

Any missing/malformed header, unknown, expired or revoked token, or a **user** token → `401 {"error": "unauthorized"}`.

### `POST /_admin/tokens`

Request: `{"name": "<str, min 1>"}` → `201`

```json
{"id": 3, "name": "mobile app", "prefix": "sk_Ab3dE", "token": "sk_Ab3dE…", "created_at": "2026-10-15T12:00:00+00:00"}
```

Empty/missing name → 422, nothing created.

### `GET /_admin/tokens` → `200`

```json
[{"id": 3, "name": "mobile app", "prefix": "sk_Ab3dE", "created_at": "…", "last_used_at": null, "revoked": false}]
```

User tokens only, revoked included, ordered by id. Never contains `token` or a hash.

### `DELETE /_admin/tokens/{id}`

| Case | Status |
|------|--------|
| Existing user token (active or already revoked) | 204, no body |
| Unknown id or an admin token's id | 404 `{"error": "not_found"}` |

## Anything else under `/_admin/`

Unknown sub-path or unsupported method → `404 {"error": "not_found"}` (or 405 from the framework on a known path). Never reaches the catch-all.
