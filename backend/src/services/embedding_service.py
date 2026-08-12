from db.session import get_conn
from ai.providers.embedings import get_embedding_provider

async def store_memory(text: str):
    provider = get_embedding_provider()

    # 1. Generate embedding
    res = await provider.embed([text])
    vector = res.vectors[0]

    vector_str = f"[{','.join(str(x) for x in vector)}]"

    # 2. Memory + embedding in ONE DB transaction
    with get_conn() as conn:
        with conn.cursor() as cur:

            # Insert memory first
            cur.execute(
                """
                INSERT INTO memories (id, content)
                VALUES (gen_random_uuid(), %s)
                RETURNING id
                """,
                (text,),
            )

            memory_id = cur.fetchone()[0]

            # Insert embedding using the newly-created ID
            cur.execute(
                """
                INSERT INTO embeddings
                    (id, memory_id, vector, model)
                VALUES
                    (gen_random_uuid(), %s, %s, %s)
                """,
                (memory_id, vector_str, res.model),
            )

        # exiting the connection context commits
        # an exception rolls it back

    return memory_id