from services.retrieval_service import search_embeddings


async def get_company_memory(
    query: str,
    limit: int = 5,
):
    """
    Retrieve company information relevant to the given query.

    Use this tool when you need previously stored information about
    the company, including projects, technical decisions, architecture,
    discussions, integrations, or other engineering knowledge.
    """
    results = await search_embeddings(
        query=query,
        limit=limit,
    )

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "body": row["body"],
            "type": row["type"],
            "scope": row["scope"],
            "status": row["status"],
            "score": row["score"],
        }
        for row in results
    ]

    