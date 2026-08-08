from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class ChatJob:
    session_id: str
    user_input: str
    request_id: str
    meta: dict = field(default_factory=dict)


@dataclass
class ChatResult:
    request_id: str
    session_id: str
    response: str
    tool_calls: list[dict] = field(default_factory=list)
    error: str | None = None


ResultCallback = Callable[[ChatResult], Coroutine[Any, Any, None]]


class ChatWorker:
    def __init__(self, queue: asyncio.Queue[ChatJob], orchestrator_factory: Callable[[str], Any],
                 on_result: ResultCallback, rate_limiter: "RateLimiter | None" = None) -> None:
        self._queue = queue
        self._orchestrator_factory = orchestrator_factory
        self._on_result = on_result
        self._rate_limiter = rate_limiter
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            try:
                job: ChatJob = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                if self._rate_limiter:
                    await self._rate_limiter.acquire()
                result = await self._process(job)
            except Exception as exc:
                result = ChatResult(request_id=job.request_id, session_id=job.session_id,
                                    response="", error=str(exc))
            finally:
                self._queue.task_done()
            await self._on_result(result)

    async def _process(self, job: ChatJob) -> ChatResult:
        orchestrator = self._orchestrator_factory(job.session_id)
        turn = await orchestrator.run(job.session_id, job.user_input)
        return ChatResult(request_id=job.request_id, session_id=job.session_id,
                          response=turn.response, tool_calls=turn.tool_calls, error=turn.error)


class RateLimiter:
    """
    Token bucket rate limiter.
    Free Gemini tier: 15 requests/minute → set rate=15, period=60.
    """
    def __init__(self, rate: int = 15, period: float = 60.0) -> None:
        self._tokens = float(rate)
        self._rate = rate
        self._period = period
        self._refill_per_sec = rate / period
        self._lock = asyncio.Lock()
        self._last_refill = asyncio.get_event_loop().time()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_refill
            self._tokens = min(self._rate, self._tokens + elapsed * self._refill_per_sec)
            self._last_refill = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._refill_per_sec
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1


class ChatWorkerPool:
    def __init__(self, orchestrator_factory: Callable[[str], Any], on_result: ResultCallback,
                 concurrency: int = 2, max_queue: int = 256,
                 rate: int = 15, rate_period: float = 60.0) -> None:
        self._queue: asyncio.Queue[ChatJob] = asyncio.Queue(maxsize=max_queue)
        # Single shared rate limiter across all workers — pool-wide limit
        self._rate_limiter = RateLimiter(rate=rate, period=rate_period)
        self._workers = [
            ChatWorker(self._queue, orchestrator_factory, on_result, self._rate_limiter)
            for _ in range(concurrency)
        ]

    async def start(self) -> None:
        for w in self._workers:
            await w.start()

    async def stop(self) -> None:
        for w in self._workers:
            await w.stop()

    async def submit(self, job: ChatJob) -> None:
        await self._queue.put(job)

    def submit_nowait(self, job: ChatJob) -> None:
        self._queue.put_nowait(job)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()
