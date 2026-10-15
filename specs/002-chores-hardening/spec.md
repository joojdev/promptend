# Feature Specification: Chores Hardening

**Feature Branch**: `002-chores-hardening`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "chores — (1) redact sensitive request headers before they reach the agent; (2) protect the paid LLM call with a per-client rate limit and an optional access key; (3) make agent failures (no answer, loose text, timeout, provider outage, loop limit) visible to callers instead of masked as success or generic errors."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Client credentials never reach the LLM provider (Priority: P1)

An operator runs Dopamine in front of real clients. Clients send credentials (bearer tokens, cookies, API keys) in request headers. Today every header is forwarded to the agent and therefore to the external LLM provider. The operator needs those credential values stripped from what the agent sees, while the agent still knows the headers were present.

**Why this priority**: This is a credential leak to a third party. It is the most severe issue and the smallest to fix.

**Independent Test**: Send a request carrying `Authorization`, `Cookie`, `X-Api-Key`, `X-Custom-Token` and ordinary headers (`Content-Type`, `User-Agent`) to an app with a fake LLM. Inspect what the agent received.

**Acceptance Scenarios**:

1. **Given** a request with `Authorization: Bearer abc`, **When** it is handed to the agent, **Then** the agent sees header `authorization` with value `[REDACTED]` and the original value appears nowhere in the agent input.
2. **Given** a request with `Cookie`, `Set-Cookie`, `Proxy-Authorization` and `X-Api-Key` headers, **When** it is handed to the agent, **Then** each is present with value `[REDACTED]`.
3. **Given** a request with headers whose names contain "token", "secret" or "key" in any letter case (e.g. `X-Auth-Token`, `X-CLIENT-SECRET`, `My-Key-Id`), **When** it is handed to the agent, **Then** each value is `[REDACTED]`.
4. **Given** a request with `Content-Type` and `User-Agent`, **When** it is handed to the agent, **Then** both values are unchanged.
5. **Given** the operator overrides the sensitive-header configuration, **When** a request arrives, **Then** redaction follows the operator's list instead of the default.

---

### User Story 2 - Unwanted traffic cannot burn LLM budget (Priority: P2)

Every non-health request triggers a paid LLM call. Internet scanners (probing `/wp-admin`, `/.env`, etc.) would spend the owner's tokens. The operator needs a per-client request cap and an optional shared access key, both enforced before any LLM call.

**Why this priority**: It prevents direct financial loss, but the service remains functional without it, so it ranks below the credential leak.

**Independent Test**: With a fake LLM that counts invocations, send requests above the cap from one client, and requests with a missing or wrong key when a key is configured. Verify the rejection responses and that the invocation count stays at zero for rejected requests.

**Acceptance Scenarios**:

1. **Given** a per-minute limit of N, **When** one client sends N+1 requests inside a minute, **Then** the first N reach the agent and request N+1 gets 429 with body `{"error": "rate_limited"}` and the agent is not invoked.
2. **Given** two different clients and a limit of N, **When** client A exhausts its limit, **Then** client B is still served normally.
3. **Given** the limit window has elapsed, **When** the same client sends a new request, **Then** it is served again.
4. **Given** an access key is configured, **When** a request has no `X-Dopamine-Key` header or a different value, **Then** the response is 401 and the agent is not invoked.
5. **Given** an access key is configured and a request carries the matching `X-Dopamine-Key`, **When** it is handed to the agent, **Then** the request is served and the `X-Dopamine-Key` header does not appear in the agent input at all (not even as `[REDACTED]`).
6. **Given** no access key is configured, **When** any request arrives, **Then** behavior is as today (no key required).
7. **Given** limit exhausted or a key configured, **When** `/health` is requested without a key, **Then** it responds normally and does not count against the limit.

---

### User Story 3 - Agent failures are reported honestly (Priority: P3)

Callers and operators need to tell a successful answer from a failed one. Today an agent that gives no answer yields an empty 200, loose text is returned as a normal 200, a hung agent never times out, provider outages surface as generic 500s, and the loop limit is not distinguished.

**Why this priority**: It improves diagnosability and correctness of error semantics but does not leak data or cost money.

**Independent Test**: With a fake LLM scripted per scenario (no answer, loose text, hang, provider error, endless tool loop), send one request per scenario and check status code, error body and headers.

**Acceptance Scenarios**:

1. **Given** the agent finishes without calling a response tool and with no content, **When** the request completes, **Then** the response is 502 with a JSON error body naming the cause (`agent_no_response`).
2. **Given** the agent finishes with loose text and no response tool, **When** the request completes, **Then** the text is returned with status 200 as plain text and a header `X-Dopamine-Warning` stating the agent did not use a response tool.
3. **Given** the agent runs longer than the configured timeout (default 30 seconds), **When** the timeout elapses, **Then** the response is 504 with a JSON error body (`agent_timeout`) and the agent run is abandoned.
4. **Given** the provider reports a connection failure, authentication failure or provider-side rate limiting, **When** the request is processed, **Then** the response is 503 with the existing `llm_unavailable` body.
5. **Given** the agent hits the step limit without producing a response, **When** the request completes, **Then** the response is 500 with a JSON error body (`agent_loop_limit`) with a clear message.
6. **Given** any of the above, **When** the response is sent, **Then** no stack trace, provider message or credential appears in the body.

### Edge Cases

- Header names repeated or differently cased (`AUTHORIZATION`, `authorization`): all treated as the same sensitive header.
- A header like `Monkey` or `Keyboard-Layout` contains "key" and will be redacted; over-redaction is accepted (see Assumptions).
- Client IP behind a reverse proxy: all traffic would appear as the proxy's address; see Assumptions.
- Access-key comparison with a wrong key of different length must not leak timing information.
- Request with both a wrong key and an exhausted rate limit: authentication is checked first; rejected unauthenticated requests do not consume another client's quota.
- A request that is rejected (401/429/413) must never invoke the agent.
- Timeout fires while the agent is mid-tool-call: caller still gets 504 promptly.
- Loose text that is itself valid structured response JSON is treated as a structured response, not as loose text (existing behavior preserved).
- Body larger than the size limit still returns 413 before any of the new checks invoke the agent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST replace the value of every sensitive request header with the literal `[REDACTED]` before the request is given to the agent, keeping the header name present.
- **FR-002**: Sensitive headers by default MUST be: `authorization`, `proxy-authorization`, `cookie`, `set-cookie`, `x-api-key`, plus any header whose name contains `token`, `secret` or `key`, matched case-insensitively.
- **FR-003**: The sensitive-header list MUST be operator-configurable, with the defaults in FR-002 when unset.
- **FR-004**: Non-sensitive headers (e.g. `content-type`, `user-agent`) MUST be passed to the agent unchanged.
- **FR-005**: System MUST limit the number of requests per client per minute, with an operator-configurable limit (default 20 per minute).
- **FR-006**: A request over the limit MUST receive status 429 with body `{"error": "rate_limited"}` and MUST NOT invoke the agent.
- **FR-007**: Rate limiting MUST be tracked independently per client address and MUST NOT require external services or persistence.
- **FR-008**: When an access key is configured, System MUST require the `X-Dopamine-Key` header to equal it; otherwise respond 401 without invoking the agent. When no key is configured, no key is required.
- **FR-009**: The `X-Dopamine-Key` header MUST NOT appear in agent input, regardless of whether a key is configured.
- **FR-010**: The `/health` endpoint MUST be exempt from both rate limiting and access-key checks.
- **FR-011**: Access-key comparison MUST be constant-time.
- **FR-012**: The example environment file MUST document every new setting.
- **FR-013**: When the agent finishes with no response-tool call and no content, System MUST respond 502 with a JSON error body (`agent_no_response`).
- **FR-014**: When the agent finishes with loose text and no response-tool call, System MUST return that text with status 200 and an `X-Dopamine-Warning` header explaining that the agent did not use a response tool.
- **FR-015**: System MUST enforce an operator-configurable maximum agent run time (default 30 seconds); on expiry respond 504 with a JSON error body (`agent_timeout`).
- **FR-016**: Provider connection, authentication and rate-limit failures MUST be reported as the existing 503 `llm_unavailable` response.
- **FR-017**: When the agent reaches its step limit, System MUST respond 500 with a JSON error body (`agent_loop_limit`) and a clear message.
- **FR-018**: Error bodies for FR-013 to FR-017 MUST NOT expose stack traces, provider error text or secrets.
- **FR-019**: Dead error-handling code in the request path that only re-raises MUST be removed without changing behavior.
- **FR-020**: Each scenario in User Stories 1–3 MUST be covered by an automated test using a fake LLM, and the tests for rejected requests (401, 429) MUST assert the agent was not invoked.

### Key Entities

- **Sensitive header rule**: set of exact names plus name fragments, matched case-insensitively; determines which header values are masked.
- **Client quota**: per-client count of requests within the current one-minute window; resets as the window elapses.
- **Access key**: optional shared secret supplied by the operator and presented by callers in `X-Dopamine-Key`.
- **Agent outcome**: classification of an agent run as structured response, loose text, no response, timed out, provider unavailable or loop limit; determines the HTTP status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested requests, no sensitive header value appears anywhere in the text given to the LLM provider.
- **SC-002**: 100% of requests rejected for rate limit or missing/wrong key result in zero LLM invocations.
- **SC-003**: A single client sending sustained traffic can trigger at most the configured number of LLM calls per minute.
- **SC-004**: Each of the five agent-failure scenarios produces a distinct, documented status code and error code, so a caller or monitor can tell them apart without reading the body text.
- **SC-005**: No agent failure scenario returns a 2xx status except the explicit loose-text case, which always carries a warning header.
- **SC-006**: A stuck agent never holds a caller's connection longer than the configured timeout plus 2 seconds.
- **SC-007**: `/health` responds normally under rate-limit exhaustion and with an access key configured.

## Assumptions

- **Single bundle**: the three chores are specified together as one feature, delivered as three independently testable slices (P1 → P3).
- **Over-redaction accepted**: name-fragment matching ("key", "token", "secret") intentionally redacts some harmless headers; safety is preferred over precision. Operators can adjust via configuration.
- **Redaction applies to the agent input only**: the real header values stay available to the server itself (e.g. for the access-key check).
- **Rate-limit window**: a rolling or fixed one-minute window is acceptable; exact algorithm is a planning decision. Counters are in-memory, per process, and reset on restart.
- **Client identity**: the direct connection address is used. Deployments behind a reverse proxy will share one quota unless proxy-forwarded address handling is added later (out of scope).
- **Loose text decision**: loose text is kept as a 200 plain-text response with a warning header rather than failed with 502. Rationale: the text is usually a usable answer that only skipped the formal tool, failing would discard it, and the header keeps the deviation observable. Revisit if the warning shows up often.
- **Loop-limit status decision**: 500 with a specific `agent_loop_limit` error code, not 508. Rationale: 508 belongs to WebDAV and is poorly understood by proxies and clients; the error code in the body carries the specific meaning and 500 correctly signals a server-side fault.
- **Status for no response**: 502 chosen because the upstream "agent" gave an invalid (empty) result.
- **Defaults**: rate limit 20 requests/minute; agent timeout 30 seconds; access key unset (open).
- **Lightweight implementation**: no new heavy dependency is added for rate limiting; a small in-house in-memory approach is sufficient for a single-process service, and a lightweight library is acceptable if it removes real complexity (to be justified in the plan).
- **Order of checks**: body-size limit, then access key, then rate limit, then agent invocation; `/health` bypasses all.
- **Out of scope**: persistent or distributed rate limiting, per-key quotas, key rotation, redaction of the request body or query string, response redaction.
