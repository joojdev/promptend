import pytest
from langchain_core.tools import BaseTool

from src.agent.registry import build_tools
from src.agent.roles import ROLES, tool_role, tools_for_role
from src.state.kv_store import KVStore


class PlainTool(BaseTool):
    name: str = "plain"
    description: str = "no role declared"

    def _run(self) -> str:
        return "ok"


class AdminTool(PlainTool):
    name: str = "admin_tool"
    role: str = "admin"


class RootTool(PlainTool):
    name: str = "root_tool"
    role: str = "root"


def test_roles():
    assert ROLES == ("user", "admin")


def test_default_role_is_user():
    assert tool_role(PlainTool()) == "user"
    assert tool_role(AdminTool()) == "admin"


def test_tools_for_role():
    user, admin = PlainTool(), AdminTool()
    assert tools_for_role([user, admin], "admin") == [user, admin]
    assert tools_for_role([user, admin], "user") == [user]


def test_unknown_role_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        tools_for_role([PlainTool(), RootTool()], "admin")
    assert exc.value.code == 1
    assert "tool 'root_tool' declares unknown role 'root'" in capsys.readouterr().err


def test_builtin_tools_are_user_tools():
    tools = build_tools(KVStore(1000, 10))
    assert all(tool_role(t) == "user" for t in tools)
    assert tools_for_role(tools, "user") == tools
