from __future__ import annotations

import asyncio
from functools import cached_property

from app.config.settings import Settings
from app.core.exceptions import ValidationException
from app.services.providers.base import BaseChatProvider


class HuggingFacePipelineChatProvider(BaseChatProvider):
    """Optional transformers-backed chat provider."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def _pipeline(self):
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise ValidationException("transformers is not installed for Hugging Face chat provider") from exc

        pipeline_kwargs = {}
        if self.settings.huggingface_token:
            pipeline_kwargs["token"] = self.settings.huggingface_token
        try:
            return pipeline(
                "text-generation",
                model=self.settings.ai_chat_model_id,
                **pipeline_kwargs,
            )
        except Exception as exc:
            raise ValidationException(
                "Failed to initialize Hugging Face chat model",
                details={"model": self.settings.ai_chat_model_id},
            ) from exc

    async def generate_response(self, *, system_prompt: str, user_message: str, context: dict) -> str:
        prompt = (
            f"{system_prompt}\n\n"
            f"Restaurant context: {context}\n\n"
            f"User: {user_message}\n"
            "Assistant:"
        )
        generated = await asyncio.to_thread(
            self._pipeline,
            prompt,
            max_new_tokens=self.settings.ai_chat_max_new_tokens,
            temperature=self.settings.ai_chat_temperature,
            do_sample=True,
            return_full_text=False,
        )
        return generated[0]["generated_text"].strip()
