from __future__ import annotations

from app.models.base import MongoDocument


class OnboardingProfileDocument(MongoDocument):
    user_id: str
    restaurant_name: str
    restaurant_type: str
    city_location: str
    number_of_seats: int
    average_spend_per_customer: float
    interior_photo_url: str | None = None
    exterior_photo_url: str | None = None
    main_business_goal: str
    biggest_problem: str
    improvement_focus: str
    onboarding_completed: bool = True
