from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.utils.object_id import PyObjectId


class MongoDocument(BaseModel):
    """Base document with MongoDB-specific metadata."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="forbid")

    id: PyObjectId | None = Field(default=None, alias="_id")
    created_at: datetime
    updated_at: datetime
