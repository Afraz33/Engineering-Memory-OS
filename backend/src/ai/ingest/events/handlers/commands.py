from ai.ingest.events.handlers.handle_ask import handle_ask
from ai.ingest.events.handlers.handle_summarize import handle_summarize
from ai.ingest.events.handlers.handle_decision import handle_decisions

async def handle_command(event, provider, store):
    if event.event_type == "command_ask":
        return await handle_ask(event, provider, store)

    if event.event_type == "command_summarize":
        return await handle_summarize(event, provider, store)

    if event.event_type == "command_decision":
        return await handle_decisions(event, store)

    return None