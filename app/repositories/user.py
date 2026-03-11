from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository
from app.utils.datetime import utc_now


class UserRepository(BaseRepository[dict]):
    collection_name = "users"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_email(self, email: str) -> dict | None:
        return await self.get_one({"email": email.lower()})

    async def list_by_restaurant(self, restaurant_id: str, page: int, page_size: int) -> tuple[list[dict], int]:
        return await self.get_multi(
            filters={"restaurant_ids": ObjectId(restaurant_id)},
            page=page,
            page_size=page_size,
        )

    async def append_restaurant(self, user_id: str | ObjectId, restaurant_id: str | ObjectId) -> None:
        await self.collection.update_one(
            {"_id": self.to_object_id(user_id)},
            {"$addToSet": {"restaurant_ids": self.to_object_id(restaurant_id)}},
        )

    async def append_branch(self, user_id: str | ObjectId, branch_id: str | ObjectId) -> None:
        await self.collection.update_one(
            {"_id": self.to_object_id(user_id)},
            {"$addToSet": {"branch_ids": self.to_object_id(branch_id)}},
        )

    async def set_assignments(
        self,
        user_id: str | ObjectId,
        *,
        restaurant_ids: list[str] | None = None,
        branch_ids: list[str] | None = None,
    ) -> None:
        update_payload = {}
        if restaurant_ids is not None:
            update_payload["restaurant_ids"] = [self.to_object_id(item) for item in restaurant_ids]
        if branch_ids is not None:
            update_payload["branch_ids"] = [self.to_object_id(item) for item in branch_ids]
        if update_payload:
            update_payload["updated_at"] = utc_now()
            await self.collection.update_one({"_id": self.to_object_id(user_id)}, {"$set": update_payload})
