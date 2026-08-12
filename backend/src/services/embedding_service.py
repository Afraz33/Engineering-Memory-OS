"""Write the vector for a stored memory.

Called by `PostgresMemoryStore.add` right after the row commits, so semantic
search sees a memory within one request of it being captured.
"""

import asyncio
import os
from functools import lru_cache

from ai.providers.embedings.gemini import GeminiEmbeddingProvider
from db.session import get_conn


@lru_cache(maxsize=1)
def _provider() -> GeminiEmbeddingProvider:
    # Constructing the genai client per call re-does TLS setup and key parsing
    # on every captured message.
    return GeminiEmbeddingProvider(api_key=os.getenv("GOOGLE_API_KEY", ""))


def _to_vector_literal(vector: list[float]) -> str:
    """`VECTOR` columns take the `[1,2,3]` literal form. Handing psycopg a
    Python list instead produces a Postgres array, which will not cast."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


async def add_embedding(memory_id: str, text: str) -> None:
    # `embed` is a batch API — passing a bare string would iterate it into one
    # embedding per character.
    res = await _provider().embed([text])
    vector = res.vectors[0]

    await asyncio.to_thread(_insert, memory_id, vector, res.model)


def _insert(memory_id: str, vector: list[float], model: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO embeddings (id, memory_id, vector, model)
            VALUES (gen_random_uuid(), %s, %s::VECTOR, %s);
            """,
            (memory_id, _to_vector_literal(vector), model),
        )
