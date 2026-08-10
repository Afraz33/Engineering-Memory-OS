import json
import os
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai.providers.llm import ChatMessage, ChatProvider, ProviderError, get_provider

router = APIRouter(prefix="/api/chat", tags=["chat"])

# The system prompt is server-owned, not client-supplied — a client that could
# set it could overwrite the assistant's rules and persona.
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT") or None


def provider_dependency() -> ChatProvider:
    try:
        return get_provider()
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int


class ChatResponseOut(BaseModel):
    content: str
    model: str
    provider: str
    usage: UsageOut


def _to_domain(request: ChatRequest) -> list[ChatMessage]:
    return [ChatMessage(role=m.role, content=m.content) for m in request.messages]


@router.post("", response_model=ChatResponseOut)
async def chat(
    request: ChatRequest,
    provider: ChatProvider = Depends(provider_dependency),
) -> ChatResponseOut:
    try:
        result = await provider.chat(_to_domain(request), system=SYSTEM_PROMPT)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponseOut(
        content=result.content,
        model=result.model,
        provider=result.provider,
        usage=UsageOut(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        ),
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    provider: ChatProvider = Depends(provider_dependency),
) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        try:
            async for delta in provider.stream(
                _to_domain(request), system=SYSTEM_PROMPT
            ):
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except ProviderError as exc:
            # Headers are already sent, so surface the failure in-band.
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
