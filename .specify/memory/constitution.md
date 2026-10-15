<!--
SYNC IMPACT REPORT
==================
Version change: 1.1.0 → 1.2.0

Modified principles:
  - I. Agent-as-Harness (title unchanged): added "Response metadata" paragraph.
    Infrastructure MAY annotate agent-produced responses with run metadata
    (003-cosmetic-features usage headers) but MUST NOT change status or body.
  - II. Customizable Personality (title unchanged): presets are now allowed.
    Shipped presets live in `config/personalities/`; `PERSONALITY` selects one,
    `PERSONALITY_PATH` overrides with a custom file. The "MUST exist" rule now
    applies to the resolved personality file. Removed "No pre-defined personality
    presets".

Modified standards:
  - Configuration & Standards: "No long-term memory" replaced. Conversation memory
    stays out of scope (each request starts without history); explicit state
    through bounded storage tools is allowed.

Added sections: None
Removed sections: None

Bump rationale: MINOR — rules relaxed in a backward-compatible way (a custom
personality file still works and still fails startup when missing); no
principle removed.

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check reads constitution at runtime
  ✅ .specify/templates/spec-template.md — no change needed
  ✅ .specify/templates/tasks-template.md — no change needed
  ✅ specs/001-project-boilerplate/quickstart.md — personality section now describes presets
    (updated by 003-cosmetic-features implementation)

Deferred TODOs: None
-->

# Dopamine Constitution

## Core Principles

### I. Agent-as-Harness

The LangChain agent IS the request harness. Every incoming HTTP request MUST
be routed through the agent — no handler MAY produce a response that bypasses
it. The agent orchestrates execution via tools; tools are the only sanctioned
extension point for adding behavior.

The built-in `respond` tool (`return_direct=True`) is the designated exit
point for the agent loop: when the agent is ready to reply, it MUST call
`respond(reply="...")`, which immediately terminates the loop and returns the
reply to the HTTP client. The system prompt MUST instruct the agent to always
end by calling `respond`. LangGraph's `recursion_limit` acts as a hard ceiling
in case the agent fails to call it.

New capabilities are added as tools registered on the agent — never as logic
embedded directly in route handlers or middleware.

Infrastructure guards are the one sanctioned exception to "no response without
the agent". A guard MAY reject a request or report a failure without invoking the
agent only when it (a) protects the agent or the LLM provider from cost, abuse or
oversized input (body-size limit, access key, rate limit), or (b) reports an
agent-run failure the agent cannot report about itself (no response, timeout,
provider unavailable, step limit). Guards MUST NOT generate successful (2xx)
responses, MUST NOT add behavior a tool could provide, and MUST be covered by
tests proving the agent was not invoked on rejection.

Response metadata: infrastructure MAY add headers describing the agent run
(e.g. token usage, step count, estimated cost) to responses the agent produced
or failed to produce. It MUST NOT change the status code or body chosen by the
agent, and system metadata headers take precedence over same-named headers the
agent sets.

**Rationale**: The harness model keeps the agent as the single decision-maker
and makes the system trivially extensible: drop in a new tool, the agent gains
a new capability without touching routing code. This is also what makes the
project comedically coherent — the AI literally runs the backend.

### II. Customizable Personality

The agent's character is defined in a plain Markdown file editable directly by
the user without touching source code. The project ships presets in
`config/personalities/<name>.md`; the `PERSONALITY` setting selects one by name
(default `default`), and `PERSONALITY_PATH` points to a custom file and takes
priority when set. The resolved file is loaded at startup and injected as the
system prompt on every request.

Rules:
- The resolved personality file MUST exist; the server MUST refuse to start if
  it is missing or if `PERSONALITY` names no available preset (listing the
  available ones).
- Presets are discovered from the files in `config/personalities/`; adding a
  preset MUST NOT require a code change.
- Practical instructions (available tools, behavioral constraints) MUST be
  injected programmatically at runtime and kept separate from the personality
  file. The personality file is for character/tone only, and presets MUST NOT
  contradict the programmatic instructions.
- The personality is stateless — it is re-read at startup, not per-request.
  Live reloading is out of scope for v1.

**Rationale**: Keeping the personality in user-facing `config/` files makes
the comedic premise immediately accessible — anyone cloning the repo can pick
a preset or reshape the agent's character without reading a line of code.

### III. Test-First (NON-NEGOTIABLE)

Tests MUST be written and approved before implementation begins.
The Red-Green-Refactor cycle MUST be followed strictly:

1. Write a failing test that captures the intent.
2. Confirm the test fails for the right reason.
3. Implement only enough to make it pass.
4. Refactor without changing observable behavior.

No production code MAY be committed without a prior failing test.
Each tool registered on the agent MUST have its contract tested independently
before being wired into the harness.

**Rationale**: Without TDD the agent/tool boundary becomes an untestable black
box. Tests also document what the agent is expected to do with tool output,
which is otherwise implicit and hard to reason about.

### IV. Simplicity / YAGNI

Complexity MUST be justified against a concrete, present requirement.
If a simpler alternative meets the current need, it MUST be chosen.
Future-proofing, speculative abstractions, and anticipatory layers are
forbidden. Three similar lines are preferable to a premature abstraction.

Complexity violations MUST be documented in the plan's Complexity Tracking
table with an explicit rationale for why the simpler path was insufficient.

**Rationale**: The project's humor comes from the contrast between a trivial
HTTP server and an AI with opinions. Unnecessary engineering complexity dilutes
the joke and makes the codebase hard to extend.

## Configuration & Standards

- Environment variables MUST be managed via `.env` files loaded with `python-dotenv`.
- All settings MUST be declared in a `pydantic-settings` `BaseSettings` subclass.
  Hard-coded configuration values in source files are forbidden.
- Python version: 3.11+.
- Dependency management: `pyproject.toml` with `uv` (`uv.lock` is committed);
  `pip install -e .` remains a supported alternative.
- Code style: `ruff` for linting and formatting. All commits MUST pass `ruff check`.
- No conversation memory in scope for v1: each request starts without history.
  Explicit state is allowed only through storage tools with configured size and
  key-count limits.

## Development Workflow

- Every feature starts with a spec (`/speckit-specify`) and plan (`/speckit-plan`).
- Tasks are tracked in `tasks.md` generated by `/speckit-tasks`.
- Each tool's contract (inputs, outputs, error cases) MUST be defined and tested
  before the tool is registered on the agent harness.
- Commits happen after each logical task or user story completion.
- All PRs MUST include a Constitution Check confirming no principles are violated.

## Governance

This constitution supersedes all other practices in this repository.
Amendments require:

1. Written rationale for the change.
2. Version bump per semantic versioning:
   - MAJOR: principle removal, redefinition, or backward-incompatible governance change.
   - MINOR: new principle or section added.
   - PATCH: clarifications, wording fixes, non-semantic refinements.
3. Propagation check across all `.specify/templates/` files.
4. Updated `LAST_AMENDED_DATE`.

**Version**: 1.2.0 | **Ratified**: 2026-05-19 | **Last Amended**: 2026-10-15
