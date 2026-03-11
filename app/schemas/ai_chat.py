from __future__ import annotations

from pydantic import Field

from app.schemas.common import BaseSchema


class AIChatMessageRequest(BaseSchema):
    restaurant_id: str
    message: str = Field(min_length=2, max_length=4000)


class AIChatMessageResponse(BaseSchema):
    restaurant_id: str
    provider: str
    model: str
    reply: str
