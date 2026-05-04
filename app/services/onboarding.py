from __future__ import annotations

from fastapi import UploadFile

from app.core.exceptions import ValidationException
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository
from app.schemas.onboarding import OnboardingProfileResponse, OnboardingProfileUpsertRequest
from app.services.base import BaseService
from app.services.image_storage import ImageStorageService, UploadedImage


class OnboardingService(BaseService):
    """Service Layer Pattern: encapsulates onboarding persistence and response mapping."""

    def __init__(
        self,
        onboarding_repository: OnboardingProfileRepository,
        user_repository: UserRepository,
        image_storage_service: ImageStorageService | None = None,
    ) -> None:
        self.onboarding_repository = onboarding_repository
        self.user_repository = user_repository
        self.image_storage_service = image_storage_service

    async def save_profile(self, current_user: dict, payload: OnboardingProfileUpsertRequest) -> OnboardingProfileResponse:
        return await self._save_profile(
            current_user,
            payload.model_dump(mode="json"),
            restaurant_name=payload.restaurant_name,
            city_location=payload.city_location,
        )

    async def save_profile_with_uploads(
        self,
        current_user: dict,
        payload: OnboardingProfileUpsertRequest,
        *,
        profile_image: UploadFile | None = None,
        interior_photo: UploadFile | None = None,
        exterior_photo: UploadFile | None = None,
    ) -> OnboardingProfileResponse:
        data = payload.model_dump(mode="json")
        if profile_image:
            data["profile_image_url"] = await self._upload_image(current_user, profile_image, field_name="profile_image_url")
        if interior_photo:
            data["interior_photo_url"] = await self._upload_image(current_user, interior_photo, field_name="interior_photo_url")
        if exterior_photo:
            data["exterior_photo_url"] = await self._upload_image(current_user, exterior_photo, field_name="exterior_photo_url")
        return await self._save_profile(
            current_user,
            data,
            restaurant_name=payload.restaurant_name,
            city_location=payload.city_location,
        )

    async def get_profile(self, current_user: dict) -> OnboardingProfileResponse | None:
        profile = await self.onboarding_repository.get_by_user_id(str(current_user["_id"]))
        if not profile:
            return None
        return self._to_response(profile)

    async def _upload_image(self, current_user: dict, file: UploadFile, *, field_name: str) -> str:
        if not self.image_storage_service:
            raise ValidationException("Image upload service is not configured")
        uploaded: UploadedImage = await self.image_storage_service.upload_file(
            file=file,
            prefix=f"onboarding/{current_user['_id']}/{field_name}",
        )
        return uploaded.url

    async def _save_profile(
        self,
        current_user: dict,
        payload: dict,
        *,
        restaurant_name: str,
        city_location: str,
    ) -> OnboardingProfileResponse:
        next_profile_image = (
            payload.get("profile_image_url")
            or current_user.get("profile_image_url")
            or current_user.get("avatar_url")
        )
        profile = await self.onboarding_repository.upsert_by_user_id(
            str(current_user["_id"]),
            {
                **payload,
                "onboarding_completed": True,
            },
        )
        await self.user_repository.update(
            current_user["_id"],
            {
                "restaurant_name": restaurant_name,
                "restaurant_type": payload.get("restaurant_type"),
                "city_location": city_location,
                "location": city_location,
                "number_of_seats": payload.get("number_of_seats"),
                "average_spend_per_customer": payload.get("average_spend_per_customer"),
                "main_business_goal": payload.get("main_business_goal"),
                "biggest_problem": payload.get("biggest_problem"),
                "improvement_focus": payload.get("improvement_focus"),
                "profile_image_url": next_profile_image,
                "avatar_url": next_profile_image,
                "onboarding_completed": True,
            },
        )
        return self._to_response(profile)

    def _to_response(self, profile: dict) -> OnboardingProfileResponse:
        serialized = self.serialize(profile)
        if self.image_storage_service:
            serialized["profile_image_url"] = self.image_storage_service.resolve_public_url(serialized.get("profile_image_url"))
            serialized["interior_photo_url"] = self.image_storage_service.resolve_public_url(serialized.get("interior_photo_url"))
            serialized["exterior_photo_url"] = self.image_storage_service.resolve_public_url(serialized.get("exterior_photo_url"))
        return OnboardingProfileResponse(**serialized)
