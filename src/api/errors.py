from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class LLMUnavailableError(Exception):
    pass


class AgentNoResponseError(Exception):
    pass


class AgentTimeoutError(Exception):
    pass


class AgentLoopLimitError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class RateLimitedError(Exception):
    pass


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == 413:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "request_too_large",
                    "message": "Request body exceeds the maximum allowed size.",
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "message": exc.detail},
        )

    @app.exception_handler(LLMUnavailableError)
    async def llm_unavailable_handler(request: Request, exc: LLMUnavailableError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "llm_unavailable",
                "message": "The AI service is currently unavailable. Please try again later.",
            },
        )

    @app.exception_handler(AgentNoResponseError)
    async def agent_no_response_handler(request: Request, exc: AgentNoResponseError):
        return JSONResponse(
            status_code=502,
            content={
                "error": "agent_no_response",
                "message": "The agent finished without producing a response.",
            },
        )

    @app.exception_handler(AgentTimeoutError)
    async def agent_timeout_handler(request: Request, exc: AgentTimeoutError):
        return JSONResponse(
            status_code=504,
            content={
                "error": "agent_timeout",
                "message": "The agent did not respond in time.",
            },
        )

    @app.exception_handler(AgentLoopLimitError)
    async def agent_loop_limit_handler(request: Request, exc: AgentLoopLimitError):
        return JSONResponse(
            status_code=500,
            content={
                "error": "agent_loop_limit",
                "message": "The agent exceeded its step limit without producing a response.",
            },
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedError):
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Missing or invalid access key."},
        )

    @app.exception_handler(RateLimitedError)
    async def rate_limited_handler(request: Request, exc: RateLimitedError):
        return JSONResponse(status_code=429, content={"error": "rate_limited"})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred.",
            },
        )
