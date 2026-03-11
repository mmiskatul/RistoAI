from __future__ import annotations

from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.schemas.onboarding import OnboardingProfileResponse, OnboardingProfileUpsertRequest
from app.services.base import BaseService


class OnboardingService(BaseService):
    """Service Layer Pattern: encapsulates onboarding persistence and response mapping."""

    def __init__(self, onboarding_repository: OnboardingProfileRepository) -> None:
        self.onboarding_repository = onboarding_repository

    async def save_profile(self, current_user: dict, payload: OnboardingProfileUpsertRequest) -> OnboardingProfileResponse:
        profile = await self.onboarding_repository.upsert_by_user_id(
            str(current_user["_id"]),
            {
                **payload.model_dump(mode="json"),
                "onboarding_completed": True,
            },
        )
        return self._to_response(profile)

    async def get_profile(self, current_user: dict) -> OnboardingProfileResponse | None:
        profile = await self.onboarding_repository.get_by_user_id(str(current_user["_id"]))
        if not profile:
            return None
        return self._to_response(profile)

    def _to_response(self, profile: dict) -> OnboardingProfileResponse:
        serialized = self.serialize(profile)
        return OnboardingProfileResponse(**serialized)
