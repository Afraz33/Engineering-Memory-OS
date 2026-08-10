from db.session import get_conn
from ai.providers.embedings.gemini import GeminiEmbeddingProvider

async def add_embedding(memory_id: str, text: str):
    res = await GeminiEmbeddingProvider().embed(text)
    vector = res.vectors[0]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO embeddings (id, memory_id, vector, model)
                VALUES (gen_random_uuid(), %s, %s, %s)
                """,
                (memory_id, vector, res.model),
            )