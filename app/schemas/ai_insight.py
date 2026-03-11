from __future__ import annotations

from app.core.enums import InsightType
from app.schemas.common import BaseSchema


class AIInsightResponse(BaseSchema):
    restaurant_id: str
    insight_type: InsightType
    title: str
    summary: str
    confidence: float
    payload: dict
    generated_at: str
