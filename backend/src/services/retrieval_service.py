from db.session import get_conn
from ai.providers.embedings.gemini import GeminiEmbeddingProvider

async def search_embeddings(query: str, limit: int = 5):
    query_vec = await GeminiEmbeddingProvider().embed(query)
    print(query_vec)

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
                (query_vec, query_vec, limit),
            )
            return cur.fetchall()   