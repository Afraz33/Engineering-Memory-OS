"""Typed memory records — the shape everything else agrees on.

Mirrors Scope §5.2. Defined independently of how it is persisted, because the
record shape is what has to survive the move to CockroachDB + pgvector; the
store behind it (see `store.py`) is expected to be thrown away.

`embedding` is deliberately absent: there is no vector substrate yet, and a
field nothing can populate is worse than no field.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, get_args

# The six categories from Scope §5.1. Retrieval weighting, decay rates, and
# write permissions all key off this, so it is a closed set, not a free string.
MemoryType = Literal[
    "identity",
    "project",
    "convention",
    "decision",
    "reference",
    "session",
]

MEMORY_TYPES: tuple[str, ...] = get_args(MemoryType)

MemoryStatus = Literal["active", "superseded", "reverted", "quarantined"]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Provenance:
    """Where a claim came from.

    Mandatory on every record (Scope §6): a memory nobody can trace back to a
    thread or PR is exactly the unauditable landfill automatic capture is
    supposed to avoid.
    """

    source: str
    author: str
    ts: datetime
    excerpt: str
    url: str | None = None


@dataclass(slots=True)
class Memory:
    workspace_id: str
    type: MemoryType
    title: str
    body: str
    provenance: list[Provenance]
    scope: str = "workspace"
    status: MemoryStatus = "active"
    confidence: float = 0.0
    entities: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    valid_from: datetime = field(default_factory=_now)
    valid_until: datetime | None = None
    created_at: datetime = field(default_factory=_now)
    last_accessed_at: datetime | None = None
    access_count: int = 0

    def __post_init__(self) -> None:
        if not self.provenance:
            raise ValueError("a memory without provenance cannot be written")
