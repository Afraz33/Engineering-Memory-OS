"""Anthropic (Claude) adapter.

Not wired up by default — set `LLM_PROVIDER=anthropic` and
`uv add anthropic` to switch to it.
"""

import os
from collections.abc import AsyncIterator, Sequence
from functools import cached_property

from ai.providers.llm.base import ChatMessage, ChatProvider, ChatResponse, ProviderError, Usage

DEFAULT_MODEL = "claude-opus-5"
# Thinking is on by default on Opus 5 and max_tokens caps thinking + reply
# together, so keep this well above the expected answer length.
DEFAULT_MAX_TOKENS = 8192


class AnthropicProvider(ChatProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.default_model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")

    @cached_property
    def _client(self):
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self.api_key)

    def _build(self, messages, system):
        kwargs = {
            "model": self.default_model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            kwargs["system"] = system
        return kwargs

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        try:
            response = await self._client.messages.create(
                **self._build(messages, system)
            )
        except Exception as exc:
            raise ProviderError(f"anthropic request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            raise ProviderError("anthropic declined this request")

        text = "".join(b.text for b in response.content if b.type == "text")
        return ChatResponse(
            content=text,
            model=response.model,
            provider=self.name,
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        try:
            async with self._client.messages.stream(
                **self._build(messages, system)
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            raise ProviderError(f"anthropic stream failed: {exc}") from exc
