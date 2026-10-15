import json

from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field

from src.state.kv_store import KVError, KVStore


def _call(method, *args) -> str:
    try:
        result = method(*args)
    except KVError as exc:
        raise ToolException(str(exc)) from exc
    return json.dumps(result, ensure_ascii=False)


class KVSetInput(BaseModel):
    key: str = Field(description="Key shaped '<collection>/<id>', e.g. 'users/42'.")
    value: str | int | float | bool | list | dict | None = Field(
        description="Value to store: string, number, boolean, null, list or object."
    )


class KVSetTool(BaseTool):
    name: str = "kv_set"
    description: str = (
        "Store a JSON value under a key, replacing any previous value. "
        "Storage is shared across all requests; use keys like '<collection>/<id>'."
    )
    args_schema: type[BaseModel] = KVSetInput
    handle_tool_error: bool = True
    store: KVStore

    def _run(self, key: str, value=None) -> str:
        return _call(self.store.set, key, value)


class KVKeyInput(BaseModel):
    key: str = Field(description="Key shaped '<collection>/<id>', e.g. 'users/42'.")


class KVGetTool(BaseTool):
    name: str = "kv_get"
    description: str = (
        "Read the value stored under a key in the storage shared across requests. "
        "Returns found: false when the key does not exist."
    )
    args_schema: type[BaseModel] = KVKeyInput
    handle_tool_error: bool = True
    store: KVStore

    def _run(self, key: str) -> str:
        return _call(self.store.get, key)


class KVListInput(BaseModel):
    prefix: str = Field(default="", description="Only list keys starting with this, e.g. 'users/'.")


class KVListTool(BaseTool):
    name: str = "kv_list"
    description: str = (
        "List stored keys starting with a prefix, sorted. "
        "Use a prefix like 'users/' to list one collection; empty lists every key."
    )
    args_schema: type[BaseModel] = KVListInput
    handle_tool_error: bool = True
    store: KVStore

    def _run(self, prefix: str = "") -> str:
        return _call(self.store.list, prefix)


class KVDeleteTool(BaseTool):
    name: str = "kv_delete"
    description: str = (
        "Delete a key from the storage shared across requests. "
        "Returns deleted: false when the key did not exist."
    )
    args_schema: type[BaseModel] = KVKeyInput
    handle_tool_error: bool = True
    store: KVStore

    def _run(self, key: str) -> str:
        return _call(self.store.delete, key)
