import os
from dataclasses import dataclass

from ai.ingest.events.events import Event
from ai.providers.llm import ChatMessage, ChatProvider, ProviderError
from ai.memory import MEMORY_TYPES, MemoryType

# Below this, a record lands `quarantined` instead of `active` — retrievable
# only on explicit request (Scope §6.2).
CONFIDENCE_THRESHOLD = float(os.getenv("CAPTURE_CONFIDENCE_THRESHOLD", "0.6"))

SYSTEM_PROMPT = """
You extract a single, durable engineering decision from input text.

This is a high-precision task. If the input does not clearly contain a finalized decision, reject it.

A valid decision must include:

- a clear choice that was made
- context or problem it solves
- optional reasoning or tradeoffs

Rules:

- Reject if the text is a question, proposal, or speculation.
- Reject if multiple conflicting options are still being discussed.
- Do not infer decisions that are not explicitly stated.
- Be strict: false positives are worse than missing data.

Output must be JSON only:

{
  "store": true/false,
  "title": "one sentence stating the decision",
  "body": "context, reasoning, and constraints (only if present)",
  "confidence": 0.0-1.0,
  "reason": "why stored or why rejected"
}

Guidelines:

- title must stand alone as a fact
- body must not invent information
- confidence reflects certainty that this is a real, durable decision
- use lower confidence if based on partial or one-sided input

If rejected:

- set store=false
- leave title and body empty
- provide a short reason
"""


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

class DecisionError(RuntimeError): 
    """The model could not make a decision."""

async def handle_decisions(event: Event, provider: ChatProvider) -> str:
    """Ask the model to make a decision and return it."""
    try:
        response = await provider.chat(
            [ChatMessage(role="user", content=_build_prompt(event))],
            system=SYSTEM_PROMPT,
        )
    except ProviderError as exc:
        raise DecisionError(f"Decision call failed: {exc}") from exc

    return response.content
