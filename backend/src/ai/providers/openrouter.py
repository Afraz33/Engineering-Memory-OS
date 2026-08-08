from __future__ import annotations

import os
from typing import AsyncIterator

import httpx

from ai.providers.base import BaseProvider
from ai.providers.types import ChatMessage, EmbeddingVector

_BASE_URL = "https://openrouter.ai/api/v1/"
_DEFAULT_MODEL = "google/gemini-2.5-flash-lite-preview-06-17:free"


class OpenRouterProvider(BaseProvider):
    """
    Provider backed by OpenRouter (openrouter.ai).
    Supports any model on the platform — default is Gemini 2.0 Flash (free tier).

    Env vars:
        OPENROUTER_API_KEY  (required)
        OPENROUTER_MODEL    (optional, default: google/gemini-2.0-flash-001)
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        resolved_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not resolved_key:
            raise ValueError("OPENROUTER_API_KEY is required.")

        self._model = model or os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL)
        self._headers = {
            "Authorization": f"Bearer {resolved_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/engineering-memory-os",
            "X-Title": "Engineering Memory OS",
        }
        self._client = httpx.AsyncClient(headers=self._headers, timeout=120)

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                   max_tokens: int | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "messages": self._convert(messages),
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        r = await self._client.post(f"{_BASE_URL}chat/completions", json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    async def stream(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        import json

        payload: dict = {
            "model": self._model,
            "messages": self._convert(messages),
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with self._client.stream("POST", f"{_BASE_URL}chat/completions", json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                content = chunk["choices"][0].get("delta", {}).get("content")
                if content:
                    yield content

    async def embed(self, text: str) -> EmbeddingVector:
        # OpenRouter doesn't expose embeddings — raise clearly so callers know
        raise NotImplementedError("OpenRouter does not support embeddings. Use a dedicated embedding provider.")

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _convert(messages: list[ChatMessage]) -> list[dict]:
        # OpenAI format uses "assistant" not "model"
        role_map = {"model": "assistant"}
        return [{"role": role_map.get(m["role"], m["role"]), "content": m["content"]} for m in messages]
