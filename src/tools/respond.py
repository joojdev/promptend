from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field


class RespondInput(BaseModel):
    reply: str = Field(description="The final reply text to send to the user.")


class RespondTool(BaseTool):
    name: str = "respond"
    description: str = (
        "Send a final reply to the user and end the conversation. "
        "Always call this tool when you are ready to respond."
    )
    args_schema: type[BaseModel] = RespondInput
    return_direct: bool = True

    def _run(self, reply: str) -> str:
        if not reply.strip():
            raise ToolException("reply must not be empty")
        return reply
