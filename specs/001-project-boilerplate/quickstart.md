# Quickstart: Project Boilerplate

**Date**: 2026-05-19 | **Phase**: 1 | **Plan**: [plan.md](plan.md)

## Prerequisites

- Python 3.11+
- `git`

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd dopamine
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

The default provider (`anthropic`) is included. For other providers install the matching extra:
`pip install -e ".[openai]"` or `".[bedrock]"` (`uv sync --extra openai` / `--extra bedrock`).

### 4. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set the required variables:

```
LLM_API_KEY=your-api-key-here
LLM_MODEL=your-model-identifier-here
```

Optional variables (with defaults):
```
HOST=0.0.0.0
PORT=8000
MAX_REQUEST_BODY_SIZE=1048576
```

### 5. Configure the agent personality

The agent's character and tone come from a Markdown preset in `config/personalities/`.
Pick one by name with `PERSONALITY` (default: `default`):

| Preset | Character |
|--------|-----------|
| `default` | Neutral, helpful API |
| `shop` | Online store selling absurd products, consistent catalog and orders |
| `sarcastic` | Correct REST data with passive-aggressive messages |
| `website` | Every path is an HTML page of an imaginary website |
| `teapot` | Answers 418 I'm a teapot to everything, philosophically |

```bash
# .env
PERSONALITY=teapot
```

To use your own persona, set `PERSONALITY_PATH` to any Markdown file; it wins over
`PERSONALITY`. An empty file is valid (only behavioral constraints apply). To add a preset,
drop a new `<name>.md` file into `config/personalities/` — no code changes needed.

### 6. Start the service

```bash
python -m uvicorn src.api.app:app --reload
```

If the service starts successfully, you will see structured JSON log output confirming it is running.

If `PERSONALITY` names an unknown preset (the error lists the available ones), `PERSONALITY_PATH` points to a missing file, or a required environment variable is absent, the service will refuse to start and print a clear error message.

### 7. Verify it works

Health check:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok", "agent": "ready"}
```

Send a request through the agent:
```bash
curl -X POST http://localhost:8000/hello -d "Are you awake?"
```

The agent will process the request using its personality and available tools and return a `{"reply": "..."}` response.

## Running Tests

```bash
pytest
```

All tests should pass in a clean environment. The example tool test runs in isolation — no LLM API call is made.

## Adding a New Tool

1. Create a new file in `src/tools/` (e.g., `src/tools/my_tool.py`)
2. Define a `BaseTool` subclass with `name`, `description`, `args_schema`, and `_run` method
3. Write a test in `tests/unit/tools/` that calls `tool.invoke({...})` directly — no agent involved
4. Confirm the test passes (Red → Green)
5. Register the tool in `src/agent/registry.py`
6. The agent can now use the tool on all subsequent requests

See `src/tools/respond.py` and `tests/unit/tools/test_respond.py` for the complete example.

**Note**: `src/tools/respond.py` is the built-in agent exit point (`return_direct=True`). Do not remove or replace it — the agent loop depends on it to terminate cleanly.
