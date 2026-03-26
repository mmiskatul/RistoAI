from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, dashboard, onboarding, restaurant, settings, subscriptions, support, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix='/auth')
api_router.include_router(onboarding.router, prefix='/onboarding', tags=['Onboarding'])
api_router.include_router(dashboard.router, prefix='/dashboard')
api_router.include_router(restaurant.router, prefix='/restaurant')
api_router.include_router(users.router, prefix='/users', tags=['Users'])
api_router.include_router(subscriptions.router, prefix='/subscriptions')
api_router.include_router(settings.router, prefix='/settings')
api_router.include_router(support.router, prefix='/support')




