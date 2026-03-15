from __future__ import annotations

from app.core.exceptions import NotFoundException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.enums import SupportTicketStatus
from app.repositories.base import BaseRepository
from app.utils.datetime import utc_now


class SupportTicketRepository(BaseRepository[dict]):
    collection_name = "support_tickets"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_filtered_user_tickets(
        self,
        user_id: str,
        *,
        search: str | None = None,
        status: SupportTicketStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        filters: list[dict[str, object]] = [{"user_id": self.to_object_id(user_id)}]
        if status is not None:
            filters.append({"status": status})
        if search:
            search_filter = {"$regex": search.strip(), "$options": "i"}
            filters.append(
                {
                    "$or": [
                        {"ticket_number": search_filter},
                        {"subject": search_filter},
                    ]
                }
            )
        resolved = {"$and": filters} if len(filters) > 1 else filters[0]
        return await self.get_multi(filters=resolved, page=page, page_size=page_size)

    async def get_filtered_tickets(
        self,
        *,
        search: str | None = None,
        status: SupportTicketStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        filters: dict[str, object] = {}
        and_filters: list[dict[str, object]] = []
        if status is not None:
            and_filters.append({"status": status})
        if search:
            search_filter = {"$regex": search.strip(), "$options": "i"}
            and_filters.append(
                {
                    "$or": [
                        {"ticket_number": search_filter},
                        {"user_name": search_filter},
                        {"email": search_filter},
                        {"restaurant_name": search_filter},
                        {"subject": search_filter},
                    ]
                }
            )
        if and_filters:
            filters = {"$and": and_filters} if len(and_filters) > 1 else and_filters[0]
        return await self.get_multi(filters=filters, page=page, page_size=page_size)

    async def count_by_status(self, status: SupportTicketStatus) -> int:
        return await self.count({"status": status})

    async def add_message(self, ticket_id: str, message: dict) -> dict:
        now = utc_now()
        result = await self.collection.find_one_and_update(
            {"_id": self.to_object_id(ticket_id)},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": now},
            },
            return_document=True,
        )
        if not result:
            raise NotFoundException('Support ticket not found')
        return await self.get_by_id(ticket_id)

    async def resolve(self, ticket_id: str) -> dict:
        now = utc_now()
        return await self.update(ticket_id, {"status": SupportTicketStatus.RESOLVED, "resolved_at": now})
