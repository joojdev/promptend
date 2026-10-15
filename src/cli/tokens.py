"""Manage user tokens from the command line: create, list, revoke, hash-password.

Works with the server stopped and needs no LLM settings.
"""

import argparse
import getpass
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.auth.passwords import hash_password
from src.auth.tokens import TokenStore

_COLUMNS = (("ID", 4), ("NAME", 20), ("PREFIX", 10), ("CREATED AT", 26), ("LAST USED", 26))


class TokenSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tokens_db_path: str = "data/tokens.db"


def _row(values: list[str]) -> str:
    cells = [value.ljust(width) for value, (_, width) in zip(values, _COLUMNS, strict=False)]
    return "  ".join([*cells, values[-1]]).rstrip()


def _create(store: TokenStore, args) -> int:
    try:
        issued = store.create_user_token(args.name)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f'Created token #{issued.id} "{issued.name}"')
    print(issued.token)
    print("Store it now: it will not be shown again.")
    return 0


def _list(store: TokenStore, args) -> int:
    records = store.list_user_tokens(include_revoked=args.all)
    if not records:
        print("No tokens.")
        return 0
    print(_row([name for name, _ in _COLUMNS] + ["STATUS"]))
    for r in records:
        status = "revoked" if r.revoked else "active"
        print(_row([str(r.id), r.name, r.prefix, r.created_at, r.last_used_at or "never", status]))
    return 0


def _revoke(store: TokenStore, args) -> int:
    if not store.revoke_user_token(args.id):
        print(f"Token #{args.id} not found.", file=sys.stderr)
        return 1
    print(f"Revoked token #{args.id}.")
    return 0


def _hash_password(args) -> int:
    password = getpass.getpass("Password: ")
    if not password:
        print("Error: password must not be empty.", file=sys.stderr)
        return 1
    if getpass.getpass("Repeat password: ") != password:
        print("Error: passwords do not match.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tokens", description="Manage API tokens.")
    parser.add_argument("--db", help="token store path (default: TOKENS_DB_PATH or data/tokens.db)")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="create a user token and print it once")
    create.add_argument("name")
    listing = sub.add_parser("list", help="list user tokens")
    listing.add_argument("--all", action="store_true", help="include revoked tokens")
    revoke = sub.add_parser("revoke", help="revoke a user token by id")
    revoke.add_argument("id", type=int)
    sub.add_parser("hash-password", help="print an argon2 hash for ADMIN_PASSWORD_HASH")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "hash-password":
        return _hash_password(args)
    store = TokenStore(args.db or TokenSettings().tokens_db_path)
    handlers = {"create": _create, "list": _list, "revoke": _revoke}
    return handlers[args.command](store, args)


if __name__ == "__main__":
    sys.exit(main())
