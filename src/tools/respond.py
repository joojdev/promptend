import base64
import mimetypes
from pathlib import Path

from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field

_FILES_ROOT = Path("files").resolve()


def _safe_resolve(path: str) -> Path:
    resolved = (_FILES_ROOT / path).resolve()
    if not resolved.is_relative_to(_FILES_ROOT):
        raise ToolException(f"Path '{path}' is outside the files/ directory")
    return resolved


def _respond(
    body: str | dict,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    content_type: str = "application/json",
) -> dict:
    return {
        "body": body,
        "status_code": status_code,
        "headers": headers or {},
        "content_type": content_type,
    }


class RespondInput(BaseModel):
    body: str | dict = Field(description="Response body. Plain string or a JSON object.")
    status_code: int = Field(default=200, description="HTTP status code (e.g. 200, 201, 400, 404).")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Extra HTTP response headers."
    )
    content_type: str = Field(
        default="application/json",
        description="Content-Type header value. Defaults to application/json.",
    )


class RespondTool(BaseTool):
    name: str = "respond"
    description: str = (
        "Send the final HTTP response to the client and end the conversation. "
        "Always call this tool when you are ready to respond. "
        "Set 'body' to a string or JSON object, 'status_code' to the appropriate HTTP code, "
        "'headers' to any extra response headers, and 'content_type' if needed."
    )
    args_schema: type[BaseModel] = RespondInput
    return_direct: bool = True

    def _run(
        self,
        body: str | dict,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str = "application/json",
    ) -> dict:
        if isinstance(body, str) and not body.strip():
            raise ToolException("body must not be empty")
        return _respond(body, status_code, headers, content_type)


class RespondWithFileInput(BaseModel):
    path: str = Field(
        description="Path to the file inside files/, e.g. 'index.html' or 'css/style.css'."
    )
    status_code: int = Field(default=200, description="HTTP status code.")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Extra HTTP response headers."
    )


class RespondWithFileTool(BaseTool):
    name: str = "respond_with_file"
    description: str = (
        "Send a file from the files/ directory as the HTTP response. "
        "Automatically detects the Content-Type from the file extension. "
        "Use this instead of 'respond' when you want to serve a static file."
    )
    args_schema: type[BaseModel] = RespondWithFileInput
    return_direct: bool = True

    def _run(
        self,
        path: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> dict:
        resolved = _safe_resolve(path)
        if not resolved.exists():
            raise ToolException(f"File not found: {path}")
        if not resolved.is_file():
            raise ToolException(f"Path is not a file: {path}")
        mime, _ = mimetypes.guess_type(str(resolved))
        content_type = mime or "application/octet-stream"
        raw = resolved.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        result = _respond(encoded, status_code, headers, content_type)
        result["_base64"] = True
        return result
