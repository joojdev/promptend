from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field

from src.tools.respond import _safe_resolve


class ReadFileInput(BaseModel):
    path: str = Field(description="Path to the file inside files/, e.g. 'index.html'.")
    start_line: int = Field(default=1, description="1-based line number to start reading from.")
    num_lines: int = Field(default=50, description="Number of lines to read.")


class ReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = (
        "Read a slice of a file from the files/ sandbox. "
        "Specify start_line (1-based) and num_lines to read a specific excerpt. "
        "Use stat_file first to know the total line count."
    )
    args_schema: type[BaseModel] = ReadFileInput

    def _run(self, path: str, start_line: int = 1, num_lines: int = 50) -> str:
        if start_line < 1:
            raise ToolException("start_line must be >= 1")
        if num_lines < 1:
            raise ToolException("num_lines must be >= 1")
        resolved = _safe_resolve(path)
        if not resolved.exists():
            raise ToolException(f"File not found: {path}")
        if not resolved.is_file():
            raise ToolException(f"Path is not a file: {path}")
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        start = start_line - 1
        chunk = lines[start : start + num_lines]
        return "\n".join(f"{start_line + i:>6}\t{line}" for i, line in enumerate(chunk))
