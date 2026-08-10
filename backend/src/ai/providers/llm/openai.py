"""OpenAI adapter.

Not wired up by default — set `LLM_PROVIDER=openai` and `uv add openai`
to switch to it.
"""

import os
from collections.abc import AsyncIterator, Sequence
from functools import cached_property

from ai.providers.llm.base import ChatMessage, ChatProvider, ChatResponse, ProviderError, Usage

DEFAULT_MODEL = "gpt-4.1"
DEFAULT_MAX_TOKENS = 4096


class OpenAIProvider(ChatProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.default_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not set")

    @cached_property
    def _client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.api_key)

    def _build(self, messages, system):
        payload = [{"role": m.role, "content": m.content} for m in messages]
        if system:
            payload.insert(0, {"role": "system", "content": system})
        return {
            "model": self.default_model,
            "messages": payload,
            "max_completion_tokens": DEFAULT_MAX_TOKENS,
        }

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        try:
            response = await self._client.chat.completions.create(
                **self._build(messages, system)
            )
        except Exception as exc:
            raise ProviderError(f"openai request failed: {exc}") from exc

        usage = response.usage
        return ChatResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider=self.name,
            usage=Usage(
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
        )

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                stream=True,
                **self._build(messages, system),
            )
            async for chunk in stream:
                if chunk.choices and (delta := chunk.choices[0].delta.content):
                    yield delta
        except Exception as exc:
            raise ProviderError(f"openai stream failed: {exc}") from exc
