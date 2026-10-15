"""SQLite store for user and admin bearer tokens. Only SHA-256 hashes of tokens are stored."""

import hashlib
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

USER_PREFIX = "sk_"
ADMIN_PREFIX = "adm_"
PREFIX_LEN = 8
ADMIN_TOKEN_NAME = "admin login"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    prefix TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    expires_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0
)
"""

_COLUMNS = "id, role, name, prefix, created_at, last_used_at, expires_at, revoked"


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedToken:
    id: int
    name: str
    prefix: str
    token: str
    created_at: str
    expires_at: str | None = None


@dataclass(frozen=True)
class TokenRecord:
    id: int
    role: str
    name: str
    prefix: str
    created_at: str
    last_used_at: str | None
    expires_at: str | None
    revoked: bool

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "revoked": self.revoked,
        }


def _record(row: sqlite3.Row) -> TokenRecord:
    return TokenRecord(
        id=row["id"],
        role=row["role"],
        name=row["name"],
        prefix=row["prefix"],
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        expires_at=row["expires_at"],
        revoked=bool(row["revoked"]),
    )


class TokenStore:
    """Token table in one SQLite file. No I/O until the first method call."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._ready = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        if not self._ready:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_SCHEMA)
            conn.commit()
            self._ready = True
        return conn

    def _insert(
        self, conn, role: str, name: str, token: str, expires_at: str | None
    ) -> IssuedToken:
        created_at = _iso(_now())
        prefix = token[:PREFIX_LEN]
        cur = conn.execute(
            "INSERT INTO tokens (role, name, token_hash, prefix, created_at, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (role, name, _hash(token), prefix, created_at, expires_at),
        )
        return IssuedToken(cur.lastrowid, name, prefix, token, created_at, expires_at)

    def create_user_token(self, name: str) -> IssuedToken:
        name = name.strip()
        if not name:
            raise ValueError("token name must not be blank")
        token = USER_PREFIX + secrets.token_urlsafe(32)
        with closing(self._connect()) as conn, conn:
            return self._insert(conn, "user", name, token, None)

    def issue_admin_token(self, ttl_minutes: int) -> IssuedToken:
        now = _now()
        token = ADMIN_PREFIX + secrets.token_urlsafe(32)
        expires_at = _iso(now + timedelta(minutes=ttl_minutes))
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "DELETE FROM tokens WHERE role = 'admin' AND expires_at <= ?", (_iso(now),)
            )
            return self._insert(conn, "admin", ADMIN_TOKEN_NAME, token, expires_at)

    def authenticate(self, token: str) -> TokenRecord | None:
        """Return the record for a known, unrevoked, unexpired token; None otherwise."""
        now = _iso(_now())
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM tokens WHERE token_hash = ? AND revoked = 0"
                " AND (expires_at IS NULL OR expires_at > ?)",
                (_hash(token), now),
            ).fetchone()
            if row is None:
                return None
            if row["role"] == "user":
                conn.execute("UPDATE tokens SET last_used_at = ? WHERE id = ?", (now, row["id"]))
                row = conn.execute(
                    f"SELECT {_COLUMNS} FROM tokens WHERE id = ?", (row["id"],)
                ).fetchone()
            return _record(row)

    def list_user_tokens(self, include_revoked: bool = True) -> list[TokenRecord]:
        query = f"SELECT {_COLUMNS} FROM tokens WHERE role = 'user'"
        if not include_revoked:
            query += " AND revoked = 0"
        with closing(self._connect()) as conn:
            return [_record(row) for row in conn.execute(query + " ORDER BY id")]

    def revoke_user_token(self, token_id: int) -> bool:
        """Revoke a user token. True if it exists (already revoked included), False otherwise."""
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "UPDATE tokens SET revoked = 1 WHERE id = ? AND role = 'user'", (token_id,)
            )
            return cur.rowcount > 0
