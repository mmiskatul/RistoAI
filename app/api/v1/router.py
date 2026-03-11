from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai_insights,
    analytics,
    auth,
    branches,
    customers,
    dashboard,
    menu_categories,
    menu_items,
    notifications,
    orders,
    restaurants,
    staff,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(restaurants.router, prefix="/restaurants", tags=["Restaurants"])
api_router.include_router(branches.router, prefix="/branches", tags=["Branches"])
api_router.include_router(menu_categories.router, prefix="/menu-categories", tags=["Menu Categories"])
api_router.include_router(menu_items.router, prefix="/menu-items", tags=["Menu Items"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(orders.router, prefix="/orders", tags=["Orders"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(ai_insights.router, prefix="/ai-insights", tags=["AI Insights"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(staff.router, prefix="/staff", tags=["Staff"])
