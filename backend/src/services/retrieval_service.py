from db.session import get_conn
from ai.providers.embedings import get_embedding_provider

async def search_embeddings(query: str, limit: int = 5):
    provider = get_embedding_provider()
    res = await provider.embed([query])
    query_vec = res.vectors[0]
    query_vec_str = f"[{','.join(str(x) for x in query_vec)}]"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.*, e.vector <-> %s AS score
                FROM embeddings e
                JOIN memories m ON m.id = e.memory_id
                ORDER BY e.vector <-> %s
                LIMIT %s;
                """,
                (query_vec_str, query_vec_str, limit),
            )
            return cur.fetchall()   