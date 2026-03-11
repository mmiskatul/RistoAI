from __future__ import annotations

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationException, ConflictException, ValidationException
from app.core.security import password_manager
from app.repositories.user import UserRepository
from app.schemas.common import PaginatedResponse
from app.schemas.staff import StaffCreate, StaffRead, StaffUpdate
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class StaffService(BaseService):
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def create_staff(self, current_user: dict, payload: StaffCreate) -> StaffRead:
        if await self.user_repository.get_by_email(payload.email):
            raise ConflictException("An account with this email already exists")
        if current_user["role"] == UserRole.MANAGER and payload.role != UserRole.STAFF:
            raise AuthorizationException("Managers can only create staff users")
        if payload.role == UserRole.SUPER_ADMIN:
            raise ValidationException("Super admin accounts cannot be created from this endpoint")
        for restaurant_id in payload.restaurant_ids:
            self.ensure_restaurant_access(current_user, restaurant_id)
        user = await self.user_repository.create(
            {
                "email": payload.email.lower(),
                "full_name": payload.full_name,
                "phone": payload.phone,
                "hashed_password": password_manager.hash_password(payload.password),
                "role": payload.role,
                "is_active": True,
                "restaurant_ids": self._object_ids(payload.restaurant_ids),
                "branch_ids": self._object_ids(payload.branch_ids),
            }
        )
        return StaffRead(**self.serialize(user))

    async def list_staff(self, current_user: dict, restaurant_id: str, page: int, page_size: int) -> PaginatedResponse[StaffRead]:
        if current_user["role"] not in {UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.SUPER_ADMIN}:
            raise AuthorizationException("You do not have permission to view staff users")
        self.ensure_restaurant_access(current_user, restaurant_id)
        users, total = await self.user_repository.list_by_restaurant(restaurant_id, page, page_size)
        items = [StaffRead(**document) for document in self.serialize_list(users)]
        return PaginatedResponse[StaffRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=items)

    async def update_staff(self, current_user: dict, staff_id: str, payload: StaffUpdate) -> StaffRead:
        if current_user["role"] not in {UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.SUPER_ADMIN}:
            raise AuthorizationException("You do not have permission to update staff users")
        staff_user = await self.user_repository.get_by_id(staff_id)
        for restaurant_id in [str(item) for item in staff_user.get("restaurant_ids", [])]:
            self.ensure_restaurant_access(current_user, restaurant_id)
        update_payload = payload.model_dump(exclude_none=True)
        if "restaurant_ids" in update_payload:
            for restaurant_id in update_payload["restaurant_ids"]:
                self.ensure_restaurant_access(current_user, restaurant_id)
            update_payload["restaurant_ids"] = self._object_ids(update_payload["restaurant_ids"])
        if "branch_ids" in update_payload:
            update_payload["branch_ids"] = self._object_ids(update_payload["branch_ids"])
        staff_user = await self.user_repository.update(staff_id, update_payload)
        return StaffRead(**self.serialize(staff_user))
