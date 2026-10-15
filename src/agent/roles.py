"""Caller roles and which tools each role's agent is offered."""

import sys

from langchain_core.tools import BaseTool

ROLES = ("user", "admin")


def tool_role(tool: BaseTool) -> str:
    """A tool's declared role; tools without a `role` field are user tools."""
    return getattr(tool, "role", "user")


def tools_for_role(tools: list[BaseTool], role: str) -> list[BaseTool]:
    """All tools for admin runs; only user tools for user runs. Exit 1 on an unknown tool role."""
    for tool in tools:
        declared = tool_role(tool)
        if declared not in ROLES:
            print(f"Error: tool '{tool.name}' declares unknown role '{declared}'", file=sys.stderr)
            sys.exit(1)
    if role == "admin":
        return list(tools)
    return [tool for tool in tools if tool_role(tool) == "user"]
