from __future__ import annotations

from typing import Annotated, Any

from bson import ObjectId
from pydantic import BeforeValidator, PlainSerializer


def validate_object_id(value: Any) -> ObjectId:
    """Validate and convert a MongoDB ObjectId."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError("Invalid ObjectId")


PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(validate_object_id),
    PlainSerializer(lambda value: str(value), return_type=str),
]
