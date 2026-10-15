<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.0

Modified principles:
  - I. Agent-as-Harness (title unchanged): added "Infrastructure guards" exception
    paragraph, allowing guards (body size, access key, rate limit, agent-failure
    mapping) to respond without the agent under explicit limits. Formalizes existing
    413/503 behavior and the 002-chores-hardening 401/429/502/504 responses.

Modified standards:
  - Configuration & Standards: dependency management now states pyproject.toml + uv
    (matches repo; pip remains supported). Patch-level wording fix.

Added sections: None
Removed sections: None

Bump rationale: MINOR — materially expanded guidance on Principle I; no principle
removed or redefined incompatibly.

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check reads constitution at runtime
  ✅ .specify/templates/spec-template.md — no change needed
  ✅ .specify/templates/tasks-template.md — no change needed
  ⚠ specs/002-chores-hardening/plan.md — change "⚠️ JUSTIFIED" for Principle I to PASS
    and trim Complexity Tracking; tasks.md T025 now obsolete (amendment applied)

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

**Rationale**: The harness model keeps the agent as the single decision-maker
and makes the system trivially extensible: drop in a new tool, the agent gains
a new capability without touching routing code. This is also what makes the
project comedically coherent — the AI literally runs the backend.

### II. Customizable Personality

The agent's character is defined in `config/personality.md`, a plain Markdown
file editable directly by the user without touching source code. This file is
loaded at startup and injected as the system prompt on every request.

Rules:
- `config/personality.md` MUST exist; the server MUST refuse to start if it
  is missing.
- Practical instructions (available tools, behavioral constraints) MUST be
  injected programmatically at runtime and kept separate from the personality
  file. The personality file is for character/tone only.
- The personality is stateless — it is re-read at startup, not per-request.
  Live reloading is out of scope for v1.
- No pre-defined personality presets. The user writes the prompt directly.

**Rationale**: Keeping the personality in a user-facing `config/` file makes
the comedic premise immediately accessible — anyone cloning the repo can
reshape the agent's character without reading a line of code.

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
- No long-term memory in scope for v1. The agent is stateless per request.

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

**Version**: 1.1.0 | **Ratified**: 2026-05-19 | **Last Amended**: 2026-10-15
