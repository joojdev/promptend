# Feature Specification: Cosmetic Features

**Feature Branch**: `003-cosmetic-features`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "Three improvements that make Dopamine feel like a real (and really expensive) backend. (A) Personality presets: config/personality.md is just 'You are a helpful assistant.' Ship config/personalities/ with at least 4 funny markdown presets (default, shop, sarcastic, website, teapot). New PERSONALITY setting resolves to config/personalities/<name>.md; PERSONALITY_PATH keeps working and wins when set; every preset respects the programmatic instructions (always end with respond); an invalid preset name fails startup listing the available ones. (B) Agent state: the agent is stateless, so POST /users then GET /users remembers nothing. Add key-value tools (kv_set, kv_get, kv_list(prefix), kv_delete), in-memory by default with optional JSON file persistence (STATE_FILE) written atomically, configurable limits on value size and key count, PROGRAMMATIC_INSTRUCTIONS explaining when to use storage, tools registered in the registry. (C) Usage reporting: sum input/output tokens over all agent LLM calls in a request, return X-Dopamine-Tokens-In, X-Dopamine-Tokens-Out, X-Dopamine-Steps (tool calls), optionally X-Dopamine-Cost-USD from user-configured per-token prices (no hardcoded price table), and include the numbers in the structured request log. Acceptance: preset resolution/error tests (no LLM behavior tests); KV tool unit tests plus an integration test with a fake LLM doing kv_set in one request and kv_get in the next; a fake-LLM test with known usage_metadata checking the headers."

## User Scenarios & Testing *(mandatory)*

The feature has three independent parts. Each part's stories can be built, tested and shipped on their own.

- **Part A — Personality presets**: Stories 1–4
- **Part B — Agent state**: Stories 5–7
- **Part C — Usage reporting**: Stories 8–9

### User Story 1 - Pick a ready-made personality by name (Priority: P1)

Someone who just cloned Dopamine wants to see the joke land without writing a prompt. They set one configuration value to a preset name (e.g. `shop`) and start the server; the agent now behaves as that preset's fake API.

**Why this priority**: The personality is the point of the project. Without name-based selection the presets are files nobody uses.

**Independent Test**: With a fake LLM, start the app with `PERSONALITY=shop` and confirm the agent's system prompt starts with the `shop` preset content, followed by the programmatic instructions.

**Acceptance Scenarios**:

1. **Given** `PERSONALITY=shop` and no `PERSONALITY_PATH`, **When** the server starts, **Then** the agent's system prompt is the `shop` preset content followed by the programmatic instructions.
2. **Given** neither `PERSONALITY` nor `PERSONALITY_PATH` is set, **When** the server starts, **Then** the `default` preset is used.
3. **Given** `PERSONALITY=Shop` or `PERSONALITY= shop ` (different case or surrounding whitespace), **When** the server starts, **Then** the `shop` preset is used.
4. **Given** the server started with a preset, **When** it logs its startup event, **Then** the log names the preset and the resolved file.

---

### User Story 2 - A custom personality file still wins (Priority: P1)

An existing user already points `PERSONALITY_PATH` at their own prompt file. Upgrading must not change which personality they get.

**Why this priority**: Breaking the existing customization path would be a regression for every current user.

**Independent Test**: Start the app with both `PERSONALITY=teapot` and `PERSONALITY_PATH=<tmp file>`; confirm the tmp file's content is used.

**Acceptance Scenarios**:

1. **Given** `PERSONALITY_PATH` points to an existing file and `PERSONALITY` is also set, **When** the server starts, **Then** the file at `PERSONALITY_PATH` is used and `PERSONALITY` is ignored.
2. **Given** `PERSONALITY_PATH` points to a missing file, **When** the server starts, **Then** startup fails with a message naming that path (existing behavior), even if `PERSONALITY` names a valid preset.
3. **Given** `PERSONALITY_PATH` is set to an empty string, **When** the server starts, **Then** it is treated as not set and preset resolution applies.

---

### User Story 3 - A typo in the preset name fails loudly and helpfully (Priority: P2)

An operator mistypes the preset (`PERSONALITY=sarcatic`). The server must refuse to start and say which names are valid, instead of silently falling back.

**Why this priority**: Prevents confusing runs, but only matters once Story 1 exists.

**Independent Test**: Start the app with `PERSONALITY=nope`; assert a non-zero exit and that the error output lists every available preset name.

**Acceptance Scenarios**:

1. **Given** `PERSONALITY=nope`, **When** the server starts, **Then** it exits with a non-zero status and the error message contains `nope` and the sorted list of available preset names (e.g. `default, sarcastic, shop, teapot, website`).
2. **Given** `PERSONALITY=../secrets` or any value containing a path separator or `..`, **When** the server starts, **Then** it is rejected as an invalid preset name with the same listing, and no file outside the presets directory is read.
3. **Given** the presets directory is empty or missing and no `PERSONALITY_PATH` is set, **When** the server starts, **Then** it exits with a clear error saying no presets were found and where it looked.

---

### User Story 4 - Presets are funny and stay inside the rules (Priority: P2)

Each shipped preset defines a distinct fake "API" with a recognizable character, and none of them contradicts the programmatic instructions (every reply ends by calling a response tool; no bare text replies).

**Why this priority**: The presets are the product's content, but their quality can only be checked by hand. Tests cover their structure.

**Independent Test**: For every file in the presets directory, check it is non-empty Markdown and contains no wording that tells the agent to bypass the response tools. A manual run per preset confirms the tone.

**Acceptance Scenarios**:

1. **Given** the shipped presets, **When** listed, **Then** at least `default`, `shop`, `sarcastic`, `website` and `teapot` exist.
2. **Given** the `default` preset, **When** compared with the previous `config/personality.md`, **Then** it has the same neutral helpful-assistant character.
3. **Given** the `shop` preset, **When** used, **Then** it describes an online store that invents absurd products with prices and stock, answering in JSON consistent with REST conventions (collections, item lookup by id, 201 on create, 404 for unknown items) and keeping its catalog consistent through the agent's storage (Part B).
4. **Given** the `sarcastic` preset, **When** used, **Then** it describes an API whose data and status codes are technically correct while its human-readable messages are passive-aggressive.
5. **Given** the `website` preset, **When** used, **Then** it describes generating a complete HTML page for any path, replied with an HTML content type instead of JSON.
6. **Given** the `teapot` preset, **When** used, **Then** it describes answering 418 to every request with a philosophical justification (`/health` and infrastructure guards are outside the agent and unaffected).
7. **Given** any preset, **When** read, **Then** it covers character and tone only: status codes or content types it mentions are what the character wants, delivered through the response tools.

---

### User Story 5 - The fake backend remembers what you created (Priority: P1)

A client sends `POST /users` with a body, then `GET /users`. Today the second request knows nothing about the first, which breaks the illusion of a backend. The agent needs a shared key-value store it can write to in one request and read from in a later one.

**Why this priority**: This is the biggest gap between Dopamine and a believable backend; it applies to every personality.

**Independent Test**: With a fake LLM scripted to call `kv_set` in request 1 and `kv_get` in request 2, check that request 2's response contains the value written in request 1. Each storage tool is also tested directly, without an agent.

**Acceptance Scenarios**:

1. **Given** an empty store, **When** `kv_set("users/1", {"name": "Ana"})` runs, **Then** it reports success and `kv_get("users/1")` returns `{"name": "Ana"}`.
2. **Given** a key that was never set, **When** `kv_get` is called on it, **Then** it reports "not found" (a normal result the agent can act on, e.g. by replying 404), not an error that aborts the request.
3. **Given** keys `users/1`, `users/2` and `orders/1`, **When** `kv_list("users/")` runs, **Then** it returns `users/1` and `users/2` in sorted order and not `orders/1`; `kv_list("")` returns all keys.
4. **Given** an existing key, **When** `kv_delete` is called on it, **Then** it reports the key was deleted and `kv_get` then reports "not found"; deleting a missing key reports "not found" and does not fail.
5. **Given** an existing key, **When** `kv_set` is called with a new value, **Then** the value is replaced.
6. **Given** request 1 runs `kv_set` and responds, **When** request 2 (same or different client) runs `kv_get` on the same key, **Then** request 2 sees the value.
7. **Given** the agent's instructions, **When** it handles a request that creates, updates or deletes a resource, **Then** the instructions tell it to persist the change in storage and to read storage before answering reads, so responses stay consistent across requests.

---

### User Story 6 - State survives a restart when the operator wants it to (Priority: P2)

An operator wants the fake backend's data to survive restarts. They set `STATE_FILE` to a path; the store is loaded from it at startup and saved to it after every change, without risk of a half-written file.

**Why this priority**: Useful for demos that last longer than one process, but in-memory state already fixes the core problem.

**Independent Test**: Start an app with `STATE_FILE=<tmp>`, `kv_set` a value, start a second app with the same file, `kv_get` the value. Separately, simulate a crash during a save and confirm the previous file content is intact.

**Acceptance Scenarios**:

1. **Given** `STATE_FILE` is not set, **When** the server restarts, **Then** the store starts empty (in-memory only) and no file is written.
2. **Given** `STATE_FILE` points to a path that does not exist, **When** the server starts, **Then** it starts with an empty store, and the file is created on the first change.
3. **Given** `STATE_FILE` is set and a value was stored, **When** the server restarts with the same setting, **Then** the value is still readable.
4. **Given** a save is interrupted part-way, **When** the file is read, **Then** it contains either the complete previous state or the complete new state, never a partial write.
5. **Given** `STATE_FILE` points to a file that is not valid state (corrupt or not an object), **When** the server starts, **Then** startup fails with a clear error naming the file, and the file is left untouched.
6. **Given** a `kv_delete` or `kv_set` succeeds, **When** the operation returns, **Then** the change has already been saved to the file.

---

### User Story 7 - The agent cannot fill up memory or disk (Priority: P2)

An LLM can loop or write huge blobs. The operator needs configurable limits on the size of each value and on the number of keys, enforced by the storage tools.

**Why this priority**: Protects the host, but only matters once Story 5 exists.

**Independent Test**: Configure small limits, call `kv_set` with an oversized value and with one key too many; check the tool's result and that the store is unchanged.

**Acceptance Scenarios**:

1. **Given** a maximum value size of N bytes, **When** `kv_set` is called with a value whose serialized size exceeds N, **Then** the tool reports the value is too large (stating the limit), and the store is unchanged.
2. **Given** a maximum key count of M and M keys stored, **When** `kv_set` is called with a new key, **Then** the tool reports the store is full (stating the limit) and the store is unchanged.
3. **Given** M keys stored, **When** `kv_set` overwrites an existing key, **Then** it succeeds.
4. **Given** a key that is empty or longer than 256 characters, **When** any storage tool is called with it, **Then** the tool reports an invalid key and the store is unchanged.
5. **Given** a limit is violated, **When** the tool reports it, **Then** the agent's request continues (the agent can still respond, e.g. with 507 or 400), rather than failing with a server error.
6. **Given** a limit setting of zero or a negative number, **When** the server starts, **Then** startup fails with a configuration error.

---

### User Story 8 - Every response shows what it cost (Priority: P2)

Part of the joke is that each request costs real money. Every agent-produced response carries headers with the total input and output tokens used by the agent's LLM calls for that request and the number of tool calls it made, and the same numbers appear in the request log.

**Why this priority**: Visible, cheap and funny, but the backend works without it.

**Independent Test**: With a fake LLM whose responses carry known token usage (e.g. call 1: 100 in / 20 out; call 2: 150 in / 30 out, with two tool calls), send one request and assert `X-Dopamine-Tokens-In: 250`, `X-Dopamine-Tokens-Out: 50`, `X-Dopamine-Steps: 2`, and that the request log contains the same values.

**Acceptance Scenarios**:

1. **Given** an agent run with several LLM calls, **When** the response is returned, **Then** `X-Dopamine-Tokens-In` and `X-Dopamine-Tokens-Out` equal the sums of input and output tokens over all LLM calls in that request.
2. **Given** an agent run, **When** the response is returned, **Then** `X-Dopamine-Steps` equals the number of tool calls the agent made in that request, including the final response tool call.
3. **Given** the provider reports no usage for a call, **When** totals are computed, **Then** that call contributes 0 and the headers are still present.
4. **Given** the agent's `respond` call sets its own `X-Dopamine-Tokens-*`, `X-Dopamine-Steps` or `X-Dopamine-Cost-USD` header, **When** the response is sent, **Then** the system's values replace them.
5. **Given** a request rejected by an infrastructure guard (413, 401, 429) before the agent runs, **When** the response is returned, **Then** no usage headers are added.
6. **Given** an agent run that ends in an agent failure (no response, loop limit, provider error), **When** the error response is returned, **Then** usage headers report the tokens and steps consumed up to the failure, when known.
7. **Given** a completed request, **When** the request log entry is written, **Then** it contains tokens in, tokens out, steps and, when configured, cost.
8. **Given** two concurrent requests, **When** both complete, **Then** each response reports only its own usage.

---

### User Story 9 - Estimated cost in dollars, with the operator's prices (Priority: P3)

The operator can configure their provider's price per million input tokens and per million output tokens. When configured, responses also carry the estimated cost in USD. No price table ships with the project, because it would go out of date.

**Why this priority**: Optional extra on top of Story 8.

**Independent Test**: With prices configured (e.g. 3.00 in / 15.00 out per million tokens) and the fake usage from Story 8 (250 in / 50 out), assert `X-Dopamine-Cost-USD: 0.001500`. Without prices, assert the header is absent.

**Acceptance Scenarios**:

1. **Given** both prices are configured, **When** a response is returned, **Then** `X-Dopamine-Cost-USD` = tokens_in × input_price / 1,000,000 + tokens_out × output_price / 1,000,000, formatted with 6 decimal places.
2. **Given** no prices are configured, **When** a response is returned, **Then** there is no `X-Dopamine-Cost-USD` header and no cost in the log.
3. **Given** only one of the two prices is configured, or a price is negative, **When** the server starts, **Then** startup fails with a configuration error naming the missing or invalid setting.
4. **Given** a price of 0 is configured (e.g. a free local model), **When** a response is returned, **Then** the cost header is present and `0.000000`.

### Edge Cases

- Preset file exists but is empty: same as an empty personality today (programmatic instructions only), with a warning logged.
- Non-Markdown files in the presets directory (e.g. `.gitkeep`): not offered as presets and not listed in error messages.
- A user adds `config/personalities/mine.md`: it becomes selectable as `PERSONALITY=mine` with no code change.
- Changing `PERSONALITY` while the server runs has no effect until restart.
- Two concurrent requests write the store at the same time: both changes are kept, no lost update and no corrupted file.
- A stored value is not plain text (object, list, number, boolean, null): it is stored and returned with its type preserved.
- `STATE_FILE` directory is not writable: the failing `kv_set`/`kv_delete` reports a storage error to the agent, the in-memory store is left unchanged, and the error is logged.
- A state file that already holds more keys or larger values than the current limits (limits were lowered): it is loaded as-is with a warning; new keys and oversized writes are rejected under the new limits.
- `kv_list` on a store with many keys returns every matching key (bounded by the key-count limit).
- An agent run with zero tool calls (fails without calling any tool) reports `X-Dopamine-Steps: 0`.
- A request served by `respond_with_file` gets the same usage headers as one served by `respond`.
- `/health` gets no usage headers.

## Requirements *(mandatory)*

### Functional Requirements

**Part A — Personality presets**

- **FR-001**: The project MUST ship a `config/personalities/` directory containing at least five Markdown presets: `default`, `shop`, `sarcastic`, `website`, `teapot`.
- **FR-002**: A new setting `PERSONALITY` MUST accept a preset name and resolve it to `config/personalities/<name>.md`; it MUST default to `default`.
- **FR-003**: When `PERSONALITY_PATH` is set to a non-empty value, it MUST take priority over `PERSONALITY`, with the existing missing-file startup failure unchanged.
- **FR-004**: Preset names MUST be normalized (trimmed, lowercased) before resolution.
- **FR-005**: A preset name that matches no available preset, or that contains a path separator or `..`, MUST fail startup with a non-zero exit and a message listing all available preset names in sorted order.
- **FR-006**: Available presets MUST be discovered from the `.md` files in the presets directory, so adding a file adds a preset with no code change.
- **FR-007**: The resolved personality MUST be combined with the programmatic instructions as today (personality first, instructions after).
- **FR-008**: No preset MAY instruct the agent to reply without calling a response tool, nor contradict the programmatic instructions.
- **FR-009**: The startup log MUST record the personality source: preset name and resolved path, or custom path.
- **FR-010**: The legacy `config/personality.md` MUST be replaced by `config/personalities/default.md` with equivalent content.

**Part B — Agent state**

- **FR-011**: The agent MUST have four storage tools: `kv_set(key, value)`, `kv_get(key)`, `kv_list(prefix)`, `kv_delete(key)`, registered in the tool registry.
- **FR-012**: The store MUST be shared by all requests and clients for the lifetime of the server process.
- **FR-013**: Values MUST be any JSON-compatible value (string, number, boolean, null, list, object) and MUST be returned with their type preserved.
- **FR-014**: `kv_get` and `kv_delete` on a missing key, and every limit or key-validation violation, MUST return a descriptive result to the agent without aborting the request or changing the store.
- **FR-015**: `kv_list(prefix)` MUST return all keys starting with `prefix`, sorted; an empty prefix returns all keys.
- **FR-016**: The store MUST be in-memory by default. When `STATE_FILE` is set, the store MUST be loaded from that file at startup (empty if the file does not exist) and saved to it after every successful change, before the tool returns.
- **FR-017**: Saving MUST be atomic: a reader of `STATE_FILE` sees either the complete previous state or the complete new state.
- **FR-018**: A `STATE_FILE` that exists but cannot be parsed as a state object MUST fail startup with an error naming the file, without modifying it.
- **FR-019**: The maximum serialized size per value (`KV_MAX_VALUE_BYTES`, default 65536) and the maximum number of keys (`KV_MAX_KEYS`, default 1000) MUST be configurable and MUST be positive.
- **FR-020**: Keys MUST be non-empty strings of at most 256 characters.
- **FR-021**: Concurrent storage operations MUST NOT lose updates or corrupt the store or the state file.
- **FR-022**: The programmatic instructions MUST explain the storage tools and when to use them: persist created, updated and deleted resources; read storage before answering reads; use consistent key naming (e.g. `<collection>/<id>`); treat "not found" as a normal outcome (e.g. 404).

**Part C — Usage reporting**

- **FR-023**: For each agent-handled request, the system MUST sum input tokens and output tokens over all LLM calls made by the agent for that request, using the usage the provider reports for each call (missing usage counts as 0).
- **FR-024**: Every response produced by an agent run (success or agent failure) MUST include `X-Dopamine-Tokens-In`, `X-Dopamine-Tokens-Out` and `X-Dopamine-Steps` (count of tool calls in that run, including the final response tool call), as non-negative integers. Infrastructure guard rejections that never run the agent MUST NOT include them.
- **FR-025**: System usage headers MUST override any header with the same name set by the agent.
- **FR-026**: Two optional settings, `LLM_PRICE_INPUT_PER_MTOK` and `LLM_PRICE_OUTPUT_PER_MTOK` (USD per million tokens), MUST enable an `X-Dopamine-Cost-USD` header with 6 decimal places. Setting only one, or a negative value, MUST fail startup. The project MUST NOT ship any default price.
- **FR-027**: The structured request log entry MUST include tokens in, tokens out, steps and, when prices are configured, cost.
- **FR-028**: Usage headers MUST be readable by browser clients across origins (exposed under the existing CORS policy).

**Cross-cutting**

- **FR-029**: `.env.example` and the quickstart MUST document `PERSONALITY`, the preset list, the `PERSONALITY_PATH` override, `STATE_FILE`, the storage limits, the usage headers and the price settings.
- **FR-030**: Automated tests MUST cover: preset resolution (default, named, normalization, `PERSONALITY_PATH` priority) and errors (invalid name with listing, path traversal, no presets); each shipped preset is non-empty; each storage tool's contract, limits and key validation directly without an agent; persistence, reload and atomic save; an integration test with a fake LLM doing `kv_set` in one request and `kv_get` in the next; and usage headers, log fields and cost with a fake LLM reporting known token usage. LLM behavior per preset is not tested.

### Key Entities

- **Personality preset**: A named Markdown file in the presets directory; name = file name without `.md`; content = character/tone text placed at the start of the system prompt.
- **Personality source**: The result of startup resolution — a preset (name + path) or a custom path — used to build the system prompt and reported in the startup log.
- **Key-value store**: A shared map from key (string, ≤256 chars) to a JSON-compatible value, bounded by the value-size and key-count limits, optionally mirrored to the state file.
- **State file**: A file holding the whole store as one JSON object, replaced atomically on every change.
- **Request usage**: Per-request totals — tokens in, tokens out, steps, and optional estimated cost — attached to the response headers and the request log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can switch between all five shipped personalities by changing one configuration value and restarting, with no file edits.
- **SC-002**: 100% of invalid preset names produce a startup failure whose message lists every available preset.
- **SC-003**: Existing setups that set `PERSONALITY_PATH` keep the same system prompt after upgrading, and the existing test suite passes unchanged except for tests that referenced the removed legacy file.
- **SC-004**: Adding a new preset takes one Markdown file and zero code changes.
- **SC-005**: A resource created in one request is returned by a later request in 100% of scripted runs, including across a restart when `STATE_FILE` is set.
- **SC-006**: No sequence of storage tool calls can store more keys or larger values than the configured limits.
- **SC-007**: An interrupted save never leaves an unreadable state file.
- **SC-008**: 100% of agent-produced responses carry usage headers whose values match the token usage reported by the provider for that request.
- **SC-009**: With prices configured, the cost header matches a hand calculation to the sixth decimal place.
- **SC-010**: In a manual smoke run, each preset produces responses a reader can identify as that preset's character within one request.

## Assumptions

- Constitution Principle II says "No pre-defined personality presets" and requires `config/personality.md` to exist. Part A needs a constitution amendment (presets allowed; the required personality file becomes the resolved personality source). The amendment is part of planning.
- The constitution's "agent is stateless" framing refers to conversation memory; Part B adds explicit storage through tools (the sanctioned extension point), not conversation history. The agent still starts each request with no memory of previous conversations.
- Removing `config/personality.md` is acceptable: the project is pre-release and anyone who customized it can point `PERSONALITY_PATH` at their copy. `PERSONALITY_PATH` therefore defaults to unset.
- Relative paths (presets directory, `PERSONALITY_PATH`, `STATE_FILE`) resolve from the working directory, as `PERSONALITY_PATH` does today. The presets directory location is fixed (YAGNI).
- Presets are written in English, like the programmatic instructions.
- The `teapot` preset's 418 applies only to agent-handled requests.
- The store is single-process; running several server processes against one `STATE_FILE` is out of scope.
- Value size is measured as the byte length of the value serialized as compact UTF-8 JSON.
- Token counts are taken as the provider reports them (input tokens include any cached input the provider counts); no client-side token estimation.
- "Steps" counts tool calls, not LLM calls, as requested.
