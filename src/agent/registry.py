from langchain_core.tools import BaseTool

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
