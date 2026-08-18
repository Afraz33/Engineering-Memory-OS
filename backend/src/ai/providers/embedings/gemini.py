import math
from typing import Sequence
from google import genai
from google.genai import types

from .base import EmbeddingProvider, EmbeddingResponse, ProviderError


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"
    # text-embedding-004 was retired and now 404s. Its replacement returns 3072
    # dimensions natively; we ask for 768 to match the VECTOR(768) column and
    # the vector index built on it. Changing this number means rebuilding both.
    default_model = "gemini-embedding-001"
    dimension = 768

    def __init__(self, api_key: str):
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            raise ProviderError(f"Failed to init Gemini client: {e}")

    async def embed(
        self,
        texts: Sequence[str],
        task_type: str | None = None,
    ) -> EmbeddingResponse:
        """`task_type` makes the embedding asymmetric.

        gemini-embedding-001 projects a stored document and the question someone
        asks about it into different places unless told which is which:
        RETRIEVAL_DOCUMENT for what we index, RETRIEVAL_QUERY for what we search
        with. Both sides must agree -- embedding a query as a document is not an
        error, it just quietly retrieves worse. Left None the model applies its
        default, which is what the pre-search callers relied on.
        """
        try:
            result = self.client.models.embed_content(
                model=self.default_model,
                contents=list(texts),
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimension,
                ),
            )

            vectors = [_normalize(e.values) for e in result.embeddings]

            return EmbeddingResponse(
                vectors=vectors,
                model=self.default_model,
                provider=self.name,
            )

        except Exception as e:
            raise ProviderError(f"Gemini embedding failed: {e}")


def _normalize(vector: Sequence[float]) -> list[float]:
    """Scale to unit length.

    gemini-embedding-001 only returns normalized vectors at its native 3072
    dimensions; truncating to 768 leaves them around norm 0.59, and Google's
    guidance is to renormalize yourself. Cosine distance ignores magnitude so
    ranking is unaffected either way, but an un-normalized vector silently
    breaks anyone who later reaches for L2 or an inner product.
    """
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return list(vector)
    return [x / norm for x in vector]