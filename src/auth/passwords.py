"""Admin password hashing and verification (argon2id)."""

import hmac
import secrets

import argon2
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = argon2.PasswordHasher()


class InvalidAdminHash(ValueError):
    pass


def validate_hash(password_hash: str) -> None:
    """Raise InvalidAdminHash if the value is not an encoded argon2 hash (value never echoed)."""
    try:
        argon2.extract_parameters(password_hash)
    except Exception:
        raise InvalidAdminHash("ADMIN_PASSWORD_HASH is not a valid argon2 hash") from None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


class AdminVerifier:
    """Checks admin credentials with the same work whether the username is right or wrong."""

    def __init__(self, username: str, password_hash: str, hasher: argon2.PasswordHasher = _hasher):
        self._username = username.encode("utf-8")
        self._password_hash = password_hash
        self._hasher = hasher
        self._dummy_hash = hasher.hash(secrets.token_urlsafe(16))

    def verify(self, username: str, password: str) -> bool:
        username_ok = hmac.compare_digest(username.encode("utf-8"), self._username)
        target = self._password_hash if username_ok else self._dummy_hash
        try:
            password_ok = self._hasher.verify(target, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            password_ok = False
        return bool(username_ok and password_ok)
