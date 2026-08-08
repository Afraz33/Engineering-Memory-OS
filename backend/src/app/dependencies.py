"""
FastAPI dependency injection.

The orchestrator and registry are created once at startup (singletons)
and injected into route handlers via Depends().
"""

from ai.memory.manager import MemoryManager
from ai.prompts.base_prompt import system_prompt
from ai.providers.registry import build_default_registry
from ai.orchestrator import AIOrchestrator
from functools import lru_cache


@lru_cache(maxsize=1)
def get_orchestrator() -> AIOrchestrator:
    """
    Build and return the singleton AIOrchestrator.
    
    Called once on first request; lru_cache ensures the same instance
    is returned for every subsequent call.
    """
    # Boot the provider registry (Ollama by default)
    build_default_registry()
    
    # Memory manager with the default system prompt
    memory_manager = MemoryManager(
        system_prompt=system_prompt,
        max_messages_per_session=200,
    )
    
    return AIOrchestrator(memory_manager=memory_manager)
