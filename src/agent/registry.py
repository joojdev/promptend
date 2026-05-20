from langchain_core.tools import BaseTool

from src.tools.respond import RespondTool

TOOLS: list[BaseTool] = [RespondTool()]
