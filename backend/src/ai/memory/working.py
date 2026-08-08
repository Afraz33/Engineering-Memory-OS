from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict


class ChatTurn(TypedDict):
    role: str
    content: str


class WorkingMemory:
    """Pure variable store for one session. No logic, no persistence."""

    def __init__(self, system_prompt: str = "", max_history: int = 100) -> None:
        self._system_prompt = system_prompt
        self._max_history = max_history
        self._chat_history: list[ChatTurn] = []
        self._snippets: dict[str, str] = {}
        self._created_at = datetime.now(timezone.utc)

    # system prompt

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self._system_prompt = value

    # chat history

    def add_turn(self, role: str, content: str) -> None:
        self._chat_history.append(ChatTurn(role=role, content=content))
        self._prune()

    def remove_last_turn(self) -> ChatTurn | None:
        return self._chat_history.pop() if self._chat_history else None

    def get_history(self) -> list[ChatTurn]:
        return list(self._chat_history)

    def last_n_turns(self, n: int) -> list[ChatTurn]:
        return list(self._chat_history[-n:])

    def clear_history(self) -> None:
        self._chat_history.clear()

    @property
    def history_length(self) -> int:
        return len(self._chat_history)

    # semantic snippets

    def set_snippet(self, key: str, value: str) -> None:
        self._snippets[key] = value

    def get_snippet(self, key: str) -> str | None:
        return self._snippets.get(key)

    def remove_snippet(self, key: str) -> bool:
        return bool(self._snippets.pop(key, None))

    def get_all_snippets(self) -> dict[str, str]:
        return dict(self._snippets)

    def clear_snippets(self) -> None:
        self._snippets.clear()

    @property
    def snippet_count(self) -> int:
        return len(self._snippets)

    # full reset

    def clear_all(self) -> None:
        self._chat_history.clear()
        self._snippets.clear()

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def _prune(self) -> None:
        while len(self._chat_history) > self._max_history:
            self._chat_history = self._chat_history[2:]

    def __repr__(self) -> str:
        return f"WorkingMemory(history={self.history_length}, snippets={self.snippet_count})"
