from typing import Optional
from .providers import get_provider, BaseLLM
from .memory.manager import MemoryManager


class AIOrchestrator:
    def __init__(
        self,
        memory_manager: MemoryManager,
        default_provider: Optional[str] = None,
    ):
        self.memory = memory_manager
        self._default_provider = default_provider
    
    async def chat(
        self,
        session_id: str,
        message: str,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send a message and get a response.
        
        The full conversation history is automatically included in the
        context sent to the LLM.
        
        Args:
            session_id: Unique session identifier
            message: The user's message
            provider: Optional provider override (defaults to active provider)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Max tokens to generate
            
        Returns:
            The assistant's response text
        """
        # 1. Store user message
        self.memory.add_user_message(session_id, message)
        
        # 2. Retrieve full conversation history
        messages = self.memory.get_messages(session_id)
        
        # 3. Get the provider
        provider_name = provider or self._default_provider
        llm: BaseLLM = get_provider(provider_name)
        
        # 4. Generate response
        response = await llm.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # 5. Store assistant response
        self.memory.add_assistant_message(session_id, response)
        
        return response
    
    async def chat_without_history(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        One-off chat — no session, no history tracking.
        
        Useful for stateless operations like embeddings, summarization, etc.
        
        Args:
            message: The user's message
            system_prompt: Optional system message
            provider: Optional provider override
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            
        Returns:
            The assistant's response
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": message})
        
        provider_name = provider or self._default_provider
        llm: BaseLLM = get_provider(provider_name)
        
        return await llm.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    def create_session(
        self,
        session_id: str,
        system_prompt: Optional[str] = None,
    ) -> None:
        """
        Explicitly create a new session with an optional custom system prompt.
        
        Args:
            session_id: Unique session identifier
            system_prompt: Optional system prompt override
        """
        self.memory.create_session(session_id, system_prompt=system_prompt)
    
    def delete_session(self, session_id: str) -> bool:
        """
        End a session and delete its history.
        
        Args:
            session_id: Session to delete
            
        Returns:
            True if session existed and was deleted, False otherwise
        """
        return self.memory.delete_session(session_id)
    
    def get_session_history(self, session_id: str) -> list[dict]:
        """
        Retrieve the full conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dicts
        """
        return self.memory.get_messages(session_id)
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear conversation history but keep session alive.
        
        Args:
            session_id: Session to clear
        """
        self.memory.clear_session(session_id)
    
    @property
    def active_sessions(self) -> list[str]:
        """List all active session IDs."""
        return self.memory.active_sessions
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Get metadata about a session."""
        return self.memory.get_session_info(session_id)
