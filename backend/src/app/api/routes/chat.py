from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_chat_service
from workers.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int | None = None


class ChatResponse(BaseModel):
    session_id: str
    request_id: str
    message: str
    response: str
    error: str | None = None


class SessionCreateRequest(BaseModel):
    session_id: str
    system_prompt: str | None = None
    namespace: str | None = None


class SessionInfo(BaseModel):
    session_id: str
    history_length: int
    namespace: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    result = await service.chat(session_id=request.session_id, user_input=request.message)
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)
    return ChatResponse(
        session_id=result.session_id,
        request_id=result.request_id,
        message=request.message,
        response=result.response,
    )


@router.get("/sessions", response_model=list[str])
async def list_sessions(service: ChatService = Depends(get_chat_service)):
    return service.list_sessions()


@router.post("/sessions", status_code=201)
async def create_session(request: SessionCreateRequest, service: ChatService = Depends(get_chat_service)):
    service.create_session(
        session_id=request.session_id,
        system_prompt=request.system_prompt,
        namespace=request.namespace,
    )
    return {"session_id": request.session_id, "status": "created"}


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str, service: ChatService = Depends(get_chat_service)):
    info = service.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return info


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, service: ChatService = Depends(get_chat_service)):
    if not service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "status": "deleted"}


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str, service: ChatService = Depends(get_chat_service)):
    try:
        history = service.get_history(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": history}


@router.post("/sessions/{session_id}/clear")
async def clear_session(session_id: str, service: ChatService = Depends(get_chat_service)):
    if not service.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    service.clear_history(session_id)
    return {"session_id": session_id, "status": "cleared"}
