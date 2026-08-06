"""
Chat routes — the user-facing API for conversations.

POST /api/chat          — Send a message and get a response
GET  /api/sessions      — List all active sessions
GET  /api/sessions/{id} — Get session metadata
POST /api/sessions      — Create a new session
DELETE /api/sessions/{id} — End a session
GET  /api/sessions/{id}/history — Get conversation history
"""

from app.dependencies import get_orchestrator
from ai.orchestrator import AIOrchestrator
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., min_length=1, description="User's message")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    session_id: str
    message: str
    response: str


class SessionCreateRequest(BaseModel):
    """Request body for creating a new session."""
    session_id: str
    system_prompt: Optional[str] = None


class SessionInfo(BaseModel):
    """Session metadata."""
    session_id: str
    message_count: int
    created_at: str
    has_system_prompt: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
):
    """
    Send a message and receive a response.
    
    The session is automatically created if it doesn't exist.
    Full conversation history is maintained in memory for context.
    """
    try:
        response = await orchestrator.chat(
            session_id=request.session_id,
            message=request.message,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        return ChatResponse(
            session_id=request.session_id,
            message=request.message,
            response=response,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=list[str])
async def list_sessions(
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
):
    """List all active session IDs."""
    return orchestrator.active_sessions


@router.post("/sessions", status_code=201)
async def create_session(
    request: SessionCreateRequest,
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
):
    """
    Explicitly create a new session with an optional system prompt override.
    
    Not required — sessions auto-create on first message.
    """
    orchestrator.create_session(
        session_id=request.session_id,
        system_prompt=request.system_prompt,
    )
    return {"session_id": request.session_id, "status": "created"}


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
):
    """Get metadata about a session."""
    info = orchestrator.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return info


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
):
    """End a session and delete its history."""
    deleted = orchestrator.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "status": "deleted"}


@router.get("/sessions/{session_id}/history")
async def get_history(
    session_id: str,
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
):
    """Retrieve the full conversation history for a session."""
    try:
        history = orchestrator.get_session_history(session_id)
        return {"session_id": session_id, "messages": history}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/clear")
async def clear_session(
    session_id: str,
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
):
    """Clear the conversation history but keep the session alive."""
    orchestrator.clear_session(session_id)
    return {"session_id": session_id, "status": "cleared"}
