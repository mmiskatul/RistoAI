from __future__ import annotations

from app.core.exceptions import ConflictException, ValidationException
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository
from app.schemas.user_management import (
    UserManagementActionResponse,
    UserManagementListItemResponse,
    UserManagementListResponse,
    UserManagementQuery,
    UserManagementSummaryResponse,
    UserManagementUpdateRequest,
)
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class UserManagementService(BaseService):
    def __init__(
        self,
        user_repository: UserRepository,
        onboarding_repository: OnboardingProfileRepository,
        auth_code_repository: AuthCodeRepository,
    ) -> None:
        self.user_repository = user_repository
        self.onboarding_repository = onboarding_repository
        self.auth_code_repository = auth_code_repository

    async def get_management_page(self, query: UserManagementQuery) -> UserManagementListResponse:
        users, total = await self.user_repository.get_filtered_users(
            search=query.search,
            role=query.role,
            is_active=query.is_active,
            page=query.page,
            page_size=query.page_size,
        )
        items = await self._build_items(users)
        pagination = build_pagination_meta(total=total, page=query.page, page_size=query.page_size)

        return UserManagementListResponse(
            summary=UserManagementSummaryResponse(
                total_users=await self.user_repository.count(),
                active_users=await self.user_repository.count({"is_active": True}),
                suspended_users=await self.user_repository.count({"is_active": False}),
            ),
            items=items,
            **pagination,
        )

    async def update_user(
        self,
        *,
        actor_user: dict,
        user_id: str,
        payload: UserManagementUpdateRequest,
    ) -> UserManagementActionResponse:
        user = await self.user_repository.get_by_id(user_id)
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            raise ValidationException("No fields provided for update")

        normalized_updates = dict(updates)
        if "email" in normalized_updates:
            normalized_updates["email"] = str(normalized_updates["email"]).lower()
            existing_user = await self.user_repository.get_by_email(normalized_updates["email"])
            if existing_user and str(existing_user["_id"]) != str(user["_id"]):
                raise ConflictException("An account with this email already exists")

        self._prevent_self_demotion(actor_user=actor_user, target_user=user, updates=normalized_updates)
        updated_user = await self.user_repository.update(user_id, normalized_updates)
        item = await self._build_item(updated_user)
        return UserManagementActionResponse(message="User updated successfully", user=item)

    async def suspend_user(self, *, actor_user: dict, user_id: str) -> UserManagementActionResponse:
        user = await self.user_repository.get_by_id(user_id)
        self._prevent_self_deactivation(actor_user=actor_user, target_user=user)
        updated_user = await self.user_repository.update(user_id, {"is_active": False})
        item = await self._build_item(updated_user)
        return UserManagementActionResponse(message="User suspended successfully", user=item)

    async def activate_user(self, user_id: str) -> UserManagementActionResponse:
        updated_user = await self.user_repository.update(user_id, {"is_active": True})
        item = await self._build_item(updated_user)
        return UserManagementActionResponse(message="User activated successfully", user=item)

    async def delete_user(self, *, actor_user: dict, user_id: str) -> None:
        user = await self.user_repository.get_by_id(user_id)
        self._prevent_self_deactivation(actor_user=actor_user, target_user=user)
        await self.user_repository.delete(user_id)
        await self.onboarding_repository.delete_by_user_id(str(user["_id"]))
        await self.auth_code_repository.delete_by_user_id(user["_id"])

    async def _build_items(self, users: list[dict]) -> list[UserManagementListItemResponse]:
        user_ids = [str(user["_id"]) for user in users]
        profiles = await self.onboarding_repository.get_by_user_ids(user_ids)
        profile_map = {profile["user_id"]: profile for profile in profiles}
        return [self._to_item(user, profile_map.get(str(user["_id"]))) for user in users]

    async def _build_item(self, user: dict) -> UserManagementListItemResponse:
        profile = await self.onboarding_repository.get_by_user_id(str(user["_id"]))
        return self._to_item(user, profile)

    def _to_item(self, user: dict, profile: dict | None) -> UserManagementListItemResponse:
        serialized_user = self.serialize(user)
        serialized_profile = self.serialize(profile) if profile else None
        return UserManagementListItemResponse(
            id=serialized_user["id"],
            full_name=serialized_user["full_name"],
            email=serialized_user["email"],
            phone=serialized_user.get("phone"),
            role=serialized_user["role"],
            restaurant_name=serialized_profile.get("restaurant_name") if serialized_profile else None,
            location=serialized_profile.get("city_location") if serialized_profile else None,
            plan=None,
            status=self._resolve_status(serialized_user),
            is_active=serialized_user["is_active"],
            email_verified=serialized_user.get("email_verified", False),
            join_date=serialized_user["created_at"][:10],
            created_at=serialized_user["created_at"],
            updated_at=serialized_user["updated_at"],
        )

    @staticmethod
    def _resolve_status(user: dict) -> str:
        if not user["is_active"]:
            return "suspended"
        if user.get("email_verified", False):
            return "active"
        return "pending"

    @staticmethod
    def _prevent_self_deactivation(*, actor_user: dict, target_user: dict) -> None:
        if str(actor_user["_id"]) == str(target_user["_id"]):
            raise ValidationException("You cannot suspend or delete your own account")

    @staticmethod
    def _prevent_self_demotion(*, actor_user: dict, target_user: dict, updates: dict) -> None:
        if str(actor_user["_id"]) != str(target_user["_id"]):
            return
        if updates.get("is_active") is False:
            raise ValidationException("You cannot suspend your own account")
        if updates.get("role") and updates["role"] != target_user["role"]:
            raise ValidationException("You cannot change your own role")
