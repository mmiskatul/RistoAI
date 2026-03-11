from __future__ import annotations

from abc import ABC, abstractmethod


class BaseChatProvider(ABC):
    """Provider interface for pluggable AI chat backends."""

    @abstractmethod
    async def generate_response(self, *, system_prompt: str, user_message: str, context: dict) -> str:
        raise NotImplementedError
