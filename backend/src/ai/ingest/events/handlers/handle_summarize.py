import os
import os
from dataclasses import dataclass

from ai.ingest.events.events import Event
from ai.providers.llm import ChatMessage, ChatProvider, ProviderError
from ai.memory import MEMORY_TYPES, MemoryType

# Below this, a record lands `quarantined` instead of `active` — retrievable
# only on explicit request (Scope §6.2).
CONFIDENCE_THRESHOLD = float(os.getenv("CAPTURE_CONFIDENCE_THRESHOLD", "0.6"))

SYSTEM_PROMPT = """
You summarize engineering discussions into structured, durable knowledge.

The input may contain noise, repetition, and informal conversation. Your job is to extract only what remains useful after the discussion ends.

Focus on:

- decisions made
- reasoning and tradeoffs
- constraints and assumptions
- outcomes and next steps (if concrete)

Rules:

- Remove all chatter, greetings, and repetition.
- Do not include speculation unless it influenced a final decision.
- Do not invent missing reasoning.
- Keep only technically meaningful content.

Output structure:

Summary:
- short, dense overview (2–4 sentences)

Key Points:
- bullet list of concrete facts

Decisions (if any):
- bullet list of finalized decisions with reasoning

Open Questions (if any):
- only unresolved, technically relevant questions

Use precise engineering language. Avoid narrative style.
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


class SummarizeError(RuntimeError): 
    """The model could not generate a valid summary."""


async def handle_summarize(event: Event, provider: ChatProvider) -> str:
    """Ask the model to summarize this event."""
    try:
        response = await provider.chat(
            [ChatMessage(role="user", content=_build_prompt(event))],
            system=SYSTEM_PROMPT,
        )
    except ProviderError as exc:
        raise SummarizeError(f"Summarize call failed: {exc}") from exc

    return response.content
