"""Bearer-token authentication for the catch-all route."""

from dataclasses import dataclass

from src.auth.tokens import TokenStore


@dataclass(frozen=True)
class Principal:
    role: str
    token_id: int | None


ANONYMOUS_USER = Principal("user", None)


def parse_bearer(header: str | None) -> str | None:
    """Token from `Authorization: Bearer <token>` (scheme case-insensitive), else None."""
    if not header:
        return None
    parts = header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        return None
    return parts[1]


def authenticate(header: str | None, store: TokenStore, auth_enabled: bool) -> Principal | None:
    """Principal for the request, or None when auth is enabled and the token is not valid.

    With auth disabled, a valid admin token still yields admin; anything else is an
    anonymous user.
    """
    token = parse_bearer(header)
    record = store.authenticate(token) if token else None
    if record is not None:
        return Principal(record.role, record.id)
    return None if auth_enabled else ANONYMOUS_USER
