"""Event ingestion endpoint.

`POST /api/events` takes one source event and runs it through the capture
pipeline. The response always says what happened and why — callers (and the
audit view in Scope §6.4) need to distinguish "nothing worth storing" from
"the classifier fell over", and the first of those is a perfectly good 200.
"""

from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.api.schemas import MemoryOut
from ai.ingest import ClassificationError, EventIn, ingest, normalize
from ai.providers.llm import ChatProvider, ProviderError, get_provider
from ai.memory import MemoryStore, get_store

router = APIRouter(prefix="/api/events", tags=["events"])


def provider_dependency() -> ChatProvider:
    try:
        return get_provider()
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def store_dependency() -> MemoryStore:
    return get_store()


class IngestResponse(BaseModel):
    outcome: Literal[
        "stored", "quarantined", "dropped_prefilter", "dropped_classifier"
    ]
    stored: bool
    reason: str
    memory: MemoryOut | None = None


@router.post("", response_model=IngestResponse)
async def ingest_event(
    request: EventIn = Body(...),
    provider: ChatProvider = Depends(provider_dependency),
    store: MemoryStore = Depends(store_dependency),
) -> IngestResponse:
    event = normalize(request)

    try:
        result = await ingest(
            event,
            workspace_id=request.workspace_id,
            provider=provider,
            store=store,
        )
    except ClassificationError as exc:
        # The event was well-formed; the extractor was not. 502 so the
        # connector retries rather than recording "nothing to store".
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return IngestResponse(
        outcome=result.outcome,
        stored=result.memory is not None,
        reason=result.reason,
        memory=MemoryOut.of(result.memory) if result.memory else None,
    )
