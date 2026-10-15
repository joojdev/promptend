import json

import pytest


@pytest.fixture()
def tools():
    from src.state.kv_store import KVStore
    from src.tools.kv import KVDeleteTool, KVGetTool, KVListTool, KVSetTool

    store = KVStore(max_value_bytes=65536, max_keys=1000)
    return {
        "set": KVSetTool(store=store),
        "get": KVGetTool(store=store),
        "list": KVListTool(store=store),
        "delete": KVDeleteTool(store=store),
    }


def test_tool_names(tools):
    assert [t.name for t in tools.values()] == ["kv_set", "kv_get", "kv_list", "kv_delete"]


def test_tools_follow_contract(tools):
    out = json.loads(tools["set"].invoke({"key": "users/1", "value": {"name": "Ana"}}))
    assert out == {"ok": True, "key": "users/1", "created": True}
    out = json.loads(tools["get"].invoke({"key": "users/1"}))
    assert out == {"found": True, "key": "users/1", "value": {"name": "Ana"}}
    assert json.loads(tools["list"].invoke({"prefix": "users/"})) == {
        "prefix": "users/",
        "keys": ["users/1"],
    }
    assert json.loads(tools["list"].invoke({})) == {"prefix": "", "keys": ["users/1"]}
    assert json.loads(tools["delete"].invoke({"key": "users/1"})) == {
        "deleted": True,
        "key": "users/1",
    }
    assert json.loads(tools["get"].invoke({"key": "users/1"})) == {
        "found": False,
        "key": "users/1",
    }


def test_store_error_returned_as_text(tools):
    out = tools["get"].invoke({"key": ""})
    assert "invalid key" in out


@pytest.mark.parametrize("value", [{"a": 1}, [1, 2], 7, 2.5, True, None, "s"])
def test_kv_set_accepts_any_json_value(tools, value):
    json.loads(tools["set"].invoke({"key": "k", "value": value}))
    got = json.loads(tools["get"].invoke({"key": "k"}))["value"]
    assert got == value
    assert type(got) is type(value)
