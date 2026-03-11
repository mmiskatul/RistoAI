from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.enums import InsightType
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_ai_insight_service
from app.schemas.ai_insight import AIInsightResponse
from app.services.ai_insight import AIInsightService

router = APIRouter()


@router.get("/recommendations", response_model=AIInsightResponse)
async def recommendations(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AIInsightService = Depends(get_ai_insight_service),
) -> AIInsightResponse:
    return await service.generate_insight(current_user, restaurant_id, InsightType.RECOMMENDATIONS)


@router.get("/demand-forecast", response_model=AIInsightResponse)
async def demand_forecast(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AIInsightService = Depends(get_ai_insight_service),
) -> AIInsightResponse:
    return await service.generate_insight(current_user, restaurant_id, InsightType.DEMAND_FORECAST)


@router.get("/waste-reduction", response_model=AIInsightResponse)
async def waste_reduction(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AIInsightService = Depends(get_ai_insight_service),
) -> AIInsightResponse:
    return await service.generate_insight(current_user, restaurant_id, InsightType.WASTE_REDUCTION)


@router.get("/menu-optimization", response_model=AIInsightResponse)
async def menu_optimization(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AIInsightService = Depends(get_ai_insight_service),
) -> AIInsightResponse:
    return await service.generate_insight(current_user, restaurant_id, InsightType.MENU_OPTIMIZATION)
