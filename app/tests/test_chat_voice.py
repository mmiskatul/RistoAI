from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.restaurant import RestaurantOperationsService
from app.services.openai_ops import OpenAIOperationsService


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

    async def summarize_chat_memory(self, **kwargs):
        recent_messages = kwargs.get("recent_messages") or []
        return {
            "summary": "Recent focus: salmon supplier pricing and invoice review",
            "preferences": ["brief professional answers"],
            "recurring_topics": ["supplier pricing"],
            "known_entities": [{"type": "product", "name": "Fresh Salmon", "note": "invoice item"}],
            "last_user_intent": recent_messages[-1]["message"] if recent_messages else "",
        }


class _FakeChatMemoryRepository:
    def __init__(self) -> None:
        self.stored = None

    async def get_by_scope(self, *, scope_id: str):
        return self.stored

    async def upsert_by_scope(self, *, scope_id: str, payload: dict):
        self.stored = {"_id": "memory-1", "tenant_id": scope_id, **payload}
        return self.stored


@pytest.mark.asyncio
async def test_voice_transcription_auto_detects_then_translates_to_target_language() -> None:
    openai_service = _FakeOpenAIService()
    service = RestaurantOperationsService(
        user_repository=None,
        document_repository=None,
        expense_repository=None,
        food_cost_repository=None,
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


def test_chat_business_context_includes_invoice_line_items_inventory_and_profile() -> None:
    service = RestaurantOperationsService(
        user_repository=None,
        document_repository=None,
        expense_repository=None,
        food_cost_repository=None,
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
        openai_service=_FakeOpenAIService(),
    )

    context = service._build_chat_business_context(
        current_user={"_id": "user-1", "restaurant_name": "Aldo Bistro", "city_location": "Rome"},
        onboarding_profile={"restaurant_type": "Seafood", "number_of_seats": 42, "main_business_goal": "Reduce food cost"},
        documents=[
            {
                "_id": "doc-1",
                "supplier_name": "Sea Supplier",
                "invoice_number": "INV-9",
                "invoice_date": "2026-05-01",
                "total_amount": 240,
                "currency": "EUR",
                "line_items": [
                    {"product_name": "Fresh Salmon", "quantity": 5, "unit_price": 48, "total_price": 240}
                ],
            }
        ],
        inventory_items=[
            {
                "_id": "inv-1",
                "product_name": "Fresh Salmon",
                "category": "Fish",
                "supplier_name": "Sea Supplier",
                "stock_quantity": 5,
                "unit_type": "kg",
                "unit_price": 48,
            }
        ],
        suppliers=[{"_id": "sup-1", "name": "Sea Supplier"}],
        expenses=[],
    )

    assert context["restaurant_profile"]["restaurant_name"] == "Aldo Bistro"
    assert context["restaurant_profile"]["restaurant_type"] == "Seafood"
    assert context["recent_invoices"][0]["line_items"][0]["product_name"] == "Fresh Salmon"
    assert context["inventory_items"][0]["unit_price"] == 48
    assert any("salmon" in item["product_keywords"] for item in context["market_reference_ranges"])


def test_chat_fallback_compares_invoice_item_against_market_range() -> None:
    reply = OpenAIOperationsService._build_contextual_chat_fallback_reply(
        prompt="Was the salmon price overpriced compared to the market?",
        language="en",
        metrics_context={
            "business_context": {
                "recent_invoices": [
                    {
                        "supplier_name": "Sea Supplier",
                        "invoice_number": "INV-9",
                        "line_items": [
                            {"product_name": "Fresh Salmon", "quantity": 5, "unit_price": 48, "total_price": 240}
                        ],
                    }
                ],
                "inventory_items": [],
                "market_reference_ranges": RestaurantOperationsService._chat_market_reference_ranges(),
            }
        },
    )

    assert "Fresh Salmon" in reply
    assert "€48.00" in reply
    assert "€18.00-€32.00" in reply
    assert "above" in reply
    assert "renegotiate" in reply


def test_chat_memory_fallback_summary_captures_business_focus() -> None:
    memory = OpenAIOperationsService._fallback_chat_memory_summary(
        existing_memory=None,
        recent_messages=[
            {"role": "user", "message": "I uploaded an invoice. Was the salmon price overpriced versus the market?"}
        ],
        business_context={
            "restaurant_profile": {"main_business_goal": "Reduce food cost"},
            "recent_invoices": [
                {
                    "supplier_name": "Sea Supplier",
                    "line_items": [{"product_name": "Fresh Salmon", "unit_price": 48}],
                }
            ],
        },
        language="en",
    )

    assert "salmon price" in memory["last_user_intent"]
    assert "supplier pricing" in memory["recurring_topics"]
    assert {"type": "supplier", "name": "Sea Supplier", "note": "recent invoice supplier"} in memory["known_entities"]
    assert any(item["name"] == "Fresh Salmon" for item in memory["known_entities"])


@pytest.mark.asyncio
async def test_update_chat_memory_persists_summary_for_tenant() -> None:
    memory_repository = _FakeChatMemoryRepository()
    service = RestaurantOperationsService(
        user_repository=None,
        document_repository=None,
        expense_repository=None,
        food_cost_repository=None,
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
        openai_service=_FakeOpenAIService(),
        chat_memory_repository=memory_repository,
    )

    result = await service._update_chat_memory(
        current_user={"_id": "user-1"},
        scope_id="tenant-1",
        recent_items=[
            {
                "_id": "message-1",
                "role": "user",
                "message": "Was the salmon overpriced?",
                "created_at": datetime(2026, 5, 8, tzinfo=UTC),
            },
            {
                "_id": "message-2",
                "role": "assistant",
                "message": "It was above the reference range.",
                "created_at": datetime(2026, 5, 8, tzinfo=UTC),
            },
        ],
        metrics_context={"business_context": {"recent_invoices": []}},
        language="en",
    )

    assert result["tenant_id"] == "tenant-1"
    assert result["summary"] == "Recent focus: salmon supplier pricing and invoice review"
    assert result["source_message_ids"] == ["message-1", "message-2"]
    assert result["created_by_user_id"] == "user-1"
