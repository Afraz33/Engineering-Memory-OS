"""Retrieval endpoint.

Candidate generation is real now: a cosine nearest-neighbour search over the
`embeddings` vector index, scoped to one workspace by the index's prefix
column. The rest of the differentiated pipeline (Scope §7) is still M3 work:

    intent classify → scope resolve → hybrid candidates → category weighting
    → supersession collapse → temporal decay → ACL filter → rerank → pack

`pipeline_stages` reports per stage what actually ran, so nothing downstream
mistakes this for ranked, supersession-safe output.

Two things degrade rather than fail, because a retrieval endpoint that 500s is
worse than one that answers less well:

  * no `workspace_id` on the request — a vector search cannot run, because the
    tenant equality is what keeps the index in play (see the migration). Falls
    back to lexical.
  * the embedding provider erroring — falls back to lexical and says so.

The response shape is unchanged, so MCP `memory.search`, the web app, and the
VS Code extension keep working against it.
"""

import logging
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.schemas import MemoryOut
from ai.memory import Memory, MemoryStore, MemoryType, get_store

router = APIRouter(prefix="/api/retrieve", tags=["retrieval"])

log = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9][a-z0-9._/-]*")

# The vector index returns nearest neighbours with no idea of our status, scope
# or type filters, so some of what it returns is discarded afterwards. Ask for
# more than we need; without this a workspace whose top hits are all quarantined
# returns an empty page while relevant active memories sit just past the cut.
OVERFETCH = 4
MIN_CANDIDATES = 40

# Every stage the real pipeline will run, and whether it does anything now.
PIPELINE_STAGES: dict[str, str] = {
    "intent_classification": "not_implemented",
    "scope_resolution": "passthrough",
    "candidate_generation": "vector_cosine",
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


def _matches(
    memory: Memory,
    scope: str | None,
    types: list[MemoryType] | None,
    statuses: list[str],
) -> bool:
    """The filters `store.list` would have applied, for rows the vector index
    handed back without knowing about them."""
    if memory.status not in statuses:
        return False
    if scope is not None and memory.scope != scope:
        return False
    if types and memory.type not in set(types):
        return False
    return True


async def _lexical(
    request: RetrieveRequest, store: MemoryStore, statuses: list[str]
) -> list[tuple[Memory, float]]:
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
    return matched


async def _semantic(
    request: RetrieveRequest, store: MemoryStore, statuses: list[str]
) -> list[tuple[Memory, float]]:
    from services.embedding_service import search

    assert request.workspace_id is not None  # guarded by the caller

    hits = await search(
        request.query,
        request.workspace_id,
        max(request.limit * OVERFETCH, MIN_CANDIDATES),
    )
    if not hits:
        return []

    by_id = {m.id: m for m in await store.get_many([mid for mid, _ in hits])}

    # Re-apply the hit order: `get_many` returns rows in whatever order the
    # database produced them, and that order is not the ranking.
    ranked: list[tuple[Memory, float]] = []
    for memory_id, similarity in hits:
        memory = by_id.get(memory_id)
        if memory and _matches(memory, request.scope, request.types, statuses):
            ranked.append((memory, similarity))
    return ranked


@router.post("", response_model=RetrieveResponse)
async def retrieve(
    request: RetrieveRequest,
    store: MemoryStore = Depends(store_dependency),
) -> RetrieveResponse:
    statuses = ["active", "quarantined"] if request.include_quarantined else ["active"]

    stages = dict(PIPELINE_STAGES)
    note: str

    if request.workspace_id is None:
        # The vector index is prefixed by workspace_id, so a search without one
        # cannot use it. Refusing outright would break callers that legitimately
        # want a global lexical sweep, so degrade instead of erroring.
        stages["candidate_generation"] = "lexical_only"
        note = (
            "Lexical fallback: no workspace_id on the request, and semantic "
            "search is scoped to a workspace by the vector index prefix."
        )
        matched = await _lexical(request, store, statuses)
    else:
        try:
            matched = await _semantic(request, store, statuses)
            note = (
                "Semantic retrieval: cosine nearest-neighbour over the "
                "workspace-partitioned vector index. No category weighting, "
                "supersession collapse, decay, ACL filtering, or reranking is "
                "applied."
            )
        except Exception as exc:  # noqa: BLE001 - provider errors are open-ended
            # Embedding the query needs a live provider call. When that is down
            # or unconfigured, answering worse beats not answering.
            log.warning("semantic retrieval failed, falling back to lexical: %s", exc)
            stages["candidate_generation"] = "lexical_fallback"
            note = (
                "Lexical fallback: the embedding provider was unavailable, so "
                "results are token overlap, not semantic similarity."
            )
            matched = await _lexical(request, store, statuses)

    top = matched[: request.limit]

    return RetrieveResponse(
        query=request.query,
        count=len(top),
        results=[
            RetrieveResult(memory=MemoryOut.of(m), score=round(s, 4)) for m, s in top
        ],
        pipeline_stages=stages,
        note=note,
    )
