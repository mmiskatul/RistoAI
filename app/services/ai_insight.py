from __future__ import annotations

from app.core.enums import InsightType
from app.schemas.ai_insight import AIInsightResponse
from app.services.analytics import AnalyticsService
from app.services.base import BaseService
from app.services.strategies.base import BaseInsightStrategy
from app.utils.datetime import utc_now


class AIInsightService(BaseService):
    def __init__(
        self,
        analytics_service: AnalyticsService,
        strategies: dict[InsightType, BaseInsightStrategy],
    ) -> None:
        self.analytics_service = analytics_service
        self.strategies = strategies

    async def generate_insight(self, current_user: dict, restaurant_id: str, insight_type: InsightType) -> AIInsightResponse:
        sales = await self.analytics_service.sales_analytics(current_user, restaurant_id)
        orders = await self.analytics_service.orders_analytics(current_user, restaurant_id)
        menu = await self.analytics_service.menu_performance(current_user, restaurant_id)
        context = {
            "sales": sales.model_dump(),
            "orders": orders.model_dump(),
            "menu": [item.model_dump() for item in menu.top_items],
        }
        strategy = self.strategies[insight_type]
        generated = strategy.generate(context)
        return AIInsightResponse(
            restaurant_id=restaurant_id,
            insight_type=insight_type,
            title=generated["title"],
            summary=generated["summary"],
            confidence=generated["confidence"],
            payload=generated["payload"],
            generated_at=utc_now().isoformat(),
        )
