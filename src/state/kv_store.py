import threading
from pathlib import Path
from typing import Any

JSONValue = str | int | float | bool | None | list[Any] | dict[str, Any]

MAX_KEY_LENGTH = 256


class KVError(Exception):
    """A storage operation was rejected; the message is meant for the agent."""


def _check_key(key) -> None:
    if not isinstance(key, str) or not 1 <= len(key) <= MAX_KEY_LENGTH:
        raise KVError(f"invalid key: must be a string of 1-{MAX_KEY_LENGTH} characters")


class KVStore:
    """Thread-safe key-value store shared by every request of one app."""

    def __init__(
        self,
        max_value_bytes: int,
        max_keys: int,
        state_file: Path | None = None,
        data: dict[str, JSONValue] | None = None,
    ):
        self.max_value_bytes = max_value_bytes
        self.max_keys = max_keys
        self.state_file = state_file
        self._data: dict[str, JSONValue] = dict(data or {})
        self._lock = threading.Lock()

    def set(self, key: str, value: JSONValue) -> dict:
        _check_key(key)
        with self._lock:
            created = key not in self._data
            self._data[key] = value
        return {"ok": True, "key": key, "created": created}

    def get(self, key: str) -> dict:
        _check_key(key)
        with self._lock:
            if key not in self._data:
                return {"found": False, "key": key}
            return {"found": True, "key": key, "value": self._data[key]}

    def list(self, prefix: str = "") -> dict:
        with self._lock:
            keys = sorted(k for k in self._data if k.startswith(prefix))
        return {"prefix": prefix, "keys": keys}

    def delete(self, key: str) -> dict:
        _check_key(key)
        with self._lock:
            if key not in self._data:
                return {"deleted": False, "key": key}
            del self._data[key]
        return {"deleted": True, "key": key}
