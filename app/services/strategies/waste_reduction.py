from __future__ import annotations

from app.core.enums import InsightType
from app.services.strategies.base import BaseInsightStrategy


class WasteReductionStrategy(BaseInsightStrategy):
    insight_type = InsightType.WASTE_REDUCTION

    def generate(self, context: dict) -> dict:
        low_velocity = context["menu"][ -1 ]["name"] if context["menu"] else "slow-moving items"
        return {
            "title": "Waste Reduction Opportunities",
            "summary": f"Review procurement and prep quantities for {low_velocity} to reduce spoilage risk.",
            "confidence": 0.69,
            "payload": {
                "actions": [
                    "Prepare smaller batches for low-velocity items",
                    "Use demand-based prep cutoffs per branch",
                    "Track end-of-day leftover reasons in staff workflow",
                ]
            },
        }
