"""The extraction stage: does this event carry a durable memory, and of what type?

One LLM call decides both. It answers in JSON over the plain text interface in
`app.llm` rather than through a provider-native structured-output mode, so
switching `LLM_PROVIDER` does not change this file — the same reason the
`ChatProvider` boundary exists at all.

The model is asked to *reject* aggressively. Precision is the whole bet
(Scope §13): a store full of paraphrased chatter is worse than a thin one.
"""

import json
import os
import re
from dataclasses import dataclass

from app.ingest.events import Event
from app.llm import ChatMessage, ChatProvider, ProviderError
from app.memory import MEMORY_TYPES, MemoryType

# Below this, a record lands `quarantined` instead of `active` — retrievable
# only on explicit request (Scope §6.2).
CONFIDENCE_THRESHOLD = float(os.getenv("CAPTURE_CONFIDENCE_THRESHOLD", "0.6"))

SYSTEM_PROMPT = """\
You extract durable engineering knowledge from team activity (Slack threads, \
GitHub pull requests, Jira issues) for a shared memory store used by engineers \
and their coding agents.

For each event you decide two things: whether it is worth storing at all, and \
if so, which single category it belongs to.

Categories:
- identity: who a person or team is — role, preferences, working style. \
  "Afraz prefers explicit error handling over exceptions."
- project: what a system is — architecture, constraints, goals, ownership. \
  "Billing service is Go, talks to Stripe, owned by the payments team."
- convention: how this team does things; a rule that applies repeatedly. \
  "All migrations are reviewed by a DBA before merge."
- decision: a specific choice that was made, with its rationale or alternatives. \
  "Moved off MongoDB to CockroachDB for multi-region writes."
- reference: a pointer to an external artifact worth finding again. \
  "Prod runbook lives at <url>."
- session: ephemeral working state, useful for hours or days. \
  "Currently debugging the retry loop in worker.py."

Store ONLY if the event states a fact that stays useful after the conversation \
ends, and that a teammate or agent would want surfaced weeks later.

Do NOT store:
- questions, speculation, or proposals nobody has agreed to ("should we maybe...")
- status chatter, standups, greetings, scheduling, jokes
- transient facts with no lasting consequence ("deploy is running")
- restatements of something obvious from the code itself
- anything where you cannot write a specific, self-contained claim

Rules for the fields:
- title: one sentence stating the claim, standing alone without the source text. \
  No "the team discussed..." framing — state the fact itself.
- body: the rationale, alternatives, and constraints. Only what the event \
  actually supports. Never invent reasoning that is not present.
- entities: lowercase systems, tools, services, or people named. 0-8 items.
- confidence: 0.0-1.0, how certain you are that this is a real, correctly typed, \
  durable fact. Ambiguous or one-sided discussion belongs below 0.5.

Respond with ONLY a JSON object, no markdown fence and no commentary:
{"store": true, "type": "decision", "title": "...", "body": "...", \
"entities": ["..."], "confidence": 0.0, "reason": "..."}

When store is false, set type to null and title/body to empty strings, and put \
the rejection rationale in reason (one short sentence)."""

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(slots=True)
class Classification:
    store: bool
    type: MemoryType | None
    title: str
    body: str
    entities: list[str]
    confidence: float
    reason: str


class ClassificationError(RuntimeError):
    """The model's answer could not be read as a classification."""


def _build_prompt(event: Event) -> str:
    return (
        f"Source: {event.source}\n"
        f"Location: {event.context}\n"
        f"Author: {event.author}\n"
        f"Timestamp: {event.occurred_at.isoformat()}\n"
        f"Scope: {event.scope}\n"
        f"---\n"
        f"{event.text}"
    )


def _extract_json(raw: str) -> dict:
    text = _FENCE.sub("", raw).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Models sometimes prepend a sentence despite the instruction; salvage the
    # object rather than discarding an otherwise good extraction.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ClassificationError(f"no JSON object in model reply: {raw[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ClassificationError(f"unparseable model reply: {raw[:200]!r}") from exc


def _coerce(data: dict) -> Classification:
    store = bool(data.get("store", False))
    reason = str(data.get("reason") or "").strip()

    if not store:
        return Classification(False, None, "", "", [], 0.0, reason or "not durable")

    mem_type = data.get("type")
    if mem_type not in MEMORY_TYPES:
        raise ClassificationError(f"unknown memory type {mem_type!r}")

    title = str(data.get("title") or "").strip()
    if not title:
        raise ClassificationError("store=true with an empty title")

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    entities = [
        str(e).strip().lower()
        for e in (data.get("entities") or [])
        if str(e).strip()
    ]

    return Classification(
        store=True,
        type=mem_type,
        title=title,
        body=str(data.get("body") or "").strip(),
        entities=entities[:8],
        confidence=min(max(confidence, 0.0), 1.0),
        reason=reason,
    )


async def classify(event: Event, provider: ChatProvider) -> Classification:
    """Ask the model whether this event is worth remembering, and as what."""
    try:
        response = await provider.chat(
            [ChatMessage(role="user", content=_build_prompt(event))],
            system=SYSTEM_PROMPT,
        )
    except ProviderError as exc:
        raise ClassificationError(f"classifier call failed: {exc}") from exc

    return _coerce(_extract_json(response.content))
