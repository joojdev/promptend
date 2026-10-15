# HTTP Contract: Guards and Agent Failures

Applies to every path except `/health`. Error bodies are JSON (`application/json`) and never contain stack traces, provider error text or secrets.

## Request headers

| Header | Behavior |
|--------|----------|
| `X-Dopamine-Key` | Required only when `DOPAMINE_ACCESS_KEY` is set. Never forwarded to the agent. |
| Sensitive headers (see data-model) | Forwarded to the agent with value `[REDACTED]`. |
| All others | Forwarded unchanged. |

## Responses

| Status | `error` | When | Agent invoked? |
|--------|---------|------|----------------|
| 401 | `unauthorized` | Access key configured and header missing/wrong | No |
| 413 | `request_too_large` | Body over `MAX_REQUEST_BODY_SIZE` (existing) | No |
| 429 | `rate_limited` | Client exceeded `RATE_LIMIT_PER_MINUTE` | No |
| 502 | `agent_no_response` | Agent finished with no response tool call and no text | Yes |
| 504 | `agent_timeout` | Agent exceeded `AGENT_TIMEOUT_SECONDS` | Yes |
| 503 | `llm_unavailable` | Provider connection, authentication or rate-limit failure (existing body) | Yes |
| 500 | `agent_loop_limit` | Agent hit the step limit without responding | Yes |
| 500 | `internal_error` | Any other unexpected failure (existing) | Yes |
| 200 | — | Normal agent response, or loose text with `X-Dopamine-Warning` | Yes |

### Bodies

```json
{"error": "rate_limited"}
```

```json
{"error": "unauthorized", "message": "Missing or invalid access key."}
```

```json
{"error": "agent_no_response", "message": "The agent finished without producing a response."}
```

```json
{"error": "agent_timeout", "message": "The agent did not respond in time."}
```

```json
{"error": "agent_loop_limit", "message": "The agent exceeded its step limit without producing a response."}
```

The 429 body is exactly `{"error": "rate_limited"}` as specified; other bodies add a `message` field for consistency with existing handlers.

### Loose-text response

Status 200, `Content-Type: text/plain`, body = the agent's text, plus:

```text
X-Dopamine-Warning: agent did not use a response tool
```

### Check order

1. Body size → 413
2. Access key → 401
3. Rate limit → 429
4. Agent invocation → outcomes above

`/health` bypasses steps 1–3 (separate route).
