"""
Memory manager — holds multiple sessions, each with its own working memory.

A session = one conversation thread. The manager maps session_id → WorkingMemory.
"""

from typing import Dict, Optional
from .working import WorkingMemory


class MemoryManager:
    """
    Manages multiple concurrent conversation sessions.
    
    Each session gets its own isolated WorkingMemory instance.
    
    Example
    -------
        manager = MemoryManager(system_prompt="You are helpful.")
        
        # User A session
        manager.add_user_message("session-a", "Hello!")
        manager.add_assistant_message("session-a", "Hi there!")
        
        # User B session (isolated from A)
        manager.add_user_message("session-b", "What's the weather?")
        
        # Retrieve context for each session
        messages_a = manager.get_messages("session-a")
        messages_b = manager.get_messages("session-b")
    """
    
    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_messages_per_session: int = 100,
    ):
        """
        Args:
            system_prompt: Default system prompt for all new sessions
            max_messages_per_session: Memory limit per session
        """
        self._system_prompt = system_prompt
        self._max_messages = max_messages_per_session
        self._sessions: Dict[str, WorkingMemory] = {}
    
    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    
    def create_session(
        self,
        session_id: str,
        system_prompt: Optional[str] = None,
    ) -> WorkingMemory:
        """
        Explicitly create a new session.
        
        Args:
            session_id: Unique identifier for the session
            system_prompt: Optional override for this session's system prompt
            
        Returns:
            The newly created WorkingMemory instance
        """
        prompt = system_prompt if system_prompt is not None else self._system_prompt
        
        memory = WorkingMemory(
            system_prompt=prompt,
            max_messages=self._max_messages,
        )
        self._sessions[session_id] = memory
        return memory
    
    def get_or_create_session(self, session_id: str) -> WorkingMemory:
        """
        Lazy session creation — get existing or create if doesn't exist.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            The WorkingMemory instance for this session
        """
        if session_id not in self._sessions:
            return self.create_session(session_id)
        return self._sessions[session_id]
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its history.
        
        Args:
            session_id: Session to delete
            
        Returns:
            True if session existed and was deleted, False otherwise
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def session_exists(self, session_id: str) -> bool:
        """Check if a session is active."""
        return session_id in self._sessions
    
    # ------------------------------------------------------------------
    # Message operations
    # ------------------------------------------------------------------
    
    def add_user_message(self, session_id: str, content: str) -> None:
        """Add a user message to the session (auto-creates session if needed)."""
        memory = self.get_or_create_session(session_id)
        memory.add_user(content)
    
    def add_assistant_message(self, session_id: str, content: str) -> None:
        """Add an assistant message to the session."""
        memory = self.get_or_create_session(session_id)
        memory.add_assistant(content)
    
    def add_system_message(self, session_id: str, content: str) -> None:
        """Add a system message to the session."""
        memory = self.get_or_create_session(session_id)
        memory.add_system(content)
    
    def get_messages(self, session_id: str) -> list[dict]:
        """
        Get the full context window for a session (ready to pass to provider).
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dicts: [{"role": "...", "content": "..."}, ...]
            
        Raises:
            KeyError: If session doesn't exist
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session '{session_id}' does not exist.")
        return self._sessions[session_id].get_messages()
    
    def clear_session(self, session_id: str) -> None:
        """Clear all messages from a session (keeps system prompt and session alive)."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()
    
    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    
    @property
    def active_sessions(self) -> list[str]:
        """List of active session IDs."""
        return list(self._sessions.keys())
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        Get metadata about a session.
        
        Returns None if session doesn't exist.
        """
        if session_id not in self._sessions:
            return None
        
        memory = self._sessions[session_id]
        return {
            "session_id": session_id,
            "message_count": memory.message_count,
            "created_at": memory.created_at.isoformat(),
            "has_system_prompt": memory._system_prompt is not None,
        }
    
    def __repr__(self) -> str:
        return (
            f"MemoryManager("
            f"sessions={len(self._sessions)}, "
            f"has_default_prompt={self._system_prompt is not None})"
        )
