from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai_chat,
    ai_insights,
    analytics,
    auth,
    dashboard,
    notifications,
    staff,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(ai_chat.router, prefix="/ai-chat", tags=["AI Chat"])
api_router.include_router(ai_insights.router, prefix="/ai-insights", tags=["AI Insights"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(staff.router, prefix="/staff", tags=["Staff"])
