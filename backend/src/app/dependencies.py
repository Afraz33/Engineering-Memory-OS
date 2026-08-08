from functools import lru_cache

from ai.prompts.base_prompt import system_prompt
from ai.providers.registry import build_default_registry
from workers.chat_service import ChatService


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    build_default_registry()
    return ChatService(system_prompt=system_prompt)
