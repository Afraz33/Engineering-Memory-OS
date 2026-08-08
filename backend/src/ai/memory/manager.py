from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ai.memory.working import WorkingMemory
from ai.memory.semantic import SemanticMemory


class MemoryManager:
    def __init__(self, session: Session, system_prompt: str = "",
                 namespace: str = "default", max_history: int = 100) -> None:
        self._working = WorkingMemory(system_prompt=system_prompt, max_history=max_history)
        self._semantic = SemanticMemory(session=session, namespace=namespace)

    def build_context(self) -> list[dict]:
        system_parts: list[str] = []
        if self._working.system_prompt:
            system_parts.append(self._working.system_prompt)
        snippets = self._working.get_all_snippets()
        if snippets:
            block = "\n".join(f"- {k}: {v}" for k, v in snippets.items())
            system_parts.append(f"[Long-term memory]\n{block}")
        messages: list[dict] = []
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        for turn in self._working.get_history():
            messages.append({"role": turn["role"], "content": turn["content"]})
        return messages

    def add_user_turn(self, content: str) -> None:
        self._working.add_turn("user", content)

    def add_model_turn(self, content: str) -> None:
        self._working.add_turn("model", content)

    def remove_last_turn(self) -> None:
        self._working.remove_last_turn()

    def clear_history(self) -> None:
        self._working.clear_history()

    def set_system_prompt(self, prompt: str) -> None:
        self._working.system_prompt = prompt

    def get_system_prompt(self) -> str:
        return self._working.system_prompt

    def handle_tool_result(self, tool_name: str, args: dict, result: Any) -> None:
        if tool_name == "memory_set":
            self._semantic.set(args["key"], args["value"])
        elif tool_name == "memory_delete":
            self._semantic.delete(args["key"])
        else:
            self._working.set_snippet(tool_name, str(result))

    def handle_semantic_write(self, key: str, value: str) -> None:
        self._semantic.set(key, value)

    def handle_semantic_read(self, key: str) -> str | None:
        return self._semantic.get(key)

    def handle_semantic_delete(self, key: str) -> bool:
        return self._semantic.delete(key)

    def handle_semantic_list(self) -> list[str]:
        return self._semantic.list_keys()

    def inject_semantic_keys(self, keys: list[str]) -> None:
        self._semantic.inject_into(self._working, keys)

    def inject_all_semantic(self) -> None:
        self._semantic.inject_all_into(self._working)

    def clear_injected(self) -> None:
        self._working.clear_snippets()

    @property
    def namespace(self) -> str:
        return self._semantic.namespace

    @property
    def history_length(self) -> int:
        return self._working.history_length

    @property
    def injected_count(self) -> int:
        return self._working.snippet_count

    def __repr__(self) -> str:
        return f"MemoryManager(namespace={self.namespace!r}, history={self.history_length})"
