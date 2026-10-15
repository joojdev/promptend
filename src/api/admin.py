"""Control-plane routes under /_admin/: admin login and user token management.

None of these routes invoke the agent. When admin credentials are not configured, every
path under /_admin/ answers 404.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.api.errors import NotFoundError, RateLimitedError, UnauthorizedError
from src.api.guards import RateLimiter
from src.auth.passwords import AdminVerifier
from src.auth.tokens import TokenStore

PREFIX = "/_admin"
_ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _add_fallback(router: APIRouter) -> None:
    async def not_found(request: Request):
        raise NotFoundError()

    for path in ("", "/{rest:path}"):
        router.add_api_route(path, not_found, methods=_ALL_METHODS, include_in_schema=False)


def build_admin_router(store: TokenStore, settings) -> APIRouter:
    router = APIRouter(prefix=PREFIX)
    if not settings.admin_enabled:
        _add_fallback(router)
        return router

    verifier = AdminVerifier(settings.admin_username, settings.admin_password_hash)
    login_limiter = RateLimiter(settings.login_rate_limit_per_minute)

    @router.post("/login")
    async def login(payload: LoginRequest, request: Request):
        if not login_limiter.check(request.client.host if request.client else "unknown"):
            raise RateLimitedError()
        if not await run_in_threadpool(verifier.verify, payload.username, payload.password):
            raise UnauthorizedError()
        issued = store.issue_admin_token(settings.admin_token_ttl_minutes)
        return {"token": issued.token, "token_type": "bearer", "expires_at": issued.expires_at}

    _add_fallback(router)
    return router
