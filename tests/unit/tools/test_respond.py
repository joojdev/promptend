import pytest
from langchain_core.tools import ToolException


# T021
def test_respond_tool_returns_structured_response():
    from src.tools.respond import RespondTool

    tool = RespondTool()
    result = tool.invoke({"body": "hello"})
    assert result == {
        "body": "hello",
        "status_code": 200,
        "headers": {},
        "content_type": "application/json",
    }


def test_respond_tool_custom_status_and_headers():
    from src.tools.respond import RespondTool

    tool = RespondTool()
    result = tool.invoke({"body": {"id": 1}, "status_code": 201, "headers": {"X-Foo": "bar"}})
    assert result["status_code"] == 201
    assert result["headers"] == {"X-Foo": "bar"}
    assert result["body"] == {"id": 1}


def test_respond_tool_raises_on_empty_body():
    from src.tools.respond import RespondTool

    tool = RespondTool()
    with pytest.raises(ToolException):
        tool.invoke({"body": ""})
