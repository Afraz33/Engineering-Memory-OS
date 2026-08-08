from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

from ai.memory.manager import MemoryManager
from ai.providers.base import BaseProvider

ToolHandler = Callable[..., Any]


@dataclass
class TurnResult:
    session_id: str
    response: str
    tool_calls: list[dict] = field(default_factory=list)
    error: str | None = None


class Orchestrator:
    def __init__(
        self,
        provider: BaseProvider,
        memory: MemoryManager,
        tools: dict[str, ToolHandler] | None = None,
        max_tool_rounds: int = 5,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> None:
        self._provider = provider
        self._memory = memory
        self._tools: dict[str, ToolHandler] = tools or {}
        self._max_tool_rounds = max_tool_rounds
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def run(self, session_id: str, user_input: str) -> TurnResult:
        self._memory.add_user_turn(user_input)
        tool_calls_log: list[dict] = []
        error: str | None = None
        final_response = ""
        try:
            final_response, tool_calls_log = await self._run_turn()
        except Exception as exc:
            error = str(exc)
        if final_response:
            self._memory.add_model_turn(final_response)
        return TurnResult(session_id=session_id, response=final_response,
                          tool_calls=tool_calls_log, error=error)

    async def stream(self, session_id: str, user_input: str) -> AsyncIterator[str]:
        self._memory.add_user_turn(user_input)
        context = self._memory.build_context()
        full_response = ""
        async for chunk in self._provider.stream(context, temperature=self._temperature, max_tokens=self._max_tokens):
            full_response += chunk
            yield chunk
        if full_response:
            self._memory.add_model_turn(full_response)

    def register_tool(self, name: str, handler: ToolHandler) -> None:
        self._tools[name] = handler

    async def _run_turn(self) -> tuple[str, list[dict]]:
        tool_calls_log: list[dict] = []
        response = ""
        for _ in range(self._max_tool_rounds):
            context = self._memory.build_context()
            response = await self._provider.chat(context, temperature=self._temperature, max_tokens=self._max_tokens)
            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                return response, tool_calls_log
            for call in tool_calls:
                tool_calls_log.append(call)
                result = await self._dispatch_tool(call)
                self._memory.handle_tool_result(call["name"], call["args"], result)
        return response, tool_calls_log

    async def _dispatch_tool(self, call: dict) -> Any:
        name = call["name"]
        args = call.get("args", {})
        handler = self._tools.get(name)
        if handler is None:
            return f"error: unknown tool '{name}'"
        if asyncio.iscoroutinefunction(handler):
            return await handler(**args)
        return handler(**args)

    def _extract_tool_calls(self, response: str) -> list[dict]:
        # Placeholder — wire Gemini function calling here when ready
        return []
