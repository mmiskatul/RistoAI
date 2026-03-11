from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.enums import InsightType


class BaseInsightStrategy(ABC):
    """Strategy Pattern: each AI insight type is swappable behind a common interface."""

    insight_type: InsightType

    @abstractmethod
    def generate(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
