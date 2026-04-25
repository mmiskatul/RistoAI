from __future__ import annotations

from datetime import datetime

from app.core.enums import AccountStatus, SubscriptionPlan, SubscriptionStatus
from app.core.exceptions import ConflictException, ValidationException
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository
from app.schemas.user_management import (
    UserManagementActionResponse,
    UserManagementFilterChipResponse,
    UserManagementListItemResponse,
    UserManagementListResponse,
    UserManagementQuery,
    UserManagementRowActionResponse,
    UserManagementSummaryCardResponse,
    UserManagementSummaryResponse,
    UserManagementTableColumnResponse,
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
            subscription_status=query.subscription_status,
            page=query.page,
            page_size=query.page_size,
        )
        items = [self._to_item(user) for user in users]
        pagination = build_pagination_meta(total=total, page=query.page, page_size=query.page_size)
        summary = UserManagementSummaryResponse(
            total_users=await self.user_repository.count(),
            active_users=await self.user_repository.count({"is_active": True}),
            suspended_users=await self.user_repository.count({"is_active": False}),
            trial_users=await self.user_repository.count({"subscription_status": SubscriptionStatus.TRIAL}),
        )

        return UserManagementListResponse(
            summary=summary,
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
        if (
            normalized_updates.get("subscription_started_at")
            and normalized_updates.get("subscription_expires_at")
            and normalized_updates["subscription_expires_at"] <= normalized_updates["subscription_started_at"]
        ):
            raise ValidationException("Subscription expiry must be later than the start date")

        self._prevent_self_demotion(actor_user=actor_user, target_user=user, updates=normalized_updates)
        updated_user = await self.user_repository.update(user_id, normalized_updates)
        item = self._to_item(updated_user)
        return UserManagementActionResponse(message="User updated successfully", user=item)

    async def suspend_user(self, *, actor_user: dict, user_id: str) -> UserManagementActionResponse:
        user = await self.user_repository.get_by_id(user_id)
        self._prevent_self_deactivation(actor_user=actor_user, target_user=user)
        updated_user = await self.user_repository.update(
            user_id,
            {"is_active": False, "account_status": AccountStatus.SUSPENDED},
        )
        item = self._to_item(updated_user)
        return UserManagementActionResponse(message="User suspended successfully", user=item)

    async def activate_user(self, user_id: str) -> UserManagementActionResponse:
        user = await self.user_repository.get_by_id(user_id)
        resolved_status = user.get("subscription_status")
        if resolved_status == SubscriptionStatus.SUSPENDED:
            resolved_status = SubscriptionStatus.ACTIVE
        updated_user = await self.user_repository.update(
            user_id,
            {"is_active": True, "subscription_status": resolved_status, "account_status": None},
        )
        item = self._to_item(updated_user)
        return UserManagementActionResponse(message="User activated successfully", user=item)

    async def restrict_user(self, *, actor_user: dict, user_id: str) -> UserManagementActionResponse:
        user = await self.user_repository.get_by_id(user_id)
        self._prevent_self_deactivation(actor_user=actor_user, target_user=user)
        updated_user = await self.user_repository.update(
            user_id,
            {"is_active": False, "account_status": AccountStatus.RESTRICTED},
        )
        item = self._to_item(updated_user)
        return UserManagementActionResponse(message="User restricted successfully", user=item)

    def _to_item(self, user: dict) -> UserManagementListItemResponse:
        serialized_user = self.serialize(user)
        status = self._resolve_status(serialized_user)
        subscription_plan = serialized_user.get("subscription_plan")
        return UserManagementListItemResponse(
            id=serialized_user["id"],
            full_name=serialized_user["full_name"],
            email=serialized_user["email"],
            phone=serialized_user.get("phone"),
            role=serialized_user["role"],
            restaurant_name=serialized_user.get("restaurant_name"),
            location=serialized_user.get("location"),
            subscription_plan_name=serialized_user.get("subscription_plan_name"),
            subscription_plan=subscription_plan,
            subscription_status=serialized_user.get("subscription_status"),
            account_status=serialized_user.get("account_status"),
            subscription_started_at=serialized_user.get("subscription_started_at"),
            subscription_expires_at=serialized_user.get("subscription_expires_at"),
            status=status,
            is_active=serialized_user["is_active"],
            email_verified=serialized_user.get("email_verified", False),
            join_date=serialized_user["created_at"][:10],
            created_at=serialized_user["created_at"],
            updated_at=serialized_user["updated_at"],
        )

    @staticmethod
    def _resolve_status(user: dict) -> str:
        if not user["is_active"]:
            if user.get("account_status"):
                return user["account_status"]
            return "suspended"
        if user.get("subscription_status"):
            return user["subscription_status"]
        if user.get("email_verified", False):
            return "active"
        return "pending"

    @staticmethod
    def _prevent_self_deactivation(*, actor_user: dict, target_user: dict) -> None:
        if str(actor_user["_id"]) == str(target_user["_id"]):
            raise ValidationException("You cannot suspend or restrict your own account")

    @staticmethod
    def _prevent_self_demotion(*, actor_user: dict, target_user: dict, updates: dict) -> None:
        if str(actor_user["_id"]) != str(target_user["_id"]):
            return
        if updates.get("is_active") is False:
            raise ValidationException("You cannot suspend your own account")
        if updates.get("role") and updates["role"] != target_user["role"]:
            raise ValidationException("You cannot change your own role")
