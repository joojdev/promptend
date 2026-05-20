from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class LLMUnavailableError(Exception):
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

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred.",
            },
        )
