import os

from tavily import AsyncTavilyClient


def _get_client() -> AsyncTavilyClient:
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is not configured."
        )

    return AsyncTavilyClient(api_key=api_key)


async def web_search(
    query: str,
    limit: int = 5,
):
    """
    Search the web for current or external information.

    Use this when company memory does not contain the required
    information or when current information is required.
    """

    if limit < 1:
        limit = 1

    if limit > 10:
        limit = 10

    client = _get_client()

    response = await client.search(
        query=query,
        max_results=limit,
        search_depth="basic",
    )

    return [
        {
            "title": result.get("title"),
            "url": result.get("url"),
            "content": result.get("content"),
            "score": result.get("score"),
        }
        for result in response.get("results", [])
    ]