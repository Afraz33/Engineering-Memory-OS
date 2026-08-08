"""
Shared types for the providers package.
"""

from __future__ import annotations

from typing import TypedDict


class ChatMessage(TypedDict):
    """A single message in a conversation."""
    role: str     # "user" | "model" | "system"
    content: str


# A flat float vector returned by embed()
EmbeddingVector = list[float]
