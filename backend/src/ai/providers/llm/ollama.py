"""Ollama LLM adapter.

Uses Ollama's HTTP API (/api/chat) for local LLM inference.
Configured via `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, and `OLLAMA_MODEL`.
"""

import json
import os
import urllib.request
from collections.abc import AsyncIterator, Sequence
import asyncio

from ai.providers.llm.base import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    ProviderError,
    Usage,
)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "minicpm-v4.6:1b"
# "qwen2.5:0.5b" 

def _get_default_url() -> str:
    url = os.getenv("OLLAMA_BASE_URL")
    if url:
        return url.rstrip("/")
    # If running inside a container, test host endpoints
    if os.path.exists("/.dockerenv"):
        for host in ["host.docker.internal", "172.17.0.1"]:
            try:
                urllib.request.urlopen(f"http://{host}:11434/api/tags", timeout=1)
                return f"http://{host}:11434"
            except Exception:
                pass
    return DEFAULT_BASE_URL


class OllamaProvider(ChatProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or _get_default_url()).rstrip("/")
        self.default_model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

    def _build_payload(
        self,
        messages: Sequence[ChatMessage],
        system: str | None = None,
        stream: bool = False,
    ) -> dict:
        formatted_messages = []
        if system:
            formatted_messages.append({"role": "system", "content": system})
        for m in messages:
            formatted_messages.append({"role": m.role, "content": m.content})

        return {
            "model": self.default_model,
            "messages": formatted_messages,
            "stream": stream,
        }

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        url = f"{self.base_url}/api/chat"
        payload = self._build_payload(messages, system=system, stream=False)
        data_bytes = json.dumps(payload).encode("utf-8")

        def _do_request():
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                raise ProviderError(f"Ollama request failed: {exc}") from exc

        res_data = await asyncio.to_thread(_do_request)

        content = res_data.get("message", {}).get("content", "")
        eval_count = res_data.get("eval_count", 0)
        prompt_eval_count = res_data.get("prompt_eval_count", 0)

        return ChatResponse(
            content=content,
            model=res_data.get("model", self.default_model),
            provider=self.name,
            usage=Usage(
                input_tokens=prompt_eval_count,
                output_tokens=eval_count,
            ),
        )

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/api/chat"
        payload = self._build_payload(messages, system=system, stream=True)
        data_bytes = json.dumps(payload).encode("utf-8")

        q: asyncio.Queue[str | None | Exception] = asyncio.Queue()

        def _worker():
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    for line in resp:
                        if not line:
                            continue
                        chunk = json.loads(line.decode("utf-8"))
                        text = chunk.get("message", {}).get("content", "")
                        if text:
                            asyncio.run_coroutine_threadsafe(q.put(text), loop)
                        if chunk.get("done"):
                            break
                asyncio.run_coroutine_threadsafe(q.put(None), loop)
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(q.put(exc), loop)

        loop = asyncio.get_running_loop()
        asyncio.create_task(asyncio.to_thread(_worker))

        while True:
            item = await q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise ProviderError(f"Ollama stream failed: {item}") from item
            yield item
