import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

JSONValue = str | int | float | bool | None | list[Any] | dict[str, Any]

MAX_KEY_LENGTH = 256


class KVError(Exception):
    """A storage operation was rejected; the message is meant for the agent."""


def _check_key(key) -> None:
    if not isinstance(key, str) or not 1 <= len(key) <= MAX_KEY_LENGTH:
        raise KVError(f"invalid key: must be a string of 1-{MAX_KEY_LENGTH} characters")


def _value_size(value: JSONValue) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _load_state_file(path: Path) -> dict[str, JSONValue]:
    """Read a state file; exit 1 without touching it when the content is invalid."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        reason = f"{type(exc).__name__}: {exc}"
    else:
        if isinstance(data, dict):
            return data
        reason = f"root must be a JSON object, got {type(data).__name__}"
    print(f"Error: invalid state file {path}: {reason}", file=sys.stderr)
    sys.exit(1)


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

    @classmethod
    def from_settings(cls, settings) -> "KVStore":
        state_file = Path(settings.state_file.strip()) if settings.state_file.strip() else None
        data = _load_state_file(state_file) if state_file else {}
        store = cls(settings.kv_max_value_bytes, settings.kv_max_keys, state_file, data)
        oversized = [k for k, v in data.items() if _value_size(v) > store.max_value_bytes]
        if len(data) > store.max_keys or oversized:
            log.warning(
                "kv_state_over_limit",
                state_file=str(state_file),
                keys=len(data),
                max_keys=store.max_keys,
                oversized_values=len(oversized),
            )
        return store

    def _save(self) -> None:
        """Atomically rewrite the state file; caller holds the lock."""
        path = self.state_file
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _commit(self, undo) -> None:
        """Persist the change just applied to _data, or undo it and raise KVError."""
        if self.state_file is None:
            return
        try:
            self._save()
        except Exception as exc:
            undo()
            log.error("kv_save_failed", error_class=type(exc).__name__)
            raise KVError("storage write failed") from exc

    def set(self, key: str, value: JSONValue) -> dict:
        _check_key(key)
        size = _value_size(value)
        if size > self.max_value_bytes:
            raise KVError(
                f"value too large: {size} bytes exceeds KV_MAX_VALUE_BYTES ({self.max_value_bytes})"
            )
        with self._lock:
            created = key not in self._data
            if created and len(self._data) >= self.max_keys:
                raise KVError(
                    f"store full: KV_MAX_KEYS ({self.max_keys}) reached; "
                    "delete keys or overwrite an existing one"
                )
            previous = self._data.get(key)
            self._data[key] = value

            def undo():
                if created:
                    del self._data[key]
                else:
                    self._data[key] = previous

            self._commit(undo)
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
            previous = self._data.pop(key)
            self._commit(lambda: self._data.__setitem__(key, previous))
        return {"deleted": True, "key": key}
