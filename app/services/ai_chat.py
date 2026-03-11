from __future__ import annotations

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
    ) -> None:
        self.provider = provider
        self.provider_name = provider_name
        self.model_name = model_name
        self.analytics_service = analytics_service

    async def message(self, current_user: dict, payload: AIChatMessageRequest) -> AIChatMessageResponse:
        summary = await self.analytics_service.dashboard_summary(current_user, payload.restaurant_id)
        sales = await self.analytics_service.sales_analytics(current_user, payload.restaurant_id)
        menu = await self.analytics_service.menu_performance(current_user, payload.restaurant_id)

        system_prompt = (
            "You are RistoAI, a restaurant operations copilot. "
            "Answer briefly, prioritize practical actions, and stay grounded in the provided restaurant data."
        )
        context = {
            "restaurant": {
                "id": payload.restaurant_id,
                "name": "Removed domain placeholder",
                "cuisine_type": None,
            },
            "dashboard_summary": summary.model_dump(),
            "sales_analytics": sales.model_dump(),
            "top_menu_items": [item.model_dump() for item in menu.top_items],
            "user_role": str(current_user.get("role")),
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
