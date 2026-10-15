import threading

import pytest


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
