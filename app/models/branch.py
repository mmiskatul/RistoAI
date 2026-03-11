from __future__ import annotations

from pydantic import Field

from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class BranchDocument(MongoDocument):
    restaurant_id: PyObjectId
    name: str
    address: str
    phone: str | None = None
    manager_ids: list[PyObjectId] = Field(default_factory=list)
    is_active: bool = True
