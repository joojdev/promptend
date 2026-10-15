# Feature Specification: Cleanup

**Feature Branch**: `004-cleanup`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "cleanup — three cards: (A) simple API-key authentication with an admin role (single ADMIN_KEY from .env, manages keys only) and a client role (keys created by the admin, the only ones allowed on the catch-all); keys stored hashed in a local database file (KEYS_DB_PATH, default data/keys.db), `sk_`-prefixed, shown once; admin routes under the reserved `/_admin/keys` prefix (create / list / revoke) authenticated by `Authorization: Bearer <ADMIN_KEY>`, 404 when ADMIN_KEY is unset; catch-all requires `X-API-Key`, 401 `{\"error\": \"unauthorized\"}` without invoking the agent; credentials stripped before the agent sees the request; AUTH_ENABLED (default true) to disable for local dev; an `apikeys` CLI (create / list [--all] / revoke) talking directly to the key store; shared key logic, no duplication; .env.example updated; no use of the current project name in anything the card creates. (B) CI with ruff check, ruff format --check and pytest on Python 3.11 and 3.12 using uv; fix ruff findings; .gitattributes marking .specify/ and .claude/ as vendored and specs/ as documentation; keep .specify/ and specs/; MIT LICENSE (ask for the copyright name first). (C) A funny but technically honest English README built only from what exists in the code, with title + tagline + badges, demo placeholder, what/how (Mermaid flow + tools), quickstart (≤3 uv commands + provider choice), configuration table from the real settings, personalities, 'Why you should never use this in production' (latency, cost, non-determinism, prompt injection, third-party data flow, hallucinated status codes, each with the existing mitigation), how it was built (Spec Kit, specs/), contributing and license; TODO placeholders for real LLM output." Update (Part A): "create a login route; the .env holds an admin username and password hash. Admin username and password return an admin token; the admin token creates user tokens; user tokens use the API. Configure a way to add tools that only the admin or the user can use." Hash format: argon2.

## Clarifications

### Session 2026-10-15

- Q: Which name goes on the MIT copyright line? → A: "João Vitor Piovezan".
- Q: What happens to the existing shared access key (`DOPAMINE_ACCESS_KEY` / `X-Dopamine-Key`)? → A: Remove it and let tokens replace it (recommended for one auth path, per-client revocation and audit, and no project name in auth).
- Q: How does the admin authenticate? → A: Username and argon2 password hash in `.env`; `POST /_admin/login` returns a short-lived admin token (replaces the static `ADMIN_KEY`).
- Q: What do tokens unlock? → A: The admin token manages user tokens and can also call the API; user tokens call the API. Tools are restricted per role (`admin` or `user`).
- Q: Which hash format for the admin password? → A: argon2.

## User Scenarios & Testing *(mandatory)*

The feature has three independent parts. Each can be built, tested and shipped on its own.

- **Part A — Admin login, user tokens and role-scoped tools**: Stories 1–7
- **Part B — CI and repository hygiene**: Stories 8–9
- **Part C — README**: Story 10

### User Story 1 - Only token holders can make the agent answer (Priority: P1)

The owner runs the server on a public address. Today anyone who finds it can send requests and spend the owner's LLM tokens. After this change, a request to any agent-backed path is answered only when it carries a valid token in `Authorization: Bearer <token>`: a non-revoked user token, or an unexpired admin token. Every other request is rejected before the agent runs.

**Why this priority**: This is the reason the card exists. Every unauthenticated request costs the owner money.

**Independent Test**: With a fake LLM and a temporary token store holding one user token, send requests with no token, a malformed header, an unknown token, a revoked user token, an expired admin token, a valid admin token and the valid user token. Only the last two reach the agent. All the others get 401 `{"error": "unauthorized"}`, and the fake LLM records zero calls for them.

**Acceptance Scenarios**:

1. **Given** auth is enabled and a valid user token exists, **When** a request carries it as `Authorization: Bearer <token>`, **Then** the agent handles it with the user tool set and its response is returned as today.
2. **Given** auth is enabled and a valid admin token exists, **When** a request carries it on the catch-all, **Then** the agent handles it with the admin tool set.
3. **Given** auth is enabled, **When** a request has no `Authorization` header, a scheme other than `Bearer`, an empty token, an unknown token, a revoked user token or an expired admin token, **Then** the response is 401 with body `{"error": "unauthorized"}` and the agent is not invoked.
4. **Given** a valid user token, **When** it is used successfully, **Then** that token's "last used" time is updated.
5. **Given** a request carries an `Authorization` header (or a legacy `X-API-Key` header), **When** the agent is invoked, **Then** neither header's name nor value appears anywhere in the content sent to the agent. The headers are removed, not masked.
6. **Given** auth is enabled, **When** a client calls `/health` without any token, **Then** it still gets 200.

---

### User Story 2 - The admin logs in with a username and password (Priority: P1)

The owner puts an admin username and an argon2 hash of the admin password in the environment (never the plain password). They log in over HTTP with the username and password and receive a short-lived admin token.

**Why this priority**: Without the admin token nobody can issue user tokens, so Story 1 locks everyone out.

**Independent Test**: With `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` set (hash generated in the test) and a temporary store, log in with the right credentials and get a token; log in with a wrong password, a wrong username and a missing field and get 401/422; use the token on an admin route; let it expire (short TTL) and confirm it is rejected. Confirm the fake LLM was never called.

**Acceptance Scenarios**:

1. **Given** admin credentials are configured, **When** `POST /_admin/login` is called with `{"username": "...", "password": "..."}` matching them, **Then** the response is 200 with `{token, token_type: "bearer", expires_at}`, where the token starts with `adm_`.
2. **Given** admin credentials are configured, **When** the username or password is wrong, **Then** the response is 401 `{"error": "unauthorized"}`, with the same body and comparable timing whether the username or the password was wrong.
3. **Given** a missing or empty username or password field, **When** login is called, **Then** the request is rejected as a client error (400/422) and no token is issued.
4. **Given** an admin token, **When** its lifetime (`ADMIN_TOKEN_TTL_MINUTES`, default 60) has passed, **Then** it no longer authenticates anywhere.
5. **Given** repeated failed logins from one client, **When** more than the login limit (`LOGIN_RATE_LIMIT_PER_MINUTE`, default 5) arrive inside a minute, **Then** further login attempts get 429 until the window passes, even with correct credentials.
6. **Given** `ADMIN_USERNAME` or `ADMIN_PASSWORD_HASH` is unset or blank, **When** any route under `/_admin/` is called, **Then** the response is 404 and the server logged a startup warning that admin routes are disabled.
7. **Given** `ADMIN_PASSWORD_HASH` is set but is not a valid argon2 hash, **When** the server starts, **Then** startup fails with a clear configuration error (without printing the hash).
8. **Given** the owner needs a hash, **When** they run the command-line tool's `hash-password` command, **Then** it prompts for the password without echoing it and prints an argon2 hash ready to paste into `.env`.

---

### User Story 3 - The admin manages user tokens over HTTP (Priority: P1)

Using the admin token as a bearer token, the admin creates a token for a new user (the full token is shown once), lists existing user tokens, and revokes one. These management routes never reach the agent.

**Why this priority**: This is how API users get access.

**Independent Test**: Log in, create a user token, list tokens, revoke it, and confirm the revoked token now gets 401 on the catch-all. Confirm a user token cannot call admin routes and the fake LLM was never called by admin routes.

**Acceptance Scenarios**:

1. **Given** a valid admin token, **When** the admin calls `POST /_admin/tokens` with `{"name": "..."}`, **Then** the response is 201 with id, name, prefix, the full token (starting with `sk_`) and creation time.
2. **Given** a valid admin token, **When** the admin calls `GET /_admin/tokens`, **Then** every user token is listed with id, name, prefix, creation time, last-used time and revoked status, and no entry contains the full token or its hash. Admin tokens are not listed.
3. **Given** a valid admin token and an existing user token id, **When** the admin calls `DELETE /_admin/tokens/{id}`, **Then** the response is 204, the token is marked revoked (not deleted), and it no longer authenticates on the catch-all.
4. **Given** no `Authorization` header, an unknown token, an expired admin token, or a user token as the bearer token, **When** any token-management route is called, **Then** the response is 401.
5. **Given** any request under `/_admin/` (including unknown sub-paths or methods), **When** it is handled, **Then** the agent is never invoked.

---

### User Story 4 - Some tools are only for the admin (Priority: P2)

The owner wants to give the agent tools that only the admin may trigger (for example, a tool that wipes the agent's storage), while ordinary users get the regular tool set. Adding a tool and declaring who may use it must not require touching the routing or auth code.

**Why this priority**: It extends the role model to the agent. The token flow (Stories 1–3) works without it.

**Independent Test**: Register a test tool marked admin-only and one marked for users. Send one request with an admin token and one with a user token, and check which tools the model was offered in each run.

**Acceptance Scenarios**:

1. **Given** a tool declared for role `user`, **When** a user or the admin makes a request, **Then** the tool is available to the agent in both runs (the admin can do everything a user can).
2. **Given** a tool declared for role `admin`, **When** the admin makes a request, **Then** the tool is available; **When** a user makes a request, **Then** the tool is not offered to the model at all (not merely refused when called).
3. **Given** a tool that declares no role, **When** it is registered, **Then** it is treated as a `user` tool, so all existing tools keep working for both roles.
4. **Given** a tool declares an unknown role, **When** the server starts, **Then** startup fails with an error naming the tool and the role.
5. **Given** `AUTH_ENABLED=false` and a request without a token, **When** the agent runs, **Then** it gets the user tool set; admin tools still require a valid admin token.
6. **Given** a developer adds a new tool, **When** they follow the documented steps, **Then** declaring its role is a single attribute on the tool, with no change to routes, auth or harness code.

---

### User Story 5 - The owner manages user tokens from the command line (Priority: P2)

The owner prefers a terminal, or the server is down. A command-line tool that works directly on the token store lets them create, list and revoke user tokens, and generate the admin password hash, without running the server and without logging in.

**Why this priority**: It is a convenience and a recovery path. The HTTP routes already cover the core need.

**Independent Test**: Point the CLI at a temporary store. Run `create`, `list`, `list --all`, `revoke` and `hash-password`, and check the output and stored state after each.

**Acceptance Scenarios**:

1. **Given** a token store path, **When** the owner runs `tokens create <name>`, **Then** the full user token is printed once, with a warning that it will not be shown again.
2. **Given** active and revoked user tokens, **When** the owner runs `tokens list`, **Then** a table shows id, name, prefix, created at, last used and status for active tokens only. With `--all`, revoked tokens are included.
3. **Given** an existing token id, **When** the owner runs `tokens revoke <id>`, **Then** the token is marked revoked and a later HTTP request with it gets 401.
4. **Given** an unknown id, **When** the owner runs `tokens revoke <id>`, **Then** the tool reports the token was not found and exits non-zero.
5. **Given** the same store, **When** a token is created via the CLI, **Then** the HTTP admin list shows it, and the reverse also holds, because both paths use the same token logic.
6. **Given** `tokens hash-password`, **When** the owner types the password twice, **Then** a matching pair prints the argon2 hash and a mismatch exits non-zero without printing anything.

---

### User Story 6 - Tokens can never be recovered from storage (Priority: P1)

If the token store file leaks (backup, misplaced copy), the attacker must not get usable tokens, and `.env` never holds the admin password itself.

**Why this priority**: Storing plaintext secrets turns any file leak into full access. It is a security baseline.

**Independent Test**: Log in and create several user tokens, then read every value in the raw store file and the test `.env`. None of the full tokens and not the admin password appears anywhere.

**Acceptance Scenarios**:

1. **Given** user and admin tokens were issued, **When** the store file is inspected directly, **Then** it holds only a one-way hash, a short identifying prefix, the role, name, timestamps, expiry (admin) and revoked flag per token. No full token appears.
2. **Given** a token was issued, **When** anyone tries to retrieve it later by any supported means (HTTP, CLI), **Then** only the prefix is available.
3. **Given** the admin password, **When** configuration is written, **Then** only its argon2 hash is stored; no setting accepts the plain password.
4. **Given** the default store location, **When** the owner checks version control status, **Then** the store directory is ignored and never committed.

---

### User Story 7 - Local development without tokens (Priority: P2)

A developer running the server locally wants to curl it without logging in. They turn authentication off with one setting and get a loud startup warning that it is off.

**Why this priority**: It is a developer convenience and must not weaken the default.

**Independent Test**: Start the app with `AUTH_ENABLED=false`. A request with no token reaches the agent with the user tool set, and the startup log contains a warning.

**Acceptance Scenarios**:

1. **Given** `AUTH_ENABLED=false`, **When** a request without a token hits the catch-all, **Then** the agent handles it with the user tool set.
2. **Given** `AUTH_ENABLED=false`, **When** the server starts, **Then** a warning saying authentication is disabled is logged.
3. **Given** `AUTH_ENABLED` is not set, **When** the server starts, **Then** authentication is enabled.
4. **Given** `AUTH_ENABLED=false` and a request carrying `Authorization`, **When** the agent is invoked, **Then** the header is still removed from the agent's input; a valid admin token still selects the admin tool set, and an invalid token is ignored (user tool set).

---

### User Story 8 - Every push is checked automatically (Priority: P2)

The maintainer wants each push and pull request checked for lint, formatting and tests on every supported Python version, so regressions show up before merging.

**Why this priority**: The project has no CI, and nothing stops a broken commit from landing.

**Independent Test**: Push the branch. The workflow runs lint, format check and the test suite on Python 3.11 and 3.12, and all jobs pass.

**Acceptance Scenarios**:

1. **Given** a push or pull request, **When** CI runs, **Then** it runs lint, format check and the full test suite on Python 3.11 and on 3.12.
2. **Given** the current code base, **When** lint and format checks run, **Then** they report zero issues.
3. **Given** CI runs tests, **When** no real LLM credentials are available, **Then** the suite still passes (tests use fake LLMs).

---

### User Story 9 - The repository presents itself honestly (Priority: P3)

A visitor to the GitHub page should see a language bar that reflects the real code, not the Spec Kit scaffolding, and a clear open-source license. The spec-driven artifacts stay in the repository as a record of the process.

**Why this priority**: It affects presentation and legal clarity, not behavior.

**Independent Test**: Check that attributes mark the scaffolding directories as vendored and `specs/` as documentation, that `.specify/` and `specs/` still exist, and that a MIT LICENSE names the confirmed copyright holder.

**Acceptance Scenarios**:

1. **Given** the repository attributes file, **When** GitHub computes languages, **Then** `.specify/` and `.claude/` count as vendored and `specs/` as documentation.
2. **Given** this feature is merged, **When** the tree is listed, **Then** `.specify/` and `specs/` are still present.
3. **Given** the LICENSE file, **When** read, **Then** it is the MIT license with year 2026 and copyright holder "João Vitor Piovezan".

---

### User Story 10 - A README that is funny and technically honest (Priority: P2)

A visitor lands on the repository and, within a couple of minutes, understands what the project does, can run it, and comes away convinced the author knows exactly why it is a terrible idea.

**Why this priority**: The README is the project's public face. It depends on Parts A and B so that it can describe the token-based access and the CI badge accurately.

**Independent Test**: Review the README against the code. Every setting, preset, tool, header and command it mentions exists, every placeholder needing real LLM output is marked TODO, and all required sections are present in order.

**Acceptance Scenarios**:

1. **Given** the README, **When** read top to bottom, **Then** it has these sections in order: title, one-line tagline and badges (CI, Python, license); demo (GIF placeholder plus a curl example); "What is this?" (2–3 sentences); "How it works" (Mermaid flow request → catch-all → agent → tools → respond → HTTP response, plus a short tool list); "Quickstart" (at most 3 commands plus the provider choice); "Configuration" (a table of every real setting with default and description); "Personalities" (each shipped preset with a one-line joke, plus how to add one); "Why you should never use this in production"; "How it was built"; "Contributing"; "License".
2. **Given** the configuration table, **When** compared with the settings the application declares, **Then** every setting appears with its real default, and no setting that does not exist appears.
3. **Given** the production section, **When** read, **Then** it covers latency, cost per request, non-determinism (the same GET can answer differently), prompt injection via the request body, request data sent to a third-party provider, and hallucinated status codes. Each item names the mitigation the project actually has (header redaction/removal, rate limit, admin login and user tokens, agent timeout, body-size limit, usage/cost headers) or says plainly that there is none.
4. **Given** any example that would need real LLM output, **When** the README is written, **Then** it contains a clearly marked TODO placeholder instead of invented output, and the author is told which commands to run to fill it.
5. **Given** the "How it was built" section, **When** read, **Then** it explains that the project was built with spec-driven development using Spec Kit and links to `specs/`.
6. **Given** the README, **When** read, **Then** it is in English, jokes are occasional rather than in every sentence, and emoji are used sparingly if at all.

---

### Edge Cases

- `ADMIN_USERNAME` or `ADMIN_PASSWORD_HASH` set to an empty or whitespace-only value: treated as not set (admin routes 404, startup warning).
- Login with the right username in a different letter case: rejected (usernames are compared exactly).
- `Authorization` uses a scheme other than `Bearer`, or `Bearer` with no token: 401 on admin routes and on the catch-all.
- A user token sent to `/_admin/tokens`: 401. An admin token sent to the catch-all: accepted with the admin tool set.
- Two logins in a row: both admin tokens are valid until they expire; logging in does not revoke earlier admin tokens.
- Changing `ADMIN_PASSWORD_HASH` and restarting: existing admin tokens stay valid until they expire (documented; the owner can shorten the TTL).
- Creating a user token with a missing or empty name: rejected as a client error (422/400) and no token is created.
- Revoking an unknown id over HTTP: 404. Revoking an already-revoked token: 204 (idempotent), and revoked state stays.
- Revoking an admin token id through `/_admin/tokens/{id}`: 404 (only user tokens are managed there).
- The token store file or its parent directory does not exist yet: it is created on first use by the server or the CLI.
- A path that merely starts with the admin prefix text but is not under it (e.g. `/_adminx`): it goes to the catch-all, which applies normal token auth.
- With `AUTH_ENABLED=false`, admin routes keep their own rules (login and admin token still required, or 404 when admin credentials are unset).
- Concurrent use of the same store by the running server and the CLI: both see each other's changes without corrupting the file.
- Expired admin tokens accumulate in the store: they are purged when new admin tokens are issued.
- Order of guards on the catch-all: a request rejected for a missing token does not consume the rate-limit budget or reach the agent. Body-size rejection may still happen first. The login route has its own, stricter rate limit.
- An admin-only tool's name appears in a user's request body: the tool is still not offered to the model, so prompt injection cannot reach it.

## Requirements *(mandatory)*

### Functional Requirements

**Part A — Admin login, user tokens and role-scoped tools**

- **FR-001**: The system MUST recognise two roles: `admin` (one account, credentials from configuration) and `user` (holders of tokens the admin creates). Both roles may call agent-backed paths; only `admin` may manage tokens.
- **FR-002**: Admin credentials MUST be configured as `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH`, where the hash is in argon2 (argon2id) encoded form. No setting MAY accept the plain password. An invalid hash MUST fail startup without printing it.
- **FR-003**: `POST /_admin/login` with `{"username", "password"}` MUST verify the username exactly and the password against the argon2 hash, and on success return 200 `{token, token_type: "bearer", expires_at}`. On failure it MUST return 401 `{"error": "unauthorized"}`, with a password verification performed even when the username is wrong, so the two failures are indistinguishable.
- **FR-004**: Admin tokens MUST start with `adm_`, MUST expire after `ADMIN_TOKEN_TTL_MINUTES` (default 60, must be > 0), and MUST be stored only as a one-way hash with their expiry. Expired admin tokens MUST be purged when new ones are issued.
- **FR-005**: The login route MUST have its own per-client rate limit (`LOGIN_RATE_LIMIT_PER_MINUTE`, default 5, must be > 0) counting every attempt; beyond it, login returns 429 without verifying credentials.
- **FR-006**: User tokens MUST be generated from a cryptographically secure random source, MUST start with `sk_`, MUST be returned exactly once at creation, and MUST NOT be retrievable afterwards.
- **FR-007**: All tokens MUST be persisted in a local single-file database whose path is configurable (`TOKENS_DB_PATH`, default `data/tokens.db`). Its directory MUST be excluded from version control. For each token the store MUST hold only: an id, a role, a name/description, a one-way hash, a short identifying prefix (first 8 characters), creation time, last-used time, expiry (admin only) and a revoked flag.
- **FR-008**: Management routes MUST live under the reserved prefix `/_admin/`. They MUST take precedence over the catch-all and MUST NEVER invoke the agent.
- **FR-009**: Token-management routes MUST authenticate with `Authorization: Bearer <admin token>`. Missing, malformed, unknown, expired or user tokens MUST yield 401.
- **FR-010**: `POST /_admin/tokens` with `{"name": "..."}` MUST create a user token and return 201 with `{id, name, prefix, token, created_at}`.
- **FR-011**: `GET /_admin/tokens` MUST return all user tokens with id, name, prefix, created_at, last_used_at and revoked. It MUST NOT return full tokens, hashes or admin tokens.
- **FR-012**: `DELETE /_admin/tokens/{id}` MUST mark the user token revoked (soft delete) and return 204. An unknown id, or the id of an admin token, MUST return 404. Revoking an already-revoked token MUST return 204.
- **FR-013**: When `ADMIN_USERNAME` or `ADMIN_PASSWORD_HASH` is unset or blank, every route under `/_admin/` MUST return 404 and the server MUST log a startup warning that admin routes are disabled. User tokens already in the store keep working.
- **FR-014**: When authentication is enabled, the catch-all MUST require `Authorization: Bearer <token>` with a valid non-revoked user token or an unexpired admin token. Otherwise it MUST respond 401 with JSON `{"error": "unauthorized"}` without invoking the agent.
- **FR-015**: Each successful user-token authentication MUST update that token's last-used time.
- **FR-016**: The `Authorization` header and any `X-API-Key` header MUST be removed entirely (name and value) from the request data passed to the agent, whether or not authentication is enabled.
- **FR-017**: `/health` MUST remain public.
- **FR-018**: A setting `AUTH_ENABLED` (default true) MUST control token enforcement on the catch-all. When false, the catch-all MUST work without a token (user role, or admin role when a valid admin token is sent) and the server MUST log a startup warning.
- **FR-019**: Every tool MUST have a role, `user` or `admin`, declared on the tool itself; a tool without a declaration is `user`. A run for the `admin` role MUST be offered all tools; a run for the `user` role MUST be offered only `user` tools. Tools not allowed for the caller's role MUST NOT be offered to the model at all. An unknown role MUST fail startup naming the tool.
- **FR-020**: Adding a role-restricted tool MUST require only defining the tool with its role and registering it; no change to routes, auth or harness code. The steps MUST be documented.
- **FR-021**: A command-line tool, runnable as a module and as an installed command named `tokens`, MUST offer `create <name>` (prints the full user token once with a "won't be shown again" warning), `list` (table of id, name, prefix, created at, last used, status; `--all` includes revoked tokens), `revoke <id>` and `hash-password` (prompts twice without echo, prints the argon2 hash). It MUST operate directly on the configured store, MUST work with the server stopped, and MUST NOT need admin login.
- **FR-022**: Token generation, hashing, storage, lookup, listing, revocation and admin password verification MUST be implemented once in a shared module used by both the HTTP routes and the CLI. The argon2 implementation is the only new runtime dependency this part may add.
- **FR-023**: `.env.example` MUST document `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` (with the `tokens hash-password` command), `ADMIN_TOKEN_TTL_MINUTES`, `LOGIN_RATE_LIMIT_PER_MINUTE`, `TOKENS_DB_PATH` and `AUTH_ENABLED`.
- **FR-024**: No route, setting, token prefix, CLI command, module or file created or modified by Part A may contain the project's current name (case-insensitive). The existing usage headers (`X-Dopamine-Tokens-*`, etc.) are out of scope and unchanged.
- **FR-025**: The existing single shared access key (`DOPAMINE_ACCESS_KEY` setting and `X-Dopamine-Key` header) MUST be removed: its setting, its check on the catch-all, its special case in header handling, its `.env.example` entry and its tests. Tokens are the only way to call the catch-all. A request that still sends `X-Dopamine-Key` gets no special treatment: without a valid token it gets 401, and the header is handled by the normal redaction rules.
- **FR-026**: Existing tests that call the catch-all MUST be updated to pass with authentication on by default, through a shared test fixture that either provisions a user token or disables authentication.

**Part B — CI and repository hygiene**

- **FR-027**: A GitHub Actions workflow MUST run lint check, format check and the full test suite on Python 3.11 and 3.12 on every push and pull request, installing dependencies with uv from the committed lockfile.
- **FR-028**: Lint and format checks MUST pass with zero findings on the whole repository as configured.
- **FR-029**: A repository attributes file MUST mark `.specify/` and `.claude/` as vendored and `specs/` as documentation.
- **FR-030**: `.specify/` and `specs/` MUST NOT be removed.
- **FR-031**: A MIT `LICENSE` MUST be added with the copyright holder confirmed by the user (see Story 9), and project metadata MUST declare the license.

**Part C — README**

- **FR-032**: A `README.md` in English MUST be added following the section order in Story 10, scenario 1.
- **FR-033**: Every feature, setting, preset, tool, header, route and command named in the README MUST exist in the code at the time of writing. The configuration table MUST list every declared setting with its real default.
- **FR-034**: Examples that need real LLM output MUST be TODO placeholders. The completion report MUST tell the user which commands to run to fill them.
- **FR-035**: The production-risks section MUST cover the six risks in Story 10, scenario 3, each paired with the real mitigation or an explicit "none".
- **FR-036**: Where the user's brief differs from the code, the README MUST follow the code and the differences MUST be reported to the user.

### Key Entities

- **Admin account**: Username and argon2 password hash from configuration. Not stored in the token store. Logging in yields admin tokens.
- **Admin token**: A short-lived credential (`adm_` prefix) issued by login. Authorises token management and agent requests with the admin tool set. Stored hashed with an expiry.
- **User token**: A credential (`sk_` prefix) issued by the admin to one user. Attributes: id, name/description, hashed secret, short prefix, created at, last used at, revoked. Authorises agent requests with the user tool set. Never stored or shown again in full after creation.
- **Token store**: A local single file holding admin and user token records, shared by the server and the CLI.
- **Tool role**: `user` or `admin`, declared on each tool; decides which callers' agent runs are offered the tool.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of catch-all requests without a valid token are rejected with 401 and cause zero agent/LLM invocations (verified by tests with a call-counting fake LLM).
- **SC-002**: An owner can log in, issue a new user token and make a first successful request with it in under 1 minute, via HTTP or the CLI.
- **SC-003**: A revoked user token stops working on the very next request, and an expired admin token stops working as soon as it expires, with no restart.
- **SC-004**: Inspecting the raw token store and configuration reveals zero full tokens and zero plain passwords.
- **SC-005**: Zero occurrences of the credential headers' names or values in the content sent to the agent across all tested request shapes.
- **SC-006**: Zero occurrences of the project's current name (case-insensitive) in files created by Part A, and zero new occurrences added to files Part A modifies.
- **SC-006a**: In 100% of tested runs, user-role requests are offered zero admin-only tools, and admin-role requests are offered every registered tool.
- **SC-007**: CI passes on both supported Python versions with zero lint and zero format findings.
- **SC-008**: Spec Kit scaffolding is excluded from the repository language statistics (Python is the dominant language shown).
- **SC-009**: A reviewer cross-checking the README against the code finds zero claims about features, settings, presets or tools that do not exist.
- **SC-010**: A first-time reader can go from clone to a running server with no more than 3 commands plus provider configuration.

## Assumptions

- "cleanup" is the name for this bundle of three cards, delivered as one feature on the session's working branch. The spec directory is numbered `004` per sequential numbering. No separate feature branch is created, because work must stay on the designated branch.
- Admin routes (login and token management) return successful responses without the agent. This needs a constitution amendment: Principle I currently allows agent-bypassing guards only for rejections. The plan phase will propose that amendment (token management as a reserved, non-agent control plane, like `/health`).
- The static `ADMIN_KEY` from the earlier draft is replaced by admin login; `KEYS_DB_PATH`/`apikeys` are renamed `TOKENS_DB_PATH`/`tokens`, and client keys are now called user tokens. Nothing was implemented under the old names, so there is no migration.
- Both roles use one header, `Authorization: Bearer <token>`, on admin routes and on the catch-all. `X-API-Key` is not accepted; it is only stripped from the agent input.
- Admin tokens are stored hashed in the token store with an expiry (instead of signed stateless tokens), so no extra signing secret is needed and they survive restarts. There is no logout route; tokens expire.
- User tokens are long random secrets, so a fast one-way hash is enough for them; argon2 is used only for the human-chosen admin password.
- The admin is a superset of the user: admin runs get every tool, user runs get only `user` tools. No admin-only tool ships with this feature; the mechanism, its documentation and tests with a test tool are in scope.
- The caller's role selects the tool set; it is not added to the text the agent sees.
- The current lint/format findings all sit in the vendored Spec Kit scripts under `.specify/`. "Fix what ruff reports" is satisfied by excluding the vendored directories from ruff (consistent with marking them vendored) rather than editing third-party scaffolding. Project code is already clean.
- The existing redaction of other sensitive headers (masking with `[REDACTED]`) stays as is. Only `Authorization` and `X-API-Key` change from masked to removed.
- Removing the shared access key is a breaking change for anyone with `DOPAMINE_ACCESS_KEY` in their `.env`. Since the project is pre-1.0 and has no known deployments, it is accepted with no migration shim.
- The existing per-client rate limit, body-size limit and agent timeout are unchanged. Token auth is checked before the rate limit so that unauthenticated traffic does not consume rate-limit budget.
- Timestamps are stored and shown in UTC ISO-8601.
- Token ids are short, auto-incrementing integers, which are easy to type in the CLI.
- The README describes the project by its current name ("dopamine"). The no-name rule applies only to artifacts created by Part A.
- The README badges point at this repository's GitHub path (`joojdev/dopamine`) and the new workflow.
