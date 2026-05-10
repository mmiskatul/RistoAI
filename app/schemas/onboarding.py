from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema, MongoReadSchema


class OnboardingProfileUpsertRequest(BaseSchema):
    restaurant_name: str = Field(min_length=1, max_length=120)
    restaurant_type: str = Field(min_length=1, max_length=60)
    city_location: str = Field(min_length=1, max_length=120)
    number_of_seats: int = Field(ge=1, le=10000)
    average_spend_per_customer: float = Field(ge=0, le=100000)
    profile_image_url: str | None = None
    interior_photo_url: str | None = None
    exterior_photo_url: str | None = None
    main_business_goal: str = Field(min_length=1, max_length=120)
    biggest_problem: str = Field(min_length=1, max_length=1000)
    improvement_focus: str = Field(min_length=1, max_length=1000)

    @field_validator("restaurant_type", "main_business_goal")
    @classmethod
    def normalize_short_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("profile_image_url", "interior_photo_url", "exterior_photo_url")
    @classmethod
    def validate_image_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.lower().startswith(("http://", "https://", "data:image/")):
            return normalized
        raise ValueError("Image URL must start with http://, https://, or data:image/")


class OnboardingProfileResponse(MongoReadSchema):
    user_id: str
    restaurant_name: str
    restaurant_type: str
    city_location: str
    number_of_seats: int
    average_spend_per_customer: float
    profile_image_url: str | None = None
    interior_photo_url: str | None = None
    exterior_photo_url: str | None = None
    main_business_goal: str
    biggest_problem: str
    improvement_focus: str
    onboarding_completed: bool


class OnboardingFeatureScreenResponse(BaseSchema):
    key: str
    icon: str
    title: str
    description: str
    points: list[str]


class OnboardingFeatureScreenListResponse(BaseSchema):
    language: str
    screens: list[OnboardingFeatureScreenResponse]
