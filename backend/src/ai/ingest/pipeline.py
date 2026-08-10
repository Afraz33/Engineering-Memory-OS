"""Capture pipeline: event in, memory (or a documented rejection) out.

Scope §6, minus the stages that need a vector substrate:

    normalize → filter → extract → [dedupe] → [supersession] → persist
                                    ^^^^^^^^^^^^^^^^^^^^^^^^
                    both need embeddings + a real store; not wired yet.

Every path returns an `IngestResult` with a reason. A silent drop is
indistinguishable from a bug, and the audit view (Scope §6.4) needs to be able
to show what was rejected and why.
"""

from dataclasses import dataclass
from typing import Literal

from ai.ingest.classifier import Classification, classify
from ai.ingest.classifier import CONFIDENCE_THRESHOLD
from ai.ingest.events.events import Event
from ai.ingest.filter import prefilter
from ai.providers.llm import ChatProvider
from ai.memory import Memory, MemoryStore, Provenance

Outcome = Literal["stored", "quarantined", "dropped_prefilter", "dropped_classifier"]

# Provenance carries an excerpt, not the whole message: enough to audit the
# claim without the store becoming the transcript archive Scope §3 rules out.
EXCERPT_LIMIT = 500


@dataclass(slots=True)
class IngestResult:
    outcome: Outcome
    reason: str
    memory: Memory | None = None
    classification: Classification | None = None


def _to_memory(
    event: Event,
    classification: Classification,
    workspace_id: str,
) -> Memory:
    excerpt = event.text[:EXCERPT_LIMIT]
    if len(event.text) > EXCERPT_LIMIT:
        excerpt += "…"

    return Memory(
        workspace_id=workspace_id,
        type=classification.type,
        title=classification.title,
        body=classification.body,
        scope=event.scope,
        status="active"
        if classification.confidence >= CONFIDENCE_THRESHOLD
        else "quarantined",
        confidence=classification.confidence,
        entities=classification.entities,
        valid_from=event.occurred_at,
        provenance=[
            Provenance(
                source=event.source,
                author=event.author,
                ts=event.occurred_at,
                excerpt=excerpt,
                url=event.url,
            )
        ],
    )


async def ingest(
    event: Event,
    *,
    workspace_id: str,
    provider: ChatProvider,
    store: MemoryStore,
) -> IngestResult:
    verdict = prefilter(event)
    if not verdict.keep:
        return IngestResult("dropped_prefilter", verdict.reason)

    classification = await classify(event, provider)
    if not classification.store:
        return IngestResult(
            "dropped_classifier",
            classification.reason or "classifier declined to store",
            classification=classification,
        )

    memory = await store.add(_to_memory(event, classification, workspace_id))

    if memory.status == "quarantined":
        return IngestResult(
            "quarantined",
            f"confidence {memory.confidence:.2f} below threshold "
            f"{CONFIDENCE_THRESHOLD:.2f}",
            memory=memory,
            classification=classification,
        )

    return IngestResult(
        "stored",
        classification.reason or f"stored as {memory.type}",
        memory=memory,
        classification=classification,
    )
