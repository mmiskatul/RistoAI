from __future__ import annotations

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationException
from app.repositories.branch import BranchRepository
from app.repositories.restaurant import RestaurantRepository
from app.repositories.user import UserRepository
from app.schemas.branch import BranchCreate, BranchRead, BranchUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class BranchService(BaseService):
    def __init__(
        self,
        branch_repository: BranchRepository,
        restaurant_repository: RestaurantRepository,
        user_repository: UserRepository,
    ) -> None:
        self.branch_repository = branch_repository
        self.restaurant_repository = restaurant_repository
        self.user_repository = user_repository

    async def create_branch(self, current_user: dict, payload: BranchCreate) -> BranchRead:
        self.ensure_restaurant_access(current_user, payload.restaurant_id)
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot create branches")
        branch = await self.branch_repository.create(
            {
                "restaurant_id": self.branch_repository.to_object_id(payload.restaurant_id),
                "name": payload.name,
                "address": payload.address,
                "phone": payload.phone,
                "manager_ids": self._object_ids(payload.manager_ids),
                "is_active": True,
            }
        )
        for manager_id in payload.manager_ids:
            await self.user_repository.append_restaurant(manager_id, payload.restaurant_id)
            await self.user_repository.append_branch(manager_id, branch["_id"])
        return BranchRead(**self.serialize(branch))

    async def list_branches(self, current_user: dict, restaurant_id: str, page: int, page_size: int) -> PaginatedResponse[BranchRead]:
        self.ensure_restaurant_access(current_user, restaurant_id)
        branches, total = await self.branch_repository.list_by_restaurant(restaurant_id, page, page_size)
        items = [BranchRead(**document) for document in self.serialize_list(branches)]
        return PaginatedResponse[BranchRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=items)

    async def update_branch(self, current_user: dict, branch_id: str, payload: BranchUpdate) -> BranchRead:
        branch = await self.branch_repository.get_by_id(branch_id)
        self.ensure_restaurant_access(current_user, str(branch["restaurant_id"]))
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot update branches")
        update_payload = payload.model_dump(exclude_none=True)
        if "manager_ids" in update_payload:
            update_payload["manager_ids"] = self._object_ids(update_payload["manager_ids"])
        branch = await self.branch_repository.update(branch_id, update_payload)
        if payload.manager_ids:
            for manager_id in payload.manager_ids:
                await self.user_repository.append_restaurant(manager_id, str(branch["restaurant_id"]))
                await self.user_repository.append_branch(manager_id, branch["_id"])
        return BranchRead(**self.serialize(branch))

    async def delete_branch(self, current_user: dict, branch_id: str) -> MessageResponse:
        branch = await self.branch_repository.get_by_id(branch_id)
        self.ensure_restaurant_access(current_user, str(branch["restaurant_id"]))
        if current_user["role"] not in {UserRole.RESTAURANT_OWNER, UserRole.SUPER_ADMIN}:
            raise AuthorizationException("Only owners can delete branches")
        await self.branch_repository.delete(branch_id)
        return MessageResponse(message="Branch deleted successfully")
