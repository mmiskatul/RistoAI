from __future__ import annotations

from app.core.enums import InsightType
from app.services.strategies.base import BaseInsightStrategy


class DemandForecastStrategy(BaseInsightStrategy):
    insight_type = InsightType.DEMAND_FORECAST

    def generate(self, context: dict) -> dict:
        total_orders = context["orders"]["total_orders"]
        forecast = max(total_orders, 10) * 1.12
        return {
            "title": "7-Day Demand Forecast",
            "summary": f"Projected order volume for the next cycle is approximately {forecast:.0f} orders.",
            "confidence": 0.74,
            "payload": {
                "forecast_orders": round(forecast),
                "staffing_recommendation": "Increase prep coverage during lunch and dinner peaks.",
            },
        }
