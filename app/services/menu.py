from __future__ import annotations

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationException, ValidationException
from app.repositories.branch import BranchRepository
from app.repositories.menu import MenuCategoryRepository, MenuItemRepository
from app.repositories.restaurant import RestaurantRepository
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.menu import (
    MenuAvailabilityUpdate,
    MenuCategoryCreate,
    MenuCategoryRead,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemRead,
    MenuItemUpdate,
)
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class MenuService(BaseService):
    def __init__(
        self,
        category_repository: MenuCategoryRepository,
        item_repository: MenuItemRepository,
        restaurant_repository: RestaurantRepository,
        branch_repository: BranchRepository,
    ) -> None:
        self.category_repository = category_repository
        self.item_repository = item_repository
        self.restaurant_repository = restaurant_repository
        self.branch_repository = branch_repository

    async def create_category(self, current_user: dict, payload: MenuCategoryCreate) -> MenuCategoryRead:
        self.ensure_restaurant_access(current_user, payload.restaurant_id)
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot manage menu categories")
        category = await self.category_repository.create(
            {
                "restaurant_id": self.category_repository.to_object_id(payload.restaurant_id),
                **payload.model_dump(exclude={"restaurant_id"}),
            }
        )
        return MenuCategoryRead(**self.serialize(category))

    async def list_categories(self, current_user: dict, restaurant_id: str, page: int, page_size: int) -> PaginatedResponse[MenuCategoryRead]:
        self.ensure_restaurant_access(current_user, restaurant_id)
        categories, total = await self.category_repository.list_by_restaurant(restaurant_id, page, page_size)
        items = [MenuCategoryRead(**document) for document in self.serialize_list(categories)]
        return PaginatedResponse[MenuCategoryRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=items)

    async def update_category(self, current_user: dict, category_id: str, payload: MenuCategoryUpdate) -> MenuCategoryRead:
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot manage menu categories")
        category = await self.category_repository.get_by_id(category_id)
        self.ensure_restaurant_access(current_user, str(category["restaurant_id"]))
        category = await self.category_repository.update(category_id, payload.model_dump(exclude_none=True))
        return MenuCategoryRead(**self.serialize(category))

    async def delete_category(self, current_user: dict, category_id: str) -> MessageResponse:
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot manage menu categories")
        category = await self.category_repository.get_by_id(category_id)
        self.ensure_restaurant_access(current_user, str(category["restaurant_id"]))
        await self.category_repository.delete(category_id)
        return MessageResponse(message="Category deleted successfully")

    async def create_item(self, current_user: dict, payload: MenuItemCreate) -> MenuItemRead:
        self.ensure_restaurant_access(current_user, payload.restaurant_id)
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot manage menu items")
        await self._validate_menu_relationships(payload.restaurant_id, payload.category_id, payload.branch_id)
        item = await self.item_repository.create(
            {
                "restaurant_id": self.item_repository.to_object_id(payload.restaurant_id),
                "category_id": self.item_repository.to_object_id(payload.category_id),
                "branch_id": self.item_repository.to_object_id(payload.branch_id) if payload.branch_id else None,
                **payload.model_dump(exclude={"restaurant_id", "category_id", "branch_id"}),
            }
        )
        return MenuItemRead(**self.serialize(item))

    async def list_items(
        self,
        current_user: dict,
        restaurant_id: str,
        page: int,
        page_size: int,
        branch_id: str | None = None,
    ) -> PaginatedResponse[MenuItemRead]:
        self.ensure_restaurant_access(current_user, restaurant_id)
        items, total = await self.item_repository.list_by_restaurant(restaurant_id, page, page_size, branch_id)
        serialized = [MenuItemRead(**document) for document in self.serialize_list(items)]
        return PaginatedResponse[MenuItemRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=serialized)

    async def get_item(self, current_user: dict, item_id: str) -> MenuItemRead:
        item = await self.item_repository.get_by_id(item_id)
        self.ensure_restaurant_access(current_user, str(item["restaurant_id"]))
        return MenuItemRead(**self.serialize(item))

    async def update_item(self, current_user: dict, item_id: str, payload: MenuItemUpdate) -> MenuItemRead:
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot manage menu items")
        item = await self.item_repository.get_by_id(item_id)
        self.ensure_restaurant_access(current_user, str(item["restaurant_id"]))
        update_payload = payload.model_dump(exclude_none=True)
        category_id = update_payload.get("category_id", str(item["category_id"]))
        branch_id = update_payload.get("branch_id", str(item["branch_id"]) if item.get("branch_id") else None)
        await self._validate_menu_relationships(str(item["restaurant_id"]), category_id, branch_id)
        if "category_id" in update_payload:
            update_payload["category_id"] = self.item_repository.to_object_id(update_payload["category_id"])
        if "branch_id" in update_payload and update_payload["branch_id"]:
            update_payload["branch_id"] = self.item_repository.to_object_id(update_payload["branch_id"])
        item = await self.item_repository.update(item_id, update_payload)
        return MenuItemRead(**self.serialize(item))

    async def delete_item(self, current_user: dict, item_id: str) -> MessageResponse:
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot manage menu items")
        item = await self.item_repository.get_by_id(item_id)
        self.ensure_restaurant_access(current_user, str(item["restaurant_id"]))
        await self.item_repository.delete(item_id)
        return MessageResponse(message="Menu item deleted successfully")

    async def toggle_availability(self, current_user: dict, item_id: str, payload: MenuAvailabilityUpdate) -> MenuItemRead:
        if current_user["role"] == UserRole.STAFF:
            raise AuthorizationException("Staff cannot manage menu items")
        item = await self.item_repository.get_by_id(item_id)
        self.ensure_restaurant_access(current_user, str(item["restaurant_id"]))
        item = await self.item_repository.update(item_id, {"availability": payload.availability})
        return MenuItemRead(**self.serialize(item))

    async def _validate_menu_relationships(self, restaurant_id: str, category_id: str, branch_id: str | None) -> None:
        category = await self.category_repository.get_by_id(category_id)
        if str(category["restaurant_id"]) != restaurant_id:
            raise ValidationException("Category does not belong to the restaurant")
        if branch_id:
            branch = await self.branch_repository.get_by_id(branch_id)
            if str(branch["restaurant_id"]) != restaurant_id:
                raise ValidationException("Branch does not belong to the restaurant")
