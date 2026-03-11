from __future__ import annotations

from app.core.enums import InsightType
from app.services.strategies.base import BaseInsightStrategy


class MenuOptimizationStrategy(BaseInsightStrategy):
    insight_type = InsightType.MENU_OPTIMIZATION

    def generate(self, context: dict) -> dict:
        top_items = [item["name"] for item in context["menu"][:3]]
        return {
            "title": "Menu Optimization Suggestions",
            "summary": "Highlight high-performing dishes and refine underperforming sections for better conversion.",
            "confidence": 0.79,
            "payload": {
                "top_items": top_items,
                "actions": [
                    "Pin the top-selling items to the first screen in the mobile menu",
                    "Run limited-time specials on low-performing categories",
                    "Use higher margin dishes as chef recommendations",
                ],
            },
        }
