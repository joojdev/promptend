from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel

_FILES_ROOT = Path("files").resolve()


def _build_tree(directory: Path, prefix: str = "") -> list[str]:
    entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = []
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            lines.extend(_build_tree(entry, prefix + extension))
    return lines


class ListFilesInput(BaseModel):
    pass


class ListFilesTool(BaseTool):
    name: str = "list_files"
    description: str = (
        "List all files and directories inside the files/ sandbox as a tree. "
        "Use this to discover what files are available before reading or serving them."
    )
    args_schema: type[BaseModel] = ListFilesInput

    def _run(self) -> str:
        if not _FILES_ROOT.exists():
            return "files/\n(empty)"
        lines = ["files/"] + _build_tree(_FILES_ROOT)
        return "\n".join(lines) if lines else "files/\n(empty)"
