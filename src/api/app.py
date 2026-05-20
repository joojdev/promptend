import base64
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from src.agent.harness import invoke_agent, load_harness
from src.api.errors import LLMUnavailableError, register_error_handlers
from src.config.settings import load_settings

log = structlog.get_logger()

_agent = None


def create_app(llm=None) -> FastAPI:
    settings = load_settings()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _agent
        _agent = load_harness(settings.personality_path, llm=llm)
        yield
        _agent = None

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "ready"}

    _METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]

    @app.api_route("/{full_path:path}", methods=_METHODS)
    async def catch_all(full_path: str, request: Request):
        body = await request.body()
        if len(body) > settings.max_request_body_size:
            raise HTTPException(status_code=413)

        incoming = {
            "method": request.method,
            "path": f"/{full_path}",
            "headers": dict(request.headers),
            "body": body.decode(errors="replace"),
            "query_params": dict(request.query_params),
        }

        try:
            result = await invoke_agent(_agent, incoming)
        except LLMUnavailableError:
            raise
        except Exception:
            raise

        status_code = result["status_code"]
        headers = result["headers"] or {}
        body = result["body"]
        content_type = result["content_type"]

        log.info(
            "request",
            method=request.method,
            path=f"/{full_path}",
            status=status_code,
        )

        if isinstance(body, dict):
            return JSONResponse(content=body, status_code=status_code, headers=headers)
        raw_body = base64.b64decode(body) if result.get("_base64") else body
        return Response(
            content=raw_body, status_code=status_code, headers=headers, media_type=content_type
        )

    return app


app = create_app()
