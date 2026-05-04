from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_onboarding_service
from app.schemas.onboarding import (
    OnboardingFeatureScreenListResponse,
    OnboardingProfileResponse,
    OnboardingProfileUpsertRequest,
)
from app.services.onboarding import OnboardingService

router = APIRouter()


@router.get("/feature-screens", response_model=OnboardingFeatureScreenListResponse)
async def get_onboarding_feature_screens(
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingFeatureScreenListResponse:
    return service.get_feature_screens(accept_language)


@router.get("/profile", response_model=OnboardingProfileResponse | None)
async def get_onboarding_profile(
    current_user: dict = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProfileResponse | None:
    return await service.get_profile(current_user)


@router.post("/profile", response_model=OnboardingProfileResponse, status_code=status.HTTP_200_OK)
async def save_onboarding_profile(
    restaurant_name: str = Form(..., min_length=1, max_length=120),
    restaurant_type: str = Form(..., min_length=1, max_length=60),
    city_location: str = Form(..., min_length=1, max_length=120),
    number_of_seats: int = Form(..., ge=1, le=10000),
    average_spend_per_customer: float = Form(..., ge=0, le=100000),
    main_business_goal: str = Form(..., min_length=1, max_length=120),
    biggest_problem: str = Form(..., min_length=1, max_length=1000),
    improvement_focus: str = Form(..., min_length=1, max_length=1000),
    profile_image: UploadFile | None = File(default=None),
    interior_photo: UploadFile | None = File(default=None),
    exterior_photo: UploadFile | None = File(default=None),
    profile_image_url: str | None = Form(default=None),
    interior_photo_url: str | None = Form(default=None),
    exterior_photo_url: str | None = Form(default=None),
    current_user: dict = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingProfileResponse:
    payload = OnboardingProfileUpsertRequest(
        restaurant_name=restaurant_name,
        restaurant_type=restaurant_type,
        city_location=city_location,
        number_of_seats=number_of_seats,
        average_spend_per_customer=average_spend_per_customer,
        main_business_goal=main_business_goal,
        biggest_problem=biggest_problem,
        improvement_focus=improvement_focus,
        profile_image_url=profile_image_url,
        interior_photo_url=interior_photo_url,
        exterior_photo_url=exterior_photo_url,
    )
    return await service.save_profile_with_uploads(
        current_user,
        payload,
        profile_image=profile_image,
        interior_photo=interior_photo,
        exterior_photo=exterior_photo,
    )
