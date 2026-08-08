from __future__ import annotations

import asyncio
import uuid

from ai.memory.manager import MemoryManager
from ai.orchestrator import Orchestrator
from ai.providers.registry import get_registry
from app.db.session import SessionLocal
from workers.chat_worker import ChatJob, ChatResult, ChatWorkerPool


class ChatService:
    def __init__(self, system_prompt: str = "", concurrency: int = 2, max_queue: int = 256) -> None:
        self._system_prompt = system_prompt
        self._sessions: dict[str, MemoryManager] = {}
        self._pending: dict[str, asyncio.Future[ChatResult]] = {}
        self._pool = ChatWorkerPool(
            orchestrator_factory=self._make_orchestrator,
            on_result=self._resolve_result,
            concurrency=concurrency,
            max_queue=max_queue,
        )

    async def start(self) -> None:
        await self._pool.start()

    async def stop(self) -> None:
        await self._pool.stop()

    # session management

    def create_session(self, session_id: str, system_prompt: str | None = None,
                       namespace: str | None = None) -> None:
        db = SessionLocal()
        self._sessions[session_id] = MemoryManager(
            session=db,
            system_prompt=system_prompt or self._system_prompt,
            namespace=namespace or session_id,
        )

    def delete_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        return True

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def get_session_info(self, session_id: str) -> dict | None:
        mem = self._sessions.get(session_id)
        if mem is None:
            return None
        return {"session_id": session_id, "history_length": mem.history_length, "namespace": mem.namespace}

    def get_history(self, session_id: str) -> list[dict]:
        mem = self._sessions.get(session_id)
        if mem is None:
            raise KeyError(session_id)
        return mem.build_context()

    def clear_history(self, session_id: str) -> None:
        mem = self._sessions.get(session_id)
        if mem:
            mem.clear_history()

    # chat

    async def chat(self, session_id: str, user_input: str, request_id: str | None = None) -> ChatResult:
        rid = request_id or str(uuid.uuid4())
        future: asyncio.Future[ChatResult] = asyncio.get_event_loop().create_future()
        self._pending[rid] = future
        await self._pool.submit(ChatJob(session_id=session_id, user_input=user_input, request_id=rid))
        try:
            return await future
        finally:
            self._pending.pop(rid, None)

    # internal

    def _get_or_create_session(self, session_id: str) -> MemoryManager:
        if session_id not in self._sessions:
            self.create_session(session_id)
        return self._sessions[session_id]

    def _make_orchestrator(self, session_id: str) -> Orchestrator:
        return Orchestrator(provider=get_registry().get(), memory=self._get_or_create_session(session_id))

    async def _resolve_result(self, result: ChatResult) -> None:
        future = self._pending.get(result.request_id)
        if future and not future.done():
            future.set_result(result)
