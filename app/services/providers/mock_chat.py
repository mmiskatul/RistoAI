from __future__ import annotations

from app.services.providers.base import BaseChatProvider


class MockChatProvider(BaseChatProvider):
    """Deterministic fallback provider used when no LLM runtime is configured."""

    async def generate_response(self, *, system_prompt: str, user_message: str, context: dict) -> str:
        restaurant_name = context.get("restaurant", {}).get("name", "your restaurant")
        summary = context.get("dashboard_summary", {})
        return (
            f"For {restaurant_name}, the current snapshot shows {summary.get('total_orders', 0)} orders and "
            f"{summary.get('total_revenue', 0.0):.2f} in revenue. Based on your question '{user_message}', "
            "I recommend reviewing top-selling menu items, order bottlenecks, and branch staffing coverage."
        )
