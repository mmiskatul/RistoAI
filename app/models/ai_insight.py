from __future__ import annotations

from app.core.enums import InsightType
from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class AIInsightDocument(MongoDocument):
    restaurant_id: PyObjectId
    insight_type: InsightType
    title: str
    summary: str
    payload: dict
    confidence: float
    generated_at: str
