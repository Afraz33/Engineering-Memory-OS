"""Retrieval endpoint — the request/response contract only.

This is a placeholder on purpose. The differentiated pipeline (Scope §7) is
M3 work and none of it exists yet:

    intent classify → scope resolve → hybrid candidates → category weighting
    → supersession collapse → temporal decay → ACL filter → rerank → pack

What runs today is a case-insensitive token match over title, body, and
entities, ordered by recency. It is a stub, and `pipeline_stages` in the
response says so per stage — so nothing downstream mistakes this for ranked,
supersession-safe output.

The shape is the part meant to last: MCP `memory.search`, the web app, and the
VS Code extension can all be built against it while the internals are replaced.
"""

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.schemas import MemoryOut
from ai.memory import Memory, MemoryStore, MemoryType, get_store

router = APIRouter(prefix="/api/retrieve", tags=["retrieval"])

_TOKEN = re.compile(r"[a-z0-9][a-z0-9._/-]*")

# Every stage the real pipeline will run, and whether it does anything now.
PIPELINE_STAGES: dict[str, str] = {
    "intent_classification": "not_implemented",
    "scope_resolution": "passthrough",
    "candidate_generation": "lexical_only",
    "category_weighting": "not_implemented",
    "supersession_collapse": "not_implemented",
    "temporal_decay": "not_implemented",
    "acl_filter": "not_implemented",
    "rerank": "not_implemented",
    "budget_packing": "not_implemented",
}


def store_dependency() -> MemoryStore:
    return get_store()


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    workspace_id: str | None = None
    scope: str | None = None
    types: list[MemoryType] | None = None
    limit: int = Field(default=10, ge=1, le=100)
    # Quarantined records are low-confidence extractions. They stay out of
    # results unless asked for by name (Scope §6.2).
    include_quarantined: bool = False


class RetrieveResult(BaseModel):
    memory: MemoryOut
    score: float


class RetrieveResponse(BaseModel):
    query: str
    count: int
    results: list[RetrieveResult]
    pipeline_stages: dict[str, str]
    note: str


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _score(memory: Memory, query_tokens: set[str]) -> float:
    """Fraction of query tokens present anywhere in the record.

    Not a relevance model. It exists so `results` is ordered by something
    rather than nothing, and is the first thing the M3 work deletes.
    """
    if not query_tokens:
        return 0.0
    haystack = _tokens(f"{memory.title} {memory.body} {' '.join(memory.entities)}")
    return len(query_tokens & haystack) / len(query_tokens)


@router.post("", response_model=RetrieveResponse)
async def retrieve(
    request: RetrieveRequest,
    store: MemoryStore = Depends(store_dependency),
) -> RetrieveResponse:
    statuses = ["active", "quarantined"] if request.include_quarantined else ["active"]

    candidates = await store.list(
        workspace_id=request.workspace_id,
        scope=request.scope,
        types=request.types,
        statuses=statuses,
    )

    query_tokens = _tokens(request.query)
    scored = [(m, _score(m, query_tokens)) for m in candidates]
    matched = [(m, s) for m, s in scored if s > 0]
    # `store.list` already returns newest-first, and Python's sort is stable,
    # so equal scores keep recency order.
    matched.sort(key=lambda pair: pair[1], reverse=True)

    top = matched[: request.limit]

    return RetrieveResponse(
        query=request.query,
        count=len(top),
        results=[
            RetrieveResult(memory=MemoryOut.of(m), score=round(s, 4)) for m, s in top
        ],
        pipeline_stages=PIPELINE_STAGES,
        note=(
            "Placeholder retrieval: lexical token overlap, recency-ordered. "
            "No intent classification, category weighting, supersession "
            "collapse, decay, ACL filtering, or reranking is applied."
        ),
    )
