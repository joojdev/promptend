from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

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

    app = FastAPI(lifespan=lifespan)
    register_error_handlers(app)

    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "ready"}

    _METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

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
            reply = await invoke_agent(_agent, incoming)
        except LLMUnavailableError:
            raise
        except Exception:
            raise

        log.info(
            "request",
            method=request.method,
            path=f"/{full_path}",
            status=200,
        )
        return JSONResponse({"reply": reply})

    return app


app = create_app()
