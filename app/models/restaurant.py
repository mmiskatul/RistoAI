from __future__ import annotations

from pydantic import Field

from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class RestaurantDocument(MongoDocument):
    owner_id: PyObjectId
    name: str
    description: str | None = None
    cuisine_type: str | None = None
    contact_email: str
    contact_phone: str | None = None
    address: str
    settings: dict = Field(default_factory=dict)
