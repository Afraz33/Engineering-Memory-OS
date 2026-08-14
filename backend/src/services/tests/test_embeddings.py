import asyncio
import uuid

from db.session import get_conn
from ai.providers.embedings import get_embedding_provider


def to_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def get_workspace_id() -> str:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM workspaces
            LIMIT 1;
            """
        )

        row = cur.fetchone()

        if not row:
            raise RuntimeError(
                "No workspace found. Create a workspace first."
            )

        return str(row["id"])


async def create_memory(
    workspace_id: str,
    title: str,
    body: str,
):
    provider = get_embedding_provider()

    print(f"  Generating embedding for: {title}")

    # Generate embedding
    res = await provider.embed([body])
    vector = res.vectors[0]

    memory_id = str(uuid.uuid4())

    # --------------------------------------------------
    # Insert memory
    # --------------------------------------------------

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memories (
                id,
                workspace_id,
                type,
                title,
                body,
                scope,
                status,
                confidence
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            );
            """,
            (
                memory_id,
                workspace_id,
                "semantic",
                title,
                body,
                "workspace",
                "active",
                1.0,
            ),
        )

    # --------------------------------------------------
    # Insert embedding
    # --------------------------------------------------

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO embeddings (
                id,
                memory_id,
                vector,
                model
            )
            VALUES (
                gen_random_uuid(),
                %s,
                %s::VECTOR,
                %s
            );
            """,
            (
                memory_id,
                to_vector_literal(vector),
                res.model,
            ),
        )

    return memory_id


async def search_embeddings(
    query: str,
    limit: int = 5,
):
    provider = get_embedding_provider()

    print(f"\nGenerating query embedding...")

    # Generate query embedding
    res = await provider.embed([query])

    query_vector = res.vectors[0]
    query_vector_str = to_vector_literal(query_vector)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                m.id,
                m.title,
                m.body,
                m.type,
                m.scope,
                m.status,
                e.vector <-> %s::VECTOR AS score
            FROM embeddings e
            JOIN memories m
                ON m.id = e.memory_id
            ORDER BY e.vector <-> %s::VECTOR
            LIMIT %s;
            """,
            (
                query_vector_str,
                query_vector_str,
                limit,
            ),
        )

        return cur.fetchall()


async def main():
    # ==================================================
    # 1. GET EXISTING WORKSPACE
    # ==================================================

    workspace_id = get_workspace_id()

    print("=" * 70)
    print("EMBEDDING TEST")
    print("=" * 70)

    print(f"\nWorkspace: {workspace_id}")

    # ==================================================
    # 2. CREATE TEST MEMORIES
    # ==================================================

    memories = [
        (
            "Slack Integration",
            "We decided to use Slack for collecting engineering conversations and technical discussions.",
        ),
        (
            "Database Architecture",
            "CockroachDB will store structured engineering data and vector embeddings for semantic memory search.",
        ),
        (
            "Memory Retrieval",
            "The memory system will use semantic vector search to retrieve relevant context for the AI model.",
        ),
        (
            "GitHub Integration",
            "GitHub will provide technical facts such as commits, pull requests, branches, and code changes.",
        ),
        (
            "Jira Integration",
            "Jira will provide structured project information including issues, tasks, priorities, and status.",
        ),
    ]

    print("\n" + "=" * 70)
    print("CREATING MEMORIES")
    print("=" * 70)

    for title, body in memories:
        try:
            memory_id = await create_memory(
                workspace_id=workspace_id,
                title=title,
                body=body,
            )

            print(f"  Created: {memory_id}")
            print(f"  Title:   {title}")

        except Exception as e:
            print(f"\n  FAILED: {title}")
            print(f"  {type(e).__name__}: {e}")

    # ==================================================
    # 3. SEARCH
    # ==================================================

    query = (
        "How does the system retrieve relevant engineering "
        "information from memory?"
    )

    print("\n" + "=" * 70)
    print("SEMANTIC SEARCH")
    print("=" * 70)

    print(f"\nQuery: {query}")

    try:
        results = await search_embeddings(
            query=query,
            limit=5,
        )

    except Exception as e:
        print(f"\nSearch failed:")
        print(f"{type(e).__name__}: {e}")
        return

    # ==================================================
    # 4. PRINT RESULTS
    # ==================================================

    if not results:
        print("\nNo results found.")
        return

    print(f"\nFound {len(results)} results:")

    for i, row in enumerate(results, 1):
        print("\n" + "-" * 70)
        print(f"RESULT {i}")
        print("-" * 70)

        print(f"ID:     {row['id']}")
        print(f"Title:  {row['title']}")
        print(f"Body:   {row['body']}")
        print(f"Type:   {row['type']}")
        print(f"Scope:  {row['scope']}")
        print(f"Status: {row['status']}")
        print(f"Score:  {row['score']}")


if __name__ == "__main__":
    asyncio.run(main())