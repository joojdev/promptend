"""Control-plane routes under /_admin/: admin login and user token management.

None of these routes invoke the agent. When admin credentials are not configured, every
path under /_admin/ answers 404.
"""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.api.auth import authenticate
from src.api.errors import NotFoundError, RateLimitedError, UnauthorizedError
from src.api.guards import RateLimiter
from src.auth.passwords import AdminVerifier
from src.auth.tokens import TokenStore

PREFIX = "/_admin"
_ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CreateTokenRequest(BaseModel):
    name: str = Field(min_length=1)


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

    def require_admin(request: Request) -> None:
        principal = authenticate(request.headers.get("authorization"), store, auth_enabled=True)
        if principal is None or principal.role != "admin":
            raise UnauthorizedError()

    admin_only = [Depends(require_admin)]

    @router.post("/tokens", status_code=201, dependencies=admin_only)
    def create_token(payload: CreateTokenRequest):
        try:
            issued = store.create_user_token(payload.name)
        except ValueError as exc:
            raise RequestValidationError(
                [{"type": "value_error", "loc": ("body", "name"), "msg": str(exc), "input": ""}]
            ) from None
        return {
            "id": issued.id,
            "name": issued.name,
            "prefix": issued.prefix,
            "token": issued.token,
            "created_at": issued.created_at,
        }

    @router.get("/tokens", dependencies=admin_only)
    def list_tokens():
        return [record.to_public_dict() for record in store.list_user_tokens()]

    @router.delete("/tokens/{token_id}", status_code=204, dependencies=admin_only)
    def revoke_token(token_id: int):
        if not store.revoke_user_token(token_id):
            raise NotFoundError()
        return Response(status_code=204)

    _add_fallback(router)
    return router
