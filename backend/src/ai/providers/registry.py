"""
Provider registry — the central wrapper that selects and manages LLM providers.

Adding a new provider (e.g. OpenAI, Gemini) is a one-liner:
    registry.register("openai", OpenAIProvider(...))
"""

from typing import Dict, Optional
from .base import BaseLLM
from .ollama import OllamaProvider


class ProviderRegistry:
    """
    Central provider registry.
    
    Holds named provider instances and routes requests to whichever
    one is currently active. Swap the active provider at runtime via
    `set_active(name)` without restarting the server.
    """
    
    def __init__(self):
        self._providers: Dict[str, BaseLLM] = {}
        self._active: Optional[str] = None
    
    def register(self, name: str, provider: BaseLLM) -> None:
        """
        Register a provider under a name.
        
        Args:
            name: Identifier (e.g. "ollama", "openai", "gemini")
            provider: A concrete BaseLLM instance
        """
        self._providers[name] = provider
        # Auto-set first registered provider as active
        if self._active is None:
            self._active = name
    
    def set_active(self, name: str) -> None:
        """
        Switch the active provider.
        
        Args:
            name: Name of an already-registered provider
            
        Raises:
            ValueError: If the name is not registered
        """
        if name not in self._providers:
            raise ValueError(
                f"Provider '{name}' is not registered. "
                f"Available: {list(self._providers.keys())}"
            )
        self._active = name
    
    def get(self, name: Optional[str] = None) -> BaseLLM:
        """
        Return a provider by name, or the active one if no name given.
        
        Args:
            name: Optional provider name; defaults to active provider
            
        Returns:
            The requested BaseLLM instance
            
        Raises:
            RuntimeError: If no providers are registered
            ValueError: If the requested name is not registered
        """
        if not self._providers:
            raise RuntimeError("No LLM providers are registered.")
        
        target = name or self._active
        if target not in self._providers:
            raise ValueError(f"Provider '{target}' is not registered.")
        
        return self._providers[target]
    
    @property
    def active_name(self) -> Optional[str]:
        """Name of the currently active provider."""
        return self._active
    
    @property
    def available(self) -> list[str]:
        """List of registered provider names."""
        return list(self._providers.keys())
    
    async def chat(self, messages: list[dict], **kwargs) -> str:
        """
        Convenience method — chat using the active provider.
        
        Args:
            messages: Conversation messages
            **kwargs: Forwarded to the provider's chat() method
            
        Returns:
            The assistant's response text
        """
        return await self.get().chat(messages, **kwargs)
    
    async def close_all(self) -> None:
        """Close all registered providers (call on shutdown)."""
        for provider in self._providers.values():
            await provider.close()


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly anywhere in the codebase.
# ---------------------------------------------------------------------------

_registry = ProviderRegistry()


def build_default_registry() -> ProviderRegistry:
    """
    Create the default registry pre-populated with Ollama.
    
    Override model / base_url via env vars:
    - OLLAMA_MODEL (default: qwen3.5:0.8b)
    - OLLAMA_BASE_URL (default: http://localhost:11434)
    """
    import os
    
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:0.8b")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    _registry.register(
        "ollama",
        OllamaProvider(model=ollama_model, base_url=ollama_url),
    )
    
    # Future providers drop in here:
    # from .openai import OpenAIProvider
    # _registry.register("openai", OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY")))
    
    return _registry


def get_provider(name: Optional[str] = None) -> BaseLLM:
    """
    Shortcut to fetch a provider from the module-level registry.
    
    Args:
        name: Optional provider name; returns active provider if omitted
    """
    return _registry.get(name)


def get_registry() -> ProviderRegistry:
    """Return the module-level ProviderRegistry singleton."""
    return _registry
