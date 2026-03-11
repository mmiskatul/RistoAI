from __future__ import annotations

from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class AnalyticsSnapshotDocument(MongoDocument):
    restaurant_id: PyObjectId
    metric_type: str
    payload: dict
    period_start: str | None = None
    period_end: str | None = None
    generated_at: str
