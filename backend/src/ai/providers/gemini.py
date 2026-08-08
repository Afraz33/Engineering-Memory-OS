from __future__ import annotations

import os
from typing import AsyncIterator

from google import genai
from google.genai import types as genai_types

from ai.providers.base import BaseProvider
from ai.providers.types import ChatMessage, EmbeddingVector

_DEFAULT_CHAT_MODEL = "gemini-2.0-flash"
_DEFAULT_EMBED_MODEL = "text-embedding-004"

_ROLE_MAP = {"user": "user", "model": "model", "assistant": "model"}


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 embed_model: str | None = None) -> None:
        resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not resolved_key:
            raise ValueError("Gemini API key required. Set GEMINI_API_KEY env var.")

        self._model_name = model or os.getenv("GEMINI_MODEL", _DEFAULT_CHAT_MODEL)
        self._embed_model_name = embed_model or os.getenv("GEMINI_EMBED_MODEL", _DEFAULT_EMBED_MODEL)
        self._client = genai.Client(api_key=resolved_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    # chat

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                   max_tokens: int | None = None) -> str:
        system, history, last_user = self._prepare(messages)
        config = self._gen_config(temperature, max_tokens, system)
        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=history + [{"role": "user", "parts": [{"text": last_user}]}],
            config=config,
        )
        return response.text or ""

    # streaming

    async def stream(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        system, history, last_user = self._prepare(messages)
        config = self._gen_config(temperature, max_tokens, system)
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self._model_name,
            contents=history + [{"role": "user", "parts": [{"text": last_user}]}],
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    # embeddings

    async def embed(self, text: str) -> EmbeddingVector:
        response = await self._client.aio.models.embed_content(
            model=self._embed_model_name,
            contents=text,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return response.embeddings[0].values

    async def embed_query(self, text: str) -> EmbeddingVector:
        response = await self._client.aio.models.embed_content(
            model=self._embed_model_name,
            contents=text,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return response.embeddings[0].values

    async def close(self) -> None:
        pass

    # internal

    def _prepare(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict], str]:
        system_parts: list[str] = []
        conversation: list[ChatMessage] = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                conversation.append(msg)
        if not conversation:
            raise ValueError("At least one non-system message is required.")
        last = conversation[-1]
        if last["role"] != "user":
            raise ValueError("Last message must be from 'user'.")
        history = [
            {"role": _ROLE_MAP.get(m["role"], m["role"]), "parts": [{"text": m["content"]}]}
            for m in conversation[:-1]
        ]
        system = "\n\n".join(system_parts) if system_parts else None
        return system, history, last["content"]

    def _gen_config(self, temperature: float, max_tokens: int | None,
                    system: str | None) -> genai_types.GenerateContentConfig:
        kwargs: dict = {"temperature": temperature}
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        if system:
            kwargs["system_instruction"] = system
        return genai_types.GenerateContentConfig(**kwargs)
