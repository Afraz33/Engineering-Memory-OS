import asyncio

from ai.providers.embedings import get_embedding_provider
from db.session import get_conn


async def search_embeddings(query: str, limit: int = 5):
    provider = get_embedding_provider()

    # embed() expects a batch, even for a single query.
    res = await provider.embed([query])
    query_vec = res.vectors[0]

    return await asyncio.to_thread(
        _search,
        query_vec,
        limit,
    )


def _to_vector_literal(vector: list[float]) -> str:
    """Convert a Python vector to PostgreSQL VECTOR literal syntax."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def _search(query_vec: list[float], limit: int):
    query_vec_str = _to_vector_literal(query_vec)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                m.*,
                e.vector <-> %s::VECTOR AS score
            FROM embeddings e
            JOIN memories m ON m.id = e.memory_id
            ORDER BY e.vector <-> %s::VECTOR
            LIMIT %s;
            """,
            (query_vec_str, query_vec_str, limit),
        )

        return cur.fetchall()