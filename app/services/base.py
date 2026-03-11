from __future__ import annotations

from app.utils.serialization import serialize_document, serialize_value


class BaseService:
    """Shared service helpers."""

    @staticmethod
    def serialize(document: dict | None) -> dict | None:
        return serialize_document(document)

    @staticmethod
    def serialize_list(documents: list[dict]) -> list[dict]:
        return [serialize_document(document) for document in documents if document is not None]

    @staticmethod
    def serialize_value(value):
        return serialize_value(value)
