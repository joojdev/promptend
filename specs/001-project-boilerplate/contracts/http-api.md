# HTTP API Contract: Project Boilerplate

**Date**: 2026-05-19 | **Phase**: 1 | **Plan**: [plan.md](../plan.md)

## Overview

The service exposes two endpoints:
1. `GET /health` — service liveness check (does not route through the agent)
2. `{ANY METHOD} /{full_path}` — catch-all; every request forwarded to the agent harness

All responses are JSON. All error responses follow a common structure.

---

## Endpoints

### Health Check

```
GET /health
```

**Purpose**: Confirm the service is running and the agent harness is initialized.

**Request**: No body, no required headers.

**Response 200**:
```json
{
  "status": "ok",
  "agent": "ready"
}
```

**Response 503** (if agent failed to initialize):
```json
{
  "status": "degraded",
  "agent": "unavailable"
}
```

---

### Agent Catch-All

```
{GET|POST|PUT|PATCH|DELETE|...} /{full_path}
```

**Purpose**: Route any HTTP request through the LangGraph agent harness. The agent receives full request context — method, path, headers, raw body, query params — and decides which tools to invoke.

**Request**:
- Any HTTP method
- Any path (including nested, e.g., `/foo/bar/baz`)
- Any headers
- Body: raw bytes, any content type (no format restriction). Body length must not exceed `max_request_body_size` (configurable via env var, default 1 MB).

**Response 200** (agent produced a response):
```json
{
  "reply": "<agent response text>"
}
```

**Response 413** (request body exceeds size limit):
```json
{
  "error": "request_too_large",
  "message": "Request body exceeds the maximum allowed size."
}
```

**Response 503** (LLM provider unreachable):
```json
{
  "error": "llm_unavailable",
  "message": "The AI service is currently unavailable. Please try again later."
}
```

**Response 500** (unhandled error):
```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred."
}
```

---

## Common Error Response Structure

All error responses share this shape:
```json
{
  "error": "<machine-readable error code>",
  "message": "<human-readable description>"
}
```

No raw stack traces are returned to clients.

---

## Request Size Limit

Configured via environment variable `MAX_REQUEST_BODY_SIZE` (integer, bytes). Default: 1048576 (1 MB). Requests exceeding this limit are rejected before the agent is invoked (HTTP 413).
