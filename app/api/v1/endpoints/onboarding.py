from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_onboarding_service
from app.schemas.onboarding import OnboardingProfileResponse, OnboardingProfileUpsertRequest
from app.services.onboarding import OnboardingService

router = APIRouter()


@router.get("/profile", response_model=OnboardingProfileResponse | None)
async def get_onboarding_profile(
    current_user: dict = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProfileResponse | None:
    return await service.get_profile(current_user)


@router.post("/profile", response_model=OnboardingProfileResponse, status_code=status.HTTP_200_OK)
async def save_onboarding_profile(
    payload: OnboardingProfileUpsertRequest,
    current_user: dict = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProfileResponse:
    return await service.save_profile(current_user, payload)
