# Feature Specification: Cleanup

**Feature Branch**: `004-cleanup`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "cleanup — three cards: (A) simple API-key authentication with an admin role (single ADMIN_KEY from .env, manages keys only) and a client role (keys created by the admin, the only ones allowed on the catch-all); keys stored hashed in a local database file (KEYS_DB_PATH, default data/keys.db), `sk_`-prefixed, shown once; admin routes under the reserved `/_admin/keys` prefix (create / list / revoke) authenticated by `Authorization: Bearer <ADMIN_KEY>`, 404 when ADMIN_KEY is unset; catch-all requires `X-API-Key`, 401 `{\"error\": \"unauthorized\"}` without invoking the agent; credentials stripped before the agent sees the request; AUTH_ENABLED (default true) to disable for local dev; an `apikeys` CLI (create / list [--all] / revoke) talking directly to the key store; shared key logic, no duplication; .env.example updated; no use of the current project name in anything the card creates. (B) CI with ruff check, ruff format --check and pytest on Python 3.11 and 3.12 using uv; fix ruff findings; .gitattributes marking .specify/ and .claude/ as vendored and specs/ as documentation; keep .specify/ and specs/; MIT LICENSE (ask for the copyright name first). (C) A funny but technically honest English README built only from what exists in the code, with title + tagline + badges, demo placeholder, what/how (Mermaid flow + tools), quickstart (≤3 uv commands + provider choice), configuration table from the real settings, personalities, 'Why you should never use this in production' (latency, cost, non-determinism, prompt injection, third-party data flow, hallucinated status codes, each with the existing mitigation), how it was built (Spec Kit, specs/), contributing and license; TODO placeholders for real LLM output."

## Clarifications

### Session 2026-10-15

- Q: Which name goes on the MIT copyright line? → A: "João Vitor Piovezan".
- Q: What happens to the existing shared access key (`DOPAMINE_ACCESS_KEY` / `X-Dopamine-Key`)? → A: Remove it and let client API keys replace it (recommended for one auth path, per-client revocation and audit, and no project name in auth).

## User Scenarios & Testing *(mandatory)*

The feature has three independent parts. Each can be built, tested and shipped on its own.

- **Part A — Client API keys**: Stories 1–5
- **Part B — CI and repository hygiene**: Stories 6–7
- **Part C — README**: Story 8

### User Story 1 - Only holders of a client key can make the agent answer (Priority: P1)

The owner runs the server on a public address. Today anyone who finds it can send requests and spend the owner's LLM tokens. After this change, a request to any agent-backed path is answered only when it carries a valid, non-revoked client key in the `X-API-Key` header. Every other request is rejected before the agent runs.

**Why this priority**: This is the reason the card exists. Every request without a key costs the owner money.

**Independent Test**: With a fake LLM and a temporary key store holding one client key, send requests with no key, a wrong key, a revoked key, the admin key and the valid key. Only the valid key reaches the agent. All the others get 401 `{"error": "unauthorized"}`, and the fake LLM records zero calls for them.

**Acceptance Scenarios**:

1. **Given** auth is enabled and a valid client key exists, **When** a request carries that key in `X-API-Key`, **Then** the agent handles it and its response is returned as today.
2. **Given** auth is enabled, **When** a request has no `X-API-Key`, an unknown key, or a revoked key, **Then** the response is 401 with body `{"error": "unauthorized"}` and the agent is not invoked.
3. **Given** auth is enabled, **When** a request sends the admin key as `X-API-Key` or as `Authorization: Bearer`, **Then** it gets 401 and the agent is not invoked.
4. **Given** a valid client key, **When** it is used successfully, **Then** that key's "last used" time is updated.
5. **Given** a request carries `X-API-Key` and/or `Authorization` headers, **When** the agent is invoked, **Then** neither header's name nor value appears anywhere in the content sent to the agent. The headers are removed, not masked.
6. **Given** auth is enabled, **When** a client calls `/health` without any key, **Then** it still gets 200.

---

### User Story 2 - The admin manages client keys over HTTP (Priority: P1)

The owner configures a single admin key in the environment. Using it as a bearer token, they create a key for a new client (the full key is shown once), list existing keys, and revoke one. These management routes never reach the agent.

**Why this priority**: Without a way to issue keys, Story 1 locks everyone out.

**Independent Test**: With `ADMIN_KEY` set and a temporary store, create a key, list keys, revoke the key, and confirm the revoked key now gets 401 on the catch-all. Confirm the fake LLM was never called by the admin routes.

**Acceptance Scenarios**:

1. **Given** a valid admin bearer token, **When** the admin creates a key with a name, **Then** the response is 201 with id, name, prefix, the full key (starting with `sk_`) and creation time.
2. **Given** a valid admin bearer token, **When** the admin lists keys, **Then** every key is listed with id, name, prefix, creation time, last-used time and revoked status, and no entry contains the full key or its hash.
3. **Given** a valid admin bearer token and an existing key id, **When** the admin revokes it, **Then** the response is 204, the key is marked revoked (not deleted), and it no longer authenticates on the catch-all.
4. **Given** no `Authorization` header, a wrong admin key, or a client key as the bearer token, **When** any admin route is called, **Then** the response is 401.
5. **Given** `ADMIN_KEY` is not set, **When** any admin route is called, **Then** the response is 404 and the server logged a warning at startup that admin routes are disabled.
6. **Given** any request under the admin prefix (including unknown sub-paths or methods), **When** it is handled, **Then** the agent is never invoked.

---

### User Story 3 - The owner manages keys from the command line (Priority: P2)

The owner prefers a terminal, or the server is down. A command-line tool that works directly on the key store lets them create, list and revoke keys without running the server and without the admin key.

**Why this priority**: It is a convenience and a recovery path. The HTTP routes already cover the core need.

**Independent Test**: Point the CLI at a temporary store. Run `create`, `list`, `list --all` and `revoke`, and check the output and stored state after each.

**Acceptance Scenarios**:

1. **Given** a key store path, **When** the owner runs `apikeys create <name>`, **Then** the full key is printed once, with a warning that it will not be shown again.
2. **Given** active and revoked keys, **When** the owner runs `apikeys list`, **Then** a table shows id, name, prefix, created at, last used and status for active keys only. With `--all`, revoked keys are included.
3. **Given** an existing key id, **When** the owner runs `apikeys revoke <id>`, **Then** the key is marked revoked and a later HTTP request with it gets 401.
4. **Given** an unknown id, **When** the owner runs `apikeys revoke <id>`, **Then** the tool reports the key was not found and exits non-zero.
5. **Given** the same store, **When** a key is created via the CLI, **Then** the HTTP admin list shows it, and the reverse also holds, because both paths use the same key logic.

---

### User Story 4 - Keys can never be recovered from storage (Priority: P1)

If the key store file leaks (backup, misplaced copy), the attacker must not get usable client keys.

**Why this priority**: Storing plaintext keys turns any file leak into full access. It is a security baseline.

**Independent Test**: Create several keys, then read every value in the raw store file. None of the full keys appears anywhere.

**Acceptance Scenarios**:

1. **Given** keys were created, **When** the store file is inspected directly, **Then** it holds only a one-way hash, a short identifying prefix, name, timestamps and revoked flag per key. No full key appears.
2. **Given** a key was created, **When** anyone tries to retrieve it later by any supported means (HTTP, CLI), **Then** only the prefix is available.
3. **Given** the default store location, **When** the owner checks version control status, **Then** the store directory is ignored and never committed.

---

### User Story 5 - Local development without keys (Priority: P2)

A developer running the server locally wants to curl it without creating keys. They turn authentication off with one setting and get a loud startup warning that it is off.

**Why this priority**: It is a developer convenience and must not weaken the default.

**Independent Test**: Start the app with `AUTH_ENABLED=false`. A request with no key reaches the agent, and the startup log contains a warning.

**Acceptance Scenarios**:

1. **Given** `AUTH_ENABLED=false`, **When** a request without a key hits the catch-all, **Then** the agent handles it.
2. **Given** `AUTH_ENABLED=false`, **When** the server starts, **Then** a warning saying authentication is disabled is logged.
3. **Given** `AUTH_ENABLED` is not set, **When** the server starts, **Then** authentication is enabled.
4. **Given** `AUTH_ENABLED=false` and a request carrying `X-API-Key`/`Authorization`, **When** the agent is invoked, **Then** those headers are still removed from the agent's input.

---

### User Story 6 - Every push is checked automatically (Priority: P2)

The maintainer wants each push and pull request checked for lint, formatting and tests on every supported Python version, so regressions show up before merging.

**Why this priority**: The project has no CI, and nothing stops a broken commit from landing.

**Independent Test**: Push the branch. The workflow runs lint, format check and the test suite on Python 3.11 and 3.12, and all jobs pass.

**Acceptance Scenarios**:

1. **Given** a push or pull request, **When** CI runs, **Then** it runs lint, format check and the full test suite on Python 3.11 and on 3.12.
2. **Given** the current code base, **When** lint and format checks run, **Then** they report zero issues.
3. **Given** CI runs tests, **When** no real LLM credentials are available, **Then** the suite still passes (tests use fake LLMs).

---

### User Story 7 - The repository presents itself honestly (Priority: P3)

A visitor to the GitHub page should see a language bar that reflects the real code, not the Spec Kit scaffolding, and a clear open-source license. The spec-driven artifacts stay in the repository as a record of the process.

**Why this priority**: It affects presentation and legal clarity, not behavior.

**Independent Test**: Check that attributes mark the scaffolding directories as vendored and `specs/` as documentation, that `.specify/` and `specs/` still exist, and that a MIT LICENSE names the confirmed copyright holder.

**Acceptance Scenarios**:

1. **Given** the repository attributes file, **When** GitHub computes languages, **Then** `.specify/` and `.claude/` count as vendored and `specs/` as documentation.
2. **Given** this feature is merged, **When** the tree is listed, **Then** `.specify/` and `specs/` are still present.
3. **Given** the LICENSE file, **When** read, **Then** it is the MIT license with year 2026 and copyright holder "João Vitor Piovezan".

---

### User Story 8 - A README that is funny and technically honest (Priority: P2)

A visitor lands on the repository and, within a couple of minutes, understands what the project does, can run it, and comes away convinced the author knows exactly why it is a terrible idea.

**Why this priority**: The README is the project's public face. It depends on Parts A and B so that it can describe the key-based access and the CI badge accurately.

**Independent Test**: Review the README against the code. Every setting, preset, tool, header and command it mentions exists, every placeholder needing real LLM output is marked TODO, and all required sections are present in order.

**Acceptance Scenarios**:

1. **Given** the README, **When** read top to bottom, **Then** it has these sections in order: title, one-line tagline and badges (CI, Python, license); demo (GIF placeholder plus a curl example); "What is this?" (2–3 sentences); "How it works" (Mermaid flow request → catch-all → agent → tools → respond → HTTP response, plus a short tool list); "Quickstart" (at most 3 commands plus the provider choice); "Configuration" (a table of every real setting with default and description); "Personalities" (each shipped preset with a one-line joke, plus how to add one); "Why you should never use this in production"; "How it was built"; "Contributing"; "License".
2. **Given** the configuration table, **When** compared with the settings the application declares, **Then** every setting appears with its real default, and no setting that does not exist appears.
3. **Given** the production section, **When** read, **Then** it covers latency, cost per request, non-determinism (the same GET can answer differently), prompt injection via the request body, request data sent to a third-party provider, and hallucinated status codes. Each item names the mitigation the project actually has (header redaction/removal, rate limit, client API keys, agent timeout, body-size limit, usage/cost headers) or says plainly that there is none.
4. **Given** any example that would need real LLM output, **When** the README is written, **Then** it contains a clearly marked TODO placeholder instead of invented output, and the author is told which commands to run to fill it.
5. **Given** the "How it was built" section, **When** read, **Then** it explains that the project was built with spec-driven development using Spec Kit and links to `specs/`.
6. **Given** the README, **When** read, **Then** it is in English, jokes are occasional rather than in every sentence, and emoji are used sparingly if at all.

---

### Edge Cases

- `ADMIN_KEY` is set to an empty or whitespace-only value: it is treated as not set (admin routes 404, startup warning).
- The admin key and a client key are sent together: the catch-all decides only on `X-API-Key`, and the admin routes only on the bearer token. Neither key works across roles.
- `Authorization` uses a scheme other than `Bearer`, or `Bearer` with no token: 401 on admin routes.
- `X-API-Key` is present but empty: 401.
- Creating a key with a missing or empty name: the request is rejected as a client error (422/400) and no key is created.
- Revoking an unknown id over HTTP: 404. Revoking an already-revoked key: 204 (idempotent), and revoked state stays.
- The key store file or its parent directory does not exist yet: it is created on first use by the server or the CLI.
- A path that merely starts with the admin prefix text but is not under it (e.g. `/_adminx`): it goes to the catch-all, which applies normal client auth.
- With `AUTH_ENABLED=false`, admin routes keep their own rules (they still need the admin key, or 404 when it is unset).
- Concurrent use of the same store by the running server and the CLI: both see each other's changes without corrupting the file.
- Order of guards on the catch-all: a request rejected for a missing key does not consume the rate-limit budget or read the agent. Body-size rejection may still happen first.

## Requirements *(mandatory)*

### Functional Requirements

**Part A — Client API keys**

- **FR-001**: The system MUST recognise two roles: one admin, identified by a single key from configuration that can only manage client keys, and clients, identified by keys the admin creates, who are the only callers allowed on agent-backed paths.
- **FR-002**: Client keys MUST be persisted in a local single-file database whose path is configurable (`KEYS_DB_PATH`, default `data/keys.db`). Its directory MUST be excluded from version control.
- **FR-003**: For each key the store MUST hold only: an id, a name/description, a one-way hash of the full key, a short identifying prefix (first 8 characters), creation time, last-used time (empty until first use) and a revoked flag. The full key MUST never be stored.
- **FR-004**: New keys MUST be generated from a cryptographically secure random source and MUST start with `sk_`. The full key MUST be returned exactly once, at creation, and MUST NOT be retrievable afterwards.
- **FR-005**: Management routes MUST live under the reserved prefix `/_admin/keys`. They MUST take precedence over the catch-all and MUST NEVER invoke the agent.
- **FR-006**: Admin routes MUST authenticate with `Authorization: Bearer <ADMIN_KEY>`, compared in constant time. Missing, malformed or wrong credentials, including a valid client key, MUST yield 401.
- **FR-007**: `POST /_admin/keys` with body `{"name": "..."}` MUST create a key and return 201 with `{id, name, prefix, key, created_at}`.
- **FR-008**: `GET /_admin/keys` MUST return all keys with id, name, prefix, created_at, last_used_at and revoked. It MUST NOT return the full key or the hash.
- **FR-009**: `DELETE /_admin/keys/{id}` MUST mark the key revoked (soft delete) and return 204. An unknown id MUST return 404.
- **FR-010**: When `ADMIN_KEY` is unset or blank, every route under `/_admin/keys` MUST return 404 and the server MUST log a startup warning that key management over HTTP is disabled.
- **FR-011**: When authentication is enabled, the catch-all MUST require a valid, non-revoked client key in `X-API-Key`. Otherwise it MUST respond 401 with JSON `{"error": "unauthorized"}` without invoking the agent.
- **FR-012**: The admin key MUST NOT be accepted as a client key on the catch-all.
- **FR-013**: Each successful client-key authentication MUST update that key's last-used time.
- **FR-014**: `X-API-Key` and `Authorization` headers MUST be removed entirely (name and value) from the request data passed to the agent, whether or not authentication is enabled.
- **FR-015**: `/health` MUST remain public.
- **FR-016**: A setting `AUTH_ENABLED` (default true) MUST control client-key enforcement on the catch-all. When false, the catch-all MUST work without a key and the server MUST log a startup warning.
- **FR-017**: A command-line tool, runnable as a module and as an installed command named `apikeys`, MUST offer `create <name>` (prints the full key once with a "won't be shown again" warning), `list` (table of id, name, prefix, created at, last used, status; `--all` includes revoked keys) and `revoke <id>`. It MUST operate directly on the configured key store, MUST work with the server stopped, and MUST NOT need the admin key. It MUST NOT add new runtime dependencies.
- **FR-018**: Key generation, hashing, storage, lookup, listing and revocation MUST be implemented once in a shared module used by both the HTTP routes and the CLI.
- **FR-019**: `.env.example` MUST document `ADMIN_KEY`, `KEYS_DB_PATH` and `AUTH_ENABLED`, including a comment showing how to generate an admin key (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
- **FR-020**: No route, setting, key prefix, CLI command, module or file created or modified by Part A may contain the project's current name (case-insensitive). The existing usage headers (`X-Dopamine-Tokens-*`, etc.) are out of scope and unchanged.
- **FR-020a**: The existing single shared access key (`DOPAMINE_ACCESS_KEY` setting and `X-Dopamine-Key` header) MUST be removed: its setting, its check on the catch-all, its special case in header handling, its `.env.example` entry and its tests. Client API keys are the only way to call the catch-all. A request that still sends `X-Dopamine-Key` gets no special treatment. Without a valid `X-API-Key` it gets 401, and the header is handled by the normal redaction rules.
- **FR-021**: Existing tests that call the catch-all MUST be updated to pass with authentication on by default, through a shared test fixture that either provisions a client key or disables authentication.

**Part B — CI and repository hygiene**

- **FR-022**: A GitHub Actions workflow MUST run lint check, format check and the full test suite on Python 3.11 and 3.12 on every push and pull request, installing dependencies with uv from the committed lockfile.
- **FR-023**: Lint and format checks MUST pass with zero findings on the whole repository as configured.
- **FR-024**: A repository attributes file MUST mark `.specify/` and `.claude/` as vendored and `specs/` as documentation.
- **FR-025**: `.specify/` and `specs/` MUST NOT be removed.
- **FR-026**: A MIT `LICENSE` MUST be added with the copyright holder confirmed by the user (see Story 7), and project metadata MUST declare the license.

**Part C — README**

- **FR-027**: A `README.md` in English MUST be added following the section order in Story 8, scenario 1.
- **FR-028**: Every feature, setting, preset, tool, header, route and command named in the README MUST exist in the code at the time of writing. The configuration table MUST list every declared setting with its real default.
- **FR-029**: Examples that need real LLM output MUST be TODO placeholders. The completion report MUST tell the user which commands to run to fill them.
- **FR-030**: The production-risks section MUST cover the six risks in Story 8, scenario 3, each paired with the real mitigation or an explicit "none".
- **FR-031**: Where the user's brief differs from the code, the README MUST follow the code and the differences MUST be reported to the user.

### Key Entities

- **Client API key**: A credential issued by the admin to one client. Attributes: id, name/description, hashed secret, short prefix, created at, last used at, revoked. It is never stored or shown again in full after creation.
- **Admin key**: A single secret from configuration. It is not stored in the key store, authorises only key management, and is never valid on agent-backed paths.
- **Key store**: A local single file holding client key records, shared by the server and the CLI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of catch-all requests without a valid, non-revoked client key are rejected with 401 and cause zero agent/LLM invocations (verified by tests with a call-counting fake LLM).
- **SC-002**: An owner can issue a new client key and make a first successful request with it in under 1 minute, via either HTTP or the CLI.
- **SC-003**: A revoked key stops working on the very next request, with no restart.
- **SC-004**: Inspecting the raw key store reveals zero full client keys.
- **SC-005**: Zero occurrences of the credential headers' names or values in the content sent to the agent across all tested request shapes.
- **SC-006**: Zero occurrences of the project's current name (case-insensitive) in files created by Part A, and zero new occurrences added to files Part A modifies.
- **SC-007**: CI passes on both supported Python versions with zero lint and zero format findings.
- **SC-008**: Spec Kit scaffolding is excluded from the repository language statistics (Python is the dominant language shown).
- **SC-009**: A reviewer cross-checking the README against the code finds zero claims about features, settings, presets or tools that do not exist.
- **SC-010**: A first-time reader can go from clone to a running server with no more than 3 commands plus provider configuration.

## Assumptions

- "cleanup" is the name for this bundle of three cards, delivered as one feature on the session's working branch. The spec directory is numbered `004` per sequential numbering. No separate feature branch is created, because work must stay on the designated branch.
- Admin routes return successful responses without the agent. This needs a constitution amendment: Principle I currently allows agent-bypassing guards only for rejections. The plan phase will propose that amendment (key management as a reserved, non-agent control plane, like `/health`).
- The current lint/format findings all sit in the vendored Spec Kit scripts under `.specify/`. "Fix what ruff reports" is satisfied by excluding the vendored directories from ruff (consistent with marking them vendored) rather than editing third-party scaffolding. Project code is already clean.
- The existing redaction of other sensitive headers (masking with `[REDACTED]`) stays as is. Only `X-API-Key` and `Authorization` change from masked to removed.
- Removing the shared access key is a breaking change for anyone with `DOPAMINE_ACCESS_KEY` in their `.env`. Since the project is pre-1.0 and has no known deployments, it is accepted with no migration shim.
- The existing per-client rate limit, body-size limit and agent timeout are unchanged. Client-key auth is checked before the rate limit so that unauthenticated traffic does not consume rate-limit budget.
- Timestamps are stored and shown in UTC ISO-8601.
- Key ids are short, auto-incrementing integers, which are easy to type in the CLI.
- The README describes the project by its current name ("dopamine"). The no-name rule applies only to artifacts created by Part A.
- The README badges point at this repository's GitHub path (`joojdev/dopamine`) and the new workflow.
