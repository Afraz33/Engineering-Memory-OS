"""Dispatch for the `/ask`, `/summarize`, `/decision` message prefixes.

Note this is the *prefix* path — a message that merely starts with "/ask".
Slack's real slash commands arrive form-encoded on `POST /api/slack/commands`
and are dispatched there, because they carry a `response_url` this signature
has nowhere to put.

All three handlers take `(event, provider)` and return the model's text.
"""

from ai.ingest.events.events import Event
from ai.ingest.events.handlers.handle_ask import handle_ask
from ai.ingest.events.handlers.handle_decision import handle_decisions
from ai.ingest.events.handlers.handle_summarize import handle_summarize
from ai.providers.llm import ChatProvider

_HANDLERS = {
    "command_ask": handle_ask,
    "command_summarize": handle_summarize,
    "command_decision": handle_decisions,
}


async def handle_command(event: Event, provider: ChatProvider) -> str | None:
    """Returns the answer text, or None if this event is not a command."""
    handler = _HANDLERS.get(event.event_type or "")
    return await handler(event, provider) if handler else None
