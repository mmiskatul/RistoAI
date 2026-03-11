from __future__ import annotations

from app.repositories.restaurant import RestaurantRepository
from app.schemas.ai_chat import AIChatMessageRequest, AIChatMessageResponse
from app.services.analytics import AnalyticsService
from app.services.base import BaseService
from app.services.providers.base import BaseChatProvider


class AIChatService(BaseService):
    def __init__(
        self,
        *,
        provider: BaseChatProvider,
        provider_name: str,
        model_name: str,
        analytics_service: AnalyticsService,
        restaurant_repository: RestaurantRepository,
    ) -> None:
        self.provider = provider
        self.provider_name = provider_name
        self.model_name = model_name
        self.analytics_service = analytics_service
        self.restaurant_repository = restaurant_repository

    async def message(self, current_user: dict, payload: AIChatMessageRequest) -> AIChatMessageResponse:
        self.ensure_restaurant_access(current_user, payload.restaurant_id)
        restaurant = await self.restaurant_repository.get_by_id(payload.restaurant_id)
        summary = await self.analytics_service.dashboard_summary(current_user, payload.restaurant_id)
        sales = await self.analytics_service.sales_analytics(current_user, payload.restaurant_id)
        menu = await self.analytics_service.menu_performance(current_user, payload.restaurant_id)

        system_prompt = (
            "You are RistoAI, a restaurant operations copilot. "
            "Answer briefly, prioritize practical actions, and stay grounded in the provided restaurant data."
        )
        context = {
            "restaurant": {
                "id": str(restaurant["_id"]),
                "name": restaurant["name"],
                "cuisine_type": restaurant.get("cuisine_type"),
            },
            "dashboard_summary": summary.model_dump(),
            "sales_analytics": sales.model_dump(),
            "top_menu_items": [item.model_dump() for item in menu.top_items],
        }
        reply = await self.provider.generate_response(
            system_prompt=system_prompt,
            user_message=payload.message,
            context=context,
        )
        return AIChatMessageResponse(
            restaurant_id=payload.restaurant_id,
            provider=self.provider_name,
            model=self.model_name,
            reply=reply,
        )
