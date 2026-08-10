"""Wire shapes shared by the API routers.

Kept separate from the domain dataclasses in `app.memory` so the HTTP contract
can stay stable while the record grows fields (embeddings, ACL, supersession
pointers) that clients have no business seeing.
"""

from datetime import datetime

from pydantic import BaseModel

from ai.memory import Memory


class ProvenanceOut(BaseModel):
    source: str
    author: str
    ts: datetime
    excerpt: str
    url: str | None


class MemoryOut(BaseModel):
    id: str
    workspace_id: str
    type: str
    title: str
    body: str
    scope: str
    status: str
    confidence: float
    entities: list[str]
    provenance: list[ProvenanceOut]
    valid_from: datetime
    created_at: datetime

    @classmethod
    def of(cls, memory: Memory) -> "MemoryOut":
        return cls(
            id=memory.id,
            workspace_id=memory.workspace_id,
            type=memory.type,
            title=memory.title,
            body=memory.body,
            scope=memory.scope,
            status=memory.status,
            confidence=memory.confidence,
            entities=memory.entities,
            provenance=[
                ProvenanceOut(
                    source=p.source,
                    author=p.author,
                    ts=p.ts,
                    excerpt=p.excerpt,
                    url=p.url,
                )
                for p in memory.provenance
            ],
            valid_from=memory.valid_from,
            created_at=memory.created_at,
        )
