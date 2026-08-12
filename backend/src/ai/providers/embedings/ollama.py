"""Ollama Embedding provider.

Uses Ollama's HTTP API (/api/embed) for local text vector embeddings.
Default model: granite-embedding:30m (384 dimension).
"""

import asyncio
import json
import os
import urllib.request
from typing import Sequence

from .base import EmbeddingProvider, EmbeddingResponse, ProviderError

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "nomic-embed-text:latest"
# "qwen3-embedding:0.6b"
# "granite-embedding:30m"


def _get_default_url() -> str:
    url = os.getenv("OLLAMA_BASE_URL")
    if url:
        return url.rstrip("/")
    if os.path.exists("/.dockerenv"):
        for host in ["host.docker.internal", "172.17.0.1"]:
            try:
                urllib.request.urlopen(f"http://{host}:11434/api/tags", timeout=1)
                return f"http://{host}:11434"
            except Exception:
                pass
    return DEFAULT_BASE_URL


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"
    default_model = DEFAULT_MODEL
    dimension = 768 #384  # granite-embedding:30m vector dimension

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or _get_default_url()).rstrip("/")
        self.default_model = model or os.getenv("OLLAMA_EMBEDDING_MODEL", DEFAULT_MODEL)

    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResponse:
        url = f"{self.base_url}/api/embed"
        payload = {
            "model": self.default_model,
            "input": list(texts),
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        def _do_request():
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                raise ProviderError(f"Ollama embedding failed: {exc}") from exc

        res_data = await asyncio.to_thread(_do_request)

        embeddings = res_data.get("embeddings", [])
        if not embeddings:
            raise ProviderError(f"Ollama returned empty embeddings for model {self.default_model}")

        return EmbeddingResponse(
            vectors=embeddings,
            model=res_data.get("model", self.default_model),
            provider=self.name,
        )
