"""Google AI Studio (Gemini) adapter."""

import os
from collections.abc import AsyncIterator, Sequence
from functools import cached_property

from ai.providers.llm.base import ChatMessage, ChatProvider, ChatResponse, ProviderError, Usage

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_MAX_TOKENS = 4096


class GeminiProvider(ChatProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self.default_model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        if not self.api_key:
            raise ProviderError("GOOGLE_API_KEY is not set")

    @cached_property
    def _client(self):
        from google import genai

        return genai.Client(api_key=self.api_key)

    def _build(self, messages, system):
        from google.genai import types

        contents = [
            types.Content(
                # Gemini calls the assistant role "model".
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part.from_text(text=m.content)],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=DEFAULT_MAX_TOKENS,
        )
        return contents, config

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        model = self.default_model
        contents, config = self._build(messages, system)
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as exc:  # SDK raises provider-specific errors
            raise ProviderError(f"gemini request failed: {exc}") from exc

        usage = response.usage_metadata
        return ChatResponse(
            content=response.text or "",
            model=model,
            provider=self.name,
            usage=Usage(
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            ),
        )

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        model = self.default_model
        contents, config = self._build(messages, system)
        try:
            chunks = await self._client.aio.models.generate_content_stream(
                model=model, contents=contents, config=config
            )
            async for chunk in chunks:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            raise ProviderError(f"gemini stream failed: {exc}") from exc
