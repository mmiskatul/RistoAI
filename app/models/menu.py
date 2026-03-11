from __future__ import annotations

from pydantic import Field

from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class MenuCategoryDocument(MongoDocument):
    restaurant_id: PyObjectId
    name: str
    description: str | None = None
    sort_order: int = 0


class MenuItemDocument(MongoDocument):
    restaurant_id: PyObjectId
    branch_id: PyObjectId | None = None
    category_id: PyObjectId
    name: str
    description: str | None = None
    price: float
    image_url: str | None = None
    availability: bool = True
    preparation_time: int | None = None
    tags: list[str] = Field(default_factory=list)
