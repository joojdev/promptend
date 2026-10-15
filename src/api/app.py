import base64
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from src.agent.harness import ensure_provider_installed, invoke_agent, load_harness
from src.agent.usage import UsageTracker
from src.api.auth import authenticate
from src.api.errors import (
    RateLimitedError,
    UnauthorizedError,
    register_error_handlers,
)
from src.api.guards import RateLimiter, redact_headers
from src.api.usage_headers import USAGE_HEADERS, apply_usage
from src.auth.tokens import TokenStore
from src.config.personality import resolve_personality
from src.config.settings import load_settings
from src.state.kv_store import KVStore

log = structlog.get_logger()

_agent = None


def create_app(llm=None) -> FastAPI:
    settings = load_settings()
    if llm is None:
        ensure_provider_installed(settings)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _agent
        source = resolve_personality(settings)
        store = KVStore.from_settings(settings)
        _agent = load_harness(
            str(source.path), llm=llm, store=store, personality_preset=source.preset
        )
        yield
        _agent = None

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.llm_prices = (settings.llm_price_input_per_mtok, settings.llm_price_output_per_mtok)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=list(USAGE_HEADERS),
    )
    register_error_handlers(app)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    token_store = TokenStore(settings.tokens_db_path)

    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "ready"}

    _METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]

    @app.api_route("/{full_path:path}", methods=_METHODS)
    async def catch_all(full_path: str, request: Request):
        body = await request.body()
        if len(body) > settings.max_request_body_size:
            raise HTTPException(status_code=413)

        principal = authenticate(
            request.headers.get("authorization"), token_store, settings.auth_enabled
        )
        if principal is None:
            raise UnauthorizedError()
        request.state.principal = principal
        if not limiter.check(request.client.host if request.client else "unknown"):
            raise RateLimitedError()

        incoming = {
            "method": request.method,
            "path": f"/{full_path}",
            "headers": redact_headers(request.headers, *settings.sensitive_header_rule),
            "body": body.decode(errors="replace"),
            "query_params": dict(request.query_params),
        }

        usage = UsageTracker()
        request.state.usage = usage
        result = await invoke_agent(_agent, incoming, settings.agent_timeout_seconds, usage=usage)
        warning = result.pop("warning", None)

        status_code = result["status_code"]
        headers = dict(result["headers"] or {})
        if warning:
            headers["X-Dopamine-Warning"] = warning
        body = result["body"]
        content_type = result["content_type"]

        if isinstance(body, dict):
            response = JSONResponse(content=body, status_code=status_code, headers=headers)
        else:
            raw_body = base64.b64decode(body) if result.get("_base64") else body
            response = Response(
                content=raw_body, status_code=status_code, headers=headers, media_type=content_type
            )
        return apply_usage(request, response, method=request.method, path=f"/{full_path}")

    return app


app = create_app()
