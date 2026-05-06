from __future__ import annotations

import pytest

from app.services.restaurant import RestaurantOperationsService


class _FakeOpenAIService:
    def __init__(self) -> None:
        self.transcribe_language = None
        self.translate_target_language = None

    async def transcribe_audio(self, **kwargs):
        self.transcribe_language = kwargs.get("language")
        return "buongiorno, quanto ho venduto oggi?"

    async def translate_text(self, *, text: str, target_language: str):
        self.translate_target_language = target_language
        return "good morning, how much did I sell today?"


@pytest.mark.asyncio
async def test_voice_transcription_auto_detects_then_translates_to_target_language() -> None:
    openai_service = _FakeOpenAIService()
    service = RestaurantOperationsService(
        user_repository=None,
        document_repository=None,
        expense_repository=None,
        cash_repository=None,
        bank_account_repository=None,
        daily_record_repository=None,
        record_repository=None,
        weekly_record_repository=None,
        monthly_record_repository=None,
        finance_transaction_repository=None,
        inventory_repository=None,
        inventory_category_repository=None,
        inventory_supplier_repository=None,
        chat_repository=None,
        insight_repository=None,
        openai_service=openai_service,
    )

    text = await service.transcribe_chat_voice(
        {"preferred_language": "it"},
        file_name="voice.m4a",
        content_type="audio/mp4",
        file_bytes=b"audio-bytes",
        language="en",
    )

    assert text == "good morning, how much did I sell today?"
    assert openai_service.transcribe_language is None
    assert openai_service.translate_target_language == "en"
