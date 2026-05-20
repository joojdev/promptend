from pathlib import Path

from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field

from src.tools.respond import _safe_resolve

_FILES_ROOT = Path("files").resolve()


class StatFileInput(BaseModel):
    path: str = Field(description="Path to the file inside files/, e.g. 'index.html'.")


class StatFileTool(BaseTool):
    name: str = "stat_file"
    description: str = (
        "Return metadata about a file in the files/ sandbox: path, line count, and size in bytes."
    )
    args_schema: type[BaseModel] = StatFileInput

    def _run(self, path: str) -> dict:
        resolved = _safe_resolve(path)
        if not resolved.exists():
            raise ToolException(f"File not found: {path}")
        if not resolved.is_file():
            raise ToolException(f"Path is not a file: {path}")
        content = resolved.read_text(encoding="utf-8", errors="replace")
        return {
            "path": path,
            "lines": len(content.splitlines()),
            "size_bytes": resolved.stat().st_size,
        }
