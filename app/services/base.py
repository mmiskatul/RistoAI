from __future__ import annotations

from bson import ObjectId

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationException
from app.utils.serialization import serialize_document, serialize_value


class BaseService:
    """Service Layer Pattern: business logic orchestration above repositories."""

    @staticmethod
    def serialize(document: dict | None) -> dict | None:
        return serialize_document(document)

    @staticmethod
    def serialize_list(documents: list[dict]) -> list[dict]:
        return [serialize_document(document) for document in documents if document is not None]

    @staticmethod
    def _object_ids(values: list[str]) -> list[ObjectId]:
        return [ObjectId(value) for value in values]

    @staticmethod
    def _user_restaurant_ids(user: dict) -> set[str]:
        return {str(value) for value in user.get("restaurant_ids", [])}

    @staticmethod
    def _user_branch_ids(user: dict) -> set[str]:
        return {str(value) for value in user.get("branch_ids", [])}

    def ensure_restaurant_access(self, user: dict, restaurant_id: str) -> None:
        if user["role"] == UserRole.SUPER_ADMIN:
            return
        if restaurant_id in self._user_restaurant_ids(user):
            return
        raise AuthorizationException("You do not have access to this restaurant")

    def ensure_branch_access(self, user: dict, branch_id: str) -> None:
        if user["role"] == UserRole.SUPER_ADMIN:
            return
        if branch_id in self._user_branch_ids(user):
            return
        raise AuthorizationException("You do not have access to this branch")

    @staticmethod
    def serialize_value(value):
        return serialize_value(value)
