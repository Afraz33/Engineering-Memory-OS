from typing import Sequence
from google import genai

from .base import EmbeddingProvider, EmbeddingResponse, ProviderError


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"
    default_model = "text-embedding-004"
    dimension = 768  # Gemini embedding size

    def __init__(self, api_key: str):
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            raise ProviderError(f"Failed to init Gemini client: {e}")

    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResponse:
        try:
            result = self.client.models.embed_content(
                model=self.default_model,
                contents=list(texts),
            )

            vectors = [e.values for e in result.embeddings]

            return EmbeddingResponse(
                vectors=vectors,
                model=self.default_model,
                provider=self.name,
            )

        except Exception as e:
            raise ProviderError(f"Gemini embedding failed: {e}")