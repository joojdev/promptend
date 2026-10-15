# Contract: Usage Headers and Request Log

Applies to every request handled by the catch-all route that passes the guards (body size, access key, rate limit).

## Headers

| Header | Type | Present when |
|--------|------|--------------|
| `X-Dopamine-Tokens-In` | non-negative integer | Always on agent-run responses |
| `X-Dopamine-Tokens-Out` | non-negative integer | Always on agent-run responses |
| `X-Dopamine-Steps` | non-negative integer | Always on agent-run responses |
| `X-Dopamine-Cost-USD` | decimal string, exactly 6 decimal places | Both `LLM_PRICE_INPUT_PER_MTOK` and `LLM_PRICE_OUTPUT_PER_MTOK` set |

Definitions:

- **Tokens-In / Tokens-Out**: sum of `input_tokens` / `output_tokens` reported by the provider for every LLM call the agent made for this request. A call with no reported usage counts 0.
- **Steps**: number of tool calls emitted by the model in this request, including the final `respond` / `respond_with_file` call.
- **Cost-USD**: `tokens_in × LLM_PRICE_INPUT_PER_MTOK / 1e6 + tokens_out × LLM_PRICE_OUTPUT_PER_MTOK / 1e6`, rounded half-up to 6 places.

## Which responses carry them

| Response | Usage headers |
|----------|---------------|
| Agent reply via `respond` / `respond_with_file` (any status) | Yes |
| Loose-text reply (`X-Dopamine-Warning`) | Yes |
| `502 agent_no_response` | Yes |
| `504 agent_timeout` | Yes (usage up to the timeout) |
| `500 agent_loop_limit` | Yes |
| `503 llm_unavailable` | Yes (usually 0 tokens) |
| `500 internal_error` raised during the agent run | Yes |
| `413`, `401`, `429` guard rejections | No |
| `GET /health` | No |

## Precedence

If the agent's `respond` call sets any of the four header names in any letter case, those entries are removed and replaced by the system values. When cost is not configured, an agent-set `X-Dopamine-Cost-USD` is removed and not replaced.

## CORS

The four headers are listed in `Access-Control-Expose-Headers`.

## Example

Fake LLM: call 1 uses 100 in / 20 out and calls `kv_get`; call 2 uses 150 in / 30 out and calls `respond`. Prices 3.00 / 15.00.

```http
HTTP/1.1 200 OK
content-type: application/json
x-dopamine-tokens-in: 250
x-dopamine-tokens-out: 50
x-dopamine-steps: 2
x-dopamine-cost-usd: 0.001500
```

## Request log

Event `request` (JSON, structlog), emitted once per agent-run request on success and on agent failure:

```json
{"event": "request", "method": "GET", "path": "/users", "status": 200,
 "tokens_in": 250, "tokens_out": 50, "steps": 2, "cost_usd": "0.001500",
 "timestamp": "..."}
```

`cost_usd` is omitted when prices are not configured.
