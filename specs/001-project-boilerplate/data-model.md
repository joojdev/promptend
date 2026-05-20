# Data Model: Project Boilerplate

**Date**: 2026-05-19 | **Phase**: 1 | **Plan**: [plan.md](plan.md)

> The agent is stateless per request. There is no persistent storage. The entities below represent in-memory runtime objects, not database records.

## Entities

### Settings

Validated at startup via `pydantic-settings` `BaseSettings`. All values sourced from environment variables (`.env` file or process environment).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `llm_api_key` | `str` | Yes | API key for the LLM provider |
| `llm_model` | `str` | Yes | Model identifier (e.g., provider-specific name) |
| `host` | `str` | No (default: `0.0.0.0`) | Interface to bind the server |
| `port` | `int` | No (default: `8000`) | Port to listen on |
| `max_request_body_size` | `int` | No (default: `1048576` = 1 MB) | Maximum allowed request body in bytes |

**Validation rules**:
- All required fields must be non-empty strings; `ValidationError` raised at startup if absent
- `port` must be in range 1–65535
- `max_request_body_size` must be > 0

---

### IncomingRequest

Assembled from the raw FastAPI `Request` object before passing to the agent. Represents the full context the agent receives.

| Field | Type | Description |
|-------|------|-------------|
| `method` | `str` | HTTP method (GET, POST, etc.) |
| `path` | `str` | Request path (e.g., `/foo/bar`) |
| `headers` | `dict[str, str]` | All request headers |
| `body` | `bytes` | Raw request body (unparsed) |
| `query_params` | `dict[str, str]` | URL query parameters |

**Constraints**:
- `body` length must not exceed `Settings.max_request_body_size`; exceeded requests are rejected before the agent is invoked

---

### AgentResponse

The structured result returned by `create_react_agent` after processing an `IncomingRequest`.

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The agent's final response text |
| `tool_calls` | `list[ToolCall]` | Tools invoked during this request (for observability) |

---

### ToolCall

A record of a single tool invocation within one agent request cycle. Used for logging; not returned to the HTTP client.

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Name of the tool invoked |
| `input` | `dict` | Arguments passed to the tool |
| `output` | `str` | Result returned by the tool |
| `error` | `str \| None` | Error message if the tool raised `ToolException` |

---

### Personality

Loaded once at startup from `config/personality.md`.

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Raw Markdown text from the file (may be empty string) |
| `source_path` | `str` | Absolute path to the loaded file (for logging) |

**Lifecycle**:
- Loaded during FastAPI `lifespan` startup
- Stored in application state for the lifetime of the process
- Empty string is valid (no character injected; behavioral constraints still apply)
- Missing file → `SystemExit` at startup

---

### SystemPrompt

Assembled at request time from `Personality.content` + programmatic behavioral instructions.

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Full system prompt text injected as the agent's first message |

**Assembly rule**: `text = personality.content + "\n\n" + programmatic_instructions`
where `programmatic_instructions` describes available tools and behavioral constraints.
