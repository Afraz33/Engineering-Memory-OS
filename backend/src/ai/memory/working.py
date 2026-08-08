"""
Working memory — per-session, in-process message store.

Holds the conversation history for an active session so the model
always receives the full context of what has been said. No database
needed; everything lives in RAM and is discarded when the session ends.

Later this will be swapped/backed by a persistent store (Redis / Postgres)
without changing the interface.
"""

from copy import replace
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional


@dataclass
class Message:
    """A single conversation turn."""
    role: str       # "system" | "user" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, str]:
        """Format for LLM provider message lists."""
        return {"role": self.role, "content": self.content}


class WorkingMemory:
    """
    In-memory conversation store for a single session.
    
    Usage
    -----
        memory = WorkingMemory(system_prompt="You are helpful.")
        memory.add_user("Hello!")
        memory.add_assistant("Hi there!")
        messages = memory.get_messages()  # ready to pass to provider
    """
    
    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_messages: int = 100,
    ):
        """
        Args:
            system_prompt: Optional system message prepended to every context window
            max_messages: Max non-system messages to keep in memory.
                            Oldest messages are pruned once this limit is hit.
        """
        self._system_prompt = system_prompt
        self._max_messages = max_messages
        self._messages: List[Message] = []
        self._created_at = datetime.now(timezone.utc)
    
    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------
    
    def add_user(self, content: str) -> None:
        """Append a user turn."""
        self._messages.append(Message(role="user", content=content))
        self._prune()
    
    def add_assistant(self, content: str) -> None:
        """Append an assistant turn."""
        self._messages.append(Message(role="assistant", content=content))
        self._prune()
    
    def add_system(self, content: str) -> None:
        """
        Append an in-conversation system message.
        
        Unlike the constructor system_prompt, this is injected at a specific
        point in the conversation (e.g. tool results, injected context).
        """
        self._messages.append(Message(role="system", content=content))
        self._prune()
    
    def set_system_prompt(self, content: str) -> None:
        """Replace the session's leading system prompt."""
        self._system_prompt = content
    
    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    
    def get_messages(self) -> List[Dict[str, str]]:
        """
        Return the full context window ready to pass to a provider.
        
        The leading system prompt (if any) is always first.
        """
        messages = []
        
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        
        messages.extend(msg.to_dict() for msg in self._messages)
        
        return messages
    
    def get_history(self) -> List[Message]:
        return [replace(msg) for msg in self._messages]
    
    def last_n(self, n: int) -> List[Dict[str, str]]:
        """
        Return the last n messages (plus the system prompt).
        Useful for token-budget-limited summarisation.
        """
        messages = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(msg.to_dict() for msg in self._messages[-n:])
        return messages
    
    # ------------------------------------------------------------------
    # Metadata / housekeeping
    # ------------------------------------------------------------------
    
    def clear(self) -> None:
        """Wipe conversation history (keeps system prompt)."""
        self._messages.clear()
    
    @property
    def message_count(self) -> int:
        """Number of non-system messages stored."""
        return len(self._messages)
    
    @property
    def created_at(self) -> datetime:
        return self._created_at
    
    # TODO: later implement _prune_by_tokens() instead of _prune()
    # def _prune(self) -> None:
    #     """Drop oldest messages when we exceed max_messages."""
    #     while len(self._messages) > self._max_messages:
    #         self._messages = self._messages[2:]
        
    def _prune(self) -> None:
        """Drop oldest messages when we exceed max_messages."""
        while len(self._messages) > self._max_messages:
            if len(self._messages) >= 2:
                self._messages = self._messages[2:]
            else:
                self._messages.pop(0)

    def __repr__(self) -> str:
        return (
            f"WorkingMemory("
            f"messages={self.message_count}, "
            f"max={self._max_messages}, "
            f"has_system={self._system_prompt is not None})"
        )
