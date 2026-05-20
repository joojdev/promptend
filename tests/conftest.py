from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


class ToolCapableFakeLLM(FakeListChatModel):
    """FakeListChatModel that supports bind_tools and can emit AIMessage with tool_calls."""

    queued_messages: list[AIMessage] = []

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable:
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatGeneration, ChatResult

        if self.queued_messages:
            msg = self.queued_messages.pop(0)
        else:
            from langchain_core.messages import AIMessage as AI

            msg = AI(content=self.responses[0] if self.responses else "")
        return ChatResult(generations=[ChatGeneration(message=msg)])
