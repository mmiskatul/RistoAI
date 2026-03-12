from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, dashboard, onboarding, subscriptions, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix='/auth', tags=['Authentication'])
api_router.include_router(onboarding.router, prefix='/onboarding', tags=['Onboarding'])
api_router.include_router(dashboard.router, prefix='/dashboard', tags=['Dashboard'])
api_router.include_router(users.router, prefix='/users', tags=['Users'])
api_router.include_router(subscriptions.router, prefix='/subscriptions')
