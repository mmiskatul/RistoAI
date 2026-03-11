from __future__ import annotations

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationException
from app.repositories.restaurant import RestaurantRepository
from app.repositories.user import UserRepository
from app.schemas.common import PaginatedResponse
from app.schemas.restaurant import RestaurantCreate, RestaurantRead, RestaurantUpdate
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class RestaurantService(BaseService):
    def __init__(self, restaurant_repository: RestaurantRepository, user_repository: UserRepository) -> None:
        self.restaurant_repository = restaurant_repository
        self.user_repository = user_repository

    async def create_restaurant(self, current_user: dict, payload: RestaurantCreate) -> RestaurantRead:
        if current_user["role"] not in {UserRole.RESTAURANT_OWNER, UserRole.SUPER_ADMIN}:
            raise AuthorizationException("Only restaurant owners can create restaurants")
        restaurant = await self.restaurant_repository.create({**payload.model_dump(), "owner_id": current_user["_id"]})
        await self.user_repository.append_restaurant(current_user["_id"], restaurant["_id"])
        current_user.setdefault("restaurant_ids", []).append(restaurant["_id"])
        return RestaurantRead(**self.serialize(restaurant))

    async def get_restaurant(self, current_user: dict, restaurant_id: str) -> RestaurantRead:
        self.ensure_restaurant_access(current_user, restaurant_id)
        restaurant = await self.restaurant_repository.get_by_id(restaurant_id)
        return RestaurantRead(**self.serialize(restaurant))

    async def update_restaurant(self, current_user: dict, restaurant_id: str, payload: RestaurantUpdate) -> RestaurantRead:
        self.ensure_restaurant_access(current_user, restaurant_id)
        if current_user["role"] not in {UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.SUPER_ADMIN}:
            raise AuthorizationException("You do not have permission to update restaurant profiles")
        restaurant = await self.restaurant_repository.update(restaurant_id, payload.model_dump(exclude_none=True))
        return RestaurantRead(**self.serialize(restaurant))

    async def list_restaurants(self, current_user: dict, page: int, page_size: int) -> PaginatedResponse[RestaurantRead]:
        if current_user["role"] == UserRole.SUPER_ADMIN:
            restaurants, total = await self.restaurant_repository.get_multi(page=page, page_size=page_size)
        else:
            restaurants, total = await self.restaurant_repository.list_by_ids(
                [str(item) for item in current_user.get("restaurant_ids", [])],
                page,
                page_size,
            )
        items = [RestaurantRead(**document) for document in self.serialize_list(restaurants)]
        return PaginatedResponse[RestaurantRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=items)
