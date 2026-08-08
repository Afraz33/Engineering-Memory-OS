"""Base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseLLM(ABC):
    """Abstract base class for all LLM providers."""
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        """
        Send chat messages and get a response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            
        Returns:
            The assistant's response text
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Clean up resources."""
        pass