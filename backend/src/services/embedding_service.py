"""Write the vector for a stored memory, and search over the ones already written.

`add_embedding` is called by `PostgresMemoryStore.add` right after the row
commits, so semantic search sees a memory within one request of it being
captured. `search` is the read side, used by /api/retrieve.

The two halves must agree on three things or retrieval silently degrades rather
than failing: the same model, the matching task types (document vs query), and
the cosine operator the index was built for.
"""

import asyncio
import os
from functools import lru_cache

from ai.providers.embedings.gemini import GeminiEmbeddingProvider
from db.session import get_conn

# gemini-embedding-001 embeds documents and queries asymmetrically. Indexing uses
# one, searching the other; swapping them costs recall quietly.
DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
QUERY_TASK = "RETRIEVAL_QUERY"


@lru_cache(maxsize=1)
def _provider() -> GeminiEmbeddingProvider:
    # Constructing the genai client per call re-does TLS setup and key parsing
    # on every captured message.
    return GeminiEmbeddingProvider(api_key=os.getenv("GOOGLE_API_KEY", ""))


def _to_vector_literal(vector: list[float]) -> str:
    """`VECTOR` columns take the `[1,2,3]` literal form. Handing psycopg a
    Python list instead produces a Postgres array, which will not cast."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


async def add_embedding(memory_id: str, workspace_id: str, text: str) -> None:
    # `embed` is a batch API — passing a bare string would iterate it into one
    # embedding per character.
    res = await _provider().embed([text], task_type=DOCUMENT_TASK)
    vector = res.vectors[0]

    await asyncio.to_thread(_insert, memory_id, workspace_id, vector, res.model)


def _insert(
    memory_id: str, workspace_id: str, vector: list[float], model: str
) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO embeddings (id, memory_id, workspace_id, vector, model)
            VALUES (gen_random_uuid(), %s, %s, %s::VECTOR, %s);
            """,
            (memory_id, workspace_id, _to_vector_literal(vector), model),
        )


async def search(
    query: str, workspace_id: str, limit: int
) -> list[tuple[str, float]]:
    """Nearest memories to `query`, as (memory_id, similarity) newest-best-first.

    Returns similarity in 0..1 (1 = identical), not the raw cosine *distance*
    the database orders by, because every caller and the API contract talk about
    scores that go up as relevance goes up.
    """
    res = await _provider().embed([query], task_type=QUERY_TASK)
    return await asyncio.to_thread(
        _search, _to_vector_literal(res.vectors[0]), workspace_id, limit
    )


def _search(
    vector_literal: str, workspace_id: str, limit: int
) -> list[tuple[str, float]]:
    with get_conn() as conn, conn.cursor() as cur:
        # workspace_id first and by equality: it is the vector index's prefix,
        # and it is what keeps this a partition-scoped index search instead of a
        # full scan (migrations/004_add_vector_index.sql has the two plans).
        #
        # The ORDER BY must use the same `<=>` the index was built with. Writing
        # 1 - (a <=> b) here to sort by similarity would drop the index, so the
        # conversion happens in Python after the rows come back.
        cur.execute(
            """
            SELECT memory_id, vector <=> %s::VECTOR AS distance
            FROM embeddings
            WHERE workspace_id = %s
            ORDER BY distance
            LIMIT %s;
            """,
            (vector_literal, workspace_id, limit),
        )
        return [(str(r["memory_id"]), 1.0 - float(r["distance"])) for r in cur.fetchall()]
