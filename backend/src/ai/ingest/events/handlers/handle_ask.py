import os
from dataclasses import dataclass

from ai.ingest.events.events import Event
from ai.providers.llm import ChatMessage, ChatProvider, ProviderError
from ai.memory import MEMORY_TYPES, MemoryType

# Below this, a record lands `quarantined` instead of `active` — retrievable
# only on explicit request (Scope §6.2).
CONFIDENCE_THRESHOLD = float(os.getenv("CAPTURE_CONFIDENCE_THRESHOLD", "0.6"))

SYSTEM_PROMPT = """
You are an engineering knowledge assistant. You answer questions using a shared memory store built from Jira issues, GitHub pull requests, and selected Slack decisions.

Your job is to produce precise, technically correct answers grounded in available context.

Rules:

- Prefer high-confidence sources (Jira, then GitHub, then Slack).
- Do not invent facts. If the answer is not supported, say so clearly.
- Do not speculate or guess missing details.
- Resolve conflicts by preferring the most recent or highest-confidence information.
- Use concise, direct language. No filler.

When answering:

- Start with a direct answer.
- Then provide supporting facts if needed.
- Reference systems, services, or components explicitly.
- If context is insufficient, say: "Insufficient information in memory."

Avoid:

- conversational tone
- generic explanations
- repeating the question
- fabricating rationale not present in context
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

class AnswerError(RuntimeError): 
    """The model could not answer the question."""

async def handle_ask(event: Event, provider: ChatProvider) -> str:
    """Ask the model the question and return the answer."""
    try:
        response = await provider.chat(
            [ChatMessage(role="user", content=_build_prompt(event))],
            system=SYSTEM_PROMPT,
        )
    except ProviderError as exc:
        raise AnswerError(f"Answer call failed: {exc}") from exc

    return response.content
