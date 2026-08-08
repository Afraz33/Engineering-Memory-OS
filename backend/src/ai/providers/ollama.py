from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from ai.providers.base import BaseProvider
from ai.providers.types import ChatMessage, EmbeddingVector


class OllamaProvider(BaseProvider):
    def __init__(self, model: str = "qwen3:0.6b", base_url: str = "http://localhost:11434",
                 timeout: int = 120) -> None:
        self._model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                   max_tokens: int | None = None) -> str:
        payload: dict = {"model": self._model, "messages": messages, "stream": False,
                         "options": {"temperature": temperature}}
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        try:
            r = await self.client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama error: {e}") from e

    async def stream(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        payload: dict = {"model": self._model, "messages": messages, "stream": True,
                         "options": {"temperature": temperature}}
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        try:
            async with self.client.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if line:
                        chunk = json.loads(line).get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama error: {e}") from e

    async def embed(self, text: str) -> EmbeddingVector:
        try:
            r = await self.client.post(f"{self.base_url}/api/embed",
                                       json={"model": self._model, "input": text})
            r.raise_for_status()
            return r.json().get("embeddings", [[]])[0]
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama error: {e}") from e

    async def close(self) -> None:
        await self.client.aclose()
