import json
import threading

import pytest
from structlog.testing import capture_logs


def _store(**kwargs):
    from src.state.kv_store import KVStore

    params = {"max_value_bytes": 65536, "max_keys": 1000, "state_file": None}
    params.update(kwargs)
    return KVStore(**params)


# US5 — contract


def test_set_new_then_overwrite():
    store = _store()
    assert store.set("users/1", {"name": "Ana"}) == {"ok": True, "key": "users/1", "created": True}
    assert store.set("users/1", {"name": "Bia"}) == {
        "ok": True,
        "key": "users/1",
        "created": False,
    }
    assert store.get("users/1") == {"found": True, "key": "users/1", "value": {"name": "Bia"}}


def test_get_missing():
    assert _store().get("users/9") == {"found": False, "key": "users/9"}


@pytest.mark.parametrize(
    "value", ["text", 42, 3.5, True, False, None, [1, "a", None], {"a": {"b": [1, 2]}}]
)
def test_json_types_round_trip(value):
    store = _store()
    store.set("k", value)
    got = store.get("k")["value"]
    assert got == value
    assert type(got) is type(value)


def test_list_sorted_and_filtered():
    store = _store()
    for key in ["users/2", "orders/1", "users/1", "users10"]:
        store.set(key, 1)
    assert store.list("users/") == {"prefix": "users/", "keys": ["users/1", "users/2"]}
    assert store.list("") == {"prefix": "", "keys": ["orders/1", "users/1", "users/2", "users10"]}
    assert store.list() == store.list("")


def test_delete_present_and_missing():
    store = _store()
    store.set("users/1", 1)
    assert store.delete("users/1") == {"deleted": True, "key": "users/1"}
    assert store.get("users/1") == {"found": False, "key": "users/1"}
    assert store.delete("users/1") == {"deleted": False, "key": "users/1"}


@pytest.mark.parametrize("key", ["", "x" * 257, 5, None])
def test_invalid_keys_rejected(key):
    from src.state.kv_store import KVError

    store = _store()
    store.set("keep", 1)
    for call in (lambda: store.set(key, 1), lambda: store.get(key), lambda: store.delete(key)):
        with pytest.raises(KVError, match="invalid key"):
            call()
    assert store.list() == {"prefix": "", "keys": ["keep"]}


def test_key_of_256_chars_accepted():
    store = _store()
    assert store.set("x" * 256, 1)["created"] is True


def test_concurrent_sets_no_lost_updates():
    store = _store()

    def worker(t):
        for i in range(50):
            store.set(f"t{t}/{i}", i)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(20)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(store.list()["keys"]) == 1000


# US6 — persistence


def _from_settings(tmp_path, monkeypatch, **env):
    from src.config.settings import Settings
    from src.state.kv_store import KVStore

    for name in ("STATE_FILE", "KV_MAX_VALUE_BYTES", "KV_MAX_KEYS"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None, llm_api_key="k", llm_model="m", **env)
    return KVStore.from_settings(settings)


def test_no_state_file_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = _from_settings(tmp_path, monkeypatch)
    store.set("k", 1)
    assert store.state_file is None
    assert list(tmp_path.iterdir()) == []


def test_missing_file_starts_empty_then_created(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    store = _from_settings(tmp_path, monkeypatch, state_file=str(path))
    assert store.list()["keys"] == []
    assert not path.exists()
    store.set("users/1", {"name": "Ana"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"users/1": {"name": "Ana"}}


def test_reload_preserves_values_and_deletes(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    values = {"s": "ção", "i": 1, "f": 1.5, "b": True, "n": None, "l": [1], "d": {"a": 1}}
    store = _from_settings(tmp_path, monkeypatch, state_file=str(path))
    for key, value in values.items():
        store.set(key, value)
    store.set("gone", 1)
    store.delete("gone")

    reloaded = _from_settings(tmp_path, monkeypatch, state_file=str(path))
    assert reloaded.list()["keys"] == sorted(values)
    for key, value in values.items():
        got = reloaded.get(key)["value"]
        assert got == value
        assert type(got) is type(value)


def test_interrupted_save_keeps_old_state(tmp_path, monkeypatch):
    from src.state import kv_store
    from src.state.kv_store import KVError

    path = tmp_path / "state.json"
    store = _from_settings(tmp_path, monkeypatch, state_file=str(path))
    store.set("a", 1)
    before = path.read_bytes()

    def boom(*args, **kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr(kv_store.os, "replace", boom)
    with capture_logs() as logs:
        with pytest.raises(KVError, match="storage write failed"):
            store.set("b", 2)
        with pytest.raises(KVError, match="storage write failed"):
            store.set("a", 99)
        with pytest.raises(KVError, match="storage write failed"):
            store.delete("a")

    assert store.list()["keys"] == ["a"]
    assert store.get("a")["value"] == 1
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]
    failures = [e for e in logs if e["event"] == "kv_save_failed"]
    assert failures and failures[0]["error_class"] == "OSError"


@pytest.mark.parametrize("content", ["not json", "[]", '"x"'])
def test_invalid_state_file_exits(tmp_path, monkeypatch, capsys, content):
    path = tmp_path / "state.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _from_settings(tmp_path, monkeypatch, state_file=str(path))
    assert exc.value.code == 1
    assert f"invalid state file {path}" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == content


def test_over_limit_state_file_loads_with_warning(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"a": 1, "b": 2, "c": 3}), encoding="utf-8")
    with capture_logs() as logs:
        store = _from_settings(tmp_path, monkeypatch, state_file=str(path), kv_max_keys=2)
    assert store.list()["keys"] == ["a", "b", "c"]
    assert any(e["event"] == "kv_state_over_limit" for e in logs)
