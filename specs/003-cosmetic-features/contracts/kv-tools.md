# Contract: Key-Value Storage Tools

Agent-facing tools. Each returns a JSON string on success. Errors are raised as `ToolException` and delivered to the model as a `ToolMessage` with `status="error"` (`handle_tool_error=True`); they never abort the request and never change the store.

Common key rule: string, 1–256 characters. Violation → error `invalid key: must be a string of 1-256 characters`.

## `kv_set(key, value)`

Stores `value` (string, number, boolean, null, list or object) under `key`, replacing any previous value.

| Case | Result |
|------|--------|
| New key | `{"ok": true, "key": "users/1", "created": true}` |
| Existing key | `{"ok": true, "key": "users/1", "created": false}` |
| Serialized value > `KV_MAX_VALUE_BYTES` | error `value too large: 70000 bytes exceeds KV_MAX_VALUE_BYTES (65536)` |
| New key while `KV_MAX_KEYS` keys stored | error `store full: KV_MAX_KEYS (1000) reached; delete keys or overwrite an existing one` |
| `STATE_FILE` write fails | error `storage write failed`; failure logged with `kv_save_failed` |

## `kv_get(key)`

| Case | Result |
|------|--------|
| Present | `{"found": true, "key": "users/1", "value": {"name": "Ana"}}` |
| Missing | `{"found": false, "key": "users/9"}` |

## `kv_list(prefix="")`

`{"prefix": "users/", "keys": ["users/1", "users/2"]}` — every key starting with `prefix`, sorted ascending. Empty prefix lists all keys.

## `kv_delete(key)`

| Case | Result |
|------|--------|
| Present | `{"deleted": true, "key": "users/1"}` |
| Missing | `{"deleted": false, "key": "users/9"}` |
| `STATE_FILE` write fails | error `storage write failed` (key kept) |

## Persistence (`STATE_FILE`)

- Unset: memory only; empty on every start.
- Set, file missing: start empty; file created on first successful `kv_set`/`kv_delete`.
- Set, file valid: loaded at startup.
- Set, file invalid (bad JSON, root not an object): startup exits 1 with `Error: invalid state file <path>: <reason>`; file untouched.
- Every successful mutation is saved atomically before the tool returns.

## Programmatic instructions (added section)

The system prompt gains a `## Storage` section stating:

- Storage is shared across all requests and is the only memory between requests.
- When a request creates, updates or deletes a resource, write the change with `kv_set` / `kv_delete` before responding.
- Before answering a read (`GET`), look the data up with `kv_get` / `kv_list`; do not invent data that contradicts what is stored.
- Use keys shaped `<collection>/<id>` (e.g. `users/42`) so `kv_list("users/")` lists a collection.
- `found: false` is a normal outcome (typically 404), not an error.
- Storage errors (too large, full) should be reported to the caller with an appropriate status (e.g. 413, 507), still via `respond`.
