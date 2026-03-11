from __future__ import annotations

from app.core.enums import InsightType
from app.services.strategies.base import BaseInsightStrategy


class RecommendationsStrategy(BaseInsightStrategy):
    insight_type = InsightType.RECOMMENDATIONS

    def generate(self, context: dict) -> dict:
        avg_order_value = context["sales"]["average_order_value"]
        top_item = context["menu"][0]["name"] if context["menu"] else "your best-selling dishes"
        summary = (
            f"Average order value is {avg_order_value:.2f}. Bundle {top_item} with complementary add-ons "
            "and promote it during peak demand windows."
        )
        return {
            "title": "Revenue Growth Recommendations",
            "summary": summary,
            "confidence": 0.82,
            "payload": {
                "actions": [
                    "Introduce meal bundles around top-performing items",
                    "Promote add-ons at checkout",
                    "Create branch-level upsell scripts for staff",
                ]
            },
        }
