import pytest
from langchain_core.tools import ToolException


# T021
def test_respond_tool_returns_reply():
    from src.tools.respond import RespondTool

    tool = RespondTool()
    result = tool.invoke({"reply": "hello"})
    assert result == "hello"


def test_respond_tool_raises_on_empty_reply():
    from src.tools.respond import RespondTool

    tool = RespondTool()
    with pytest.raises(ToolException):
        tool.invoke({"reply": ""})
