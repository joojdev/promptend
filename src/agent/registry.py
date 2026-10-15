from langchain_core.tools import BaseTool

from src.state.kv_store import KVStore
from src.tools.kv import KVDeleteTool, KVGetTool, KVListTool, KVSetTool
from src.tools.list_files import ListFilesTool
from src.tools.read_file import ReadFileTool
from src.tools.respond import RespondTool, RespondWithFileTool
from src.tools.stat_file import StatFileTool

TOOLS: list[BaseTool] = [
    RespondTool(),
    RespondWithFileTool(),
    ListFilesTool(),
    StatFileTool(),
    ReadFileTool(),
]


# Role-restricted tools: every tool here is offered to admin runs; a tool is offered to user
# runs only if its role is "user" (the default when it declares none). To add an admin-only tool:
#   1. Define a BaseTool subclass with the class field `role: str = "admin"`.
#   2. Add an instance to the list returned by build_tools() below.
# Routes, auth and the harness need no change.
def build_tools(store: KVStore) -> list[BaseTool]:
    return [
        RespondTool(),
        RespondWithFileTool(),
        ListFilesTool(),
        StatFileTool(),
        ReadFileTool(),
        KVSetTool(store=store),
        KVGetTool(store=store),
        KVListTool(store=store),
        KVDeleteTool(store=store),
    ]
