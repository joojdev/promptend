import asyncio
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


class CountingFakeLLM(ToolCapableFakeLLM):
    """Counts how many times the model was invoked (sync or async)."""

    calls: int = 0
    prompts: list[str] = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        self.prompts.append("\n".join(str(m.content) for m in messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class SlowFakeLLM(ToolCapableFakeLLM):
    delay: float = 5.0

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        await asyncio.sleep(self.delay)
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class RaisingFakeLLM(ToolCapableFakeLLM):
    exc: Any = None

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise self.exc

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise self.exc
