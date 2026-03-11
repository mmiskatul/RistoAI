from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, onboarding

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
