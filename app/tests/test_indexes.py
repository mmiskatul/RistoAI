from __future__ import annotations

import pytest
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import OperationFailure

from app.db.indexes import _create_indexes_safely


class _FakeCursor:
    def __init__(self, indexes: list[dict]) -> None:
        self._indexes = indexes

    async def to_list(self, length=None) -> list[dict]:
        return self._indexes


class _FakeCollection:
    def __init__(self, existing_indexes: list[dict]) -> None:
        self._existing_indexes = existing_indexes
        self.create_calls: list[list[str]] = []
        self.drop_calls: list[str] = []

    async def create_indexes(self, indexes: list[IndexModel]) -> None:
        self.create_calls.append([index.document["name"] for index in indexes])
        if len(self.create_calls) == 1:
            raise OperationFailure(
                "Index already exists with a different name: idx_restaurant_invoices_tenant_invoice_date",
                code=85,
            )

    def list_indexes(self) -> _FakeCursor:
        return _FakeCursor(self._existing_indexes)

    async def drop_index(self, index_name: str) -> None:
        self.drop_calls.append(index_name)


@pytest.mark.asyncio
async def test_create_indexes_safely_reuses_equivalent_legacy_named_index() -> None:
    collection = _FakeCollection(
        [
            {"name": "_id_", "key": {"_id": ASCENDING}},
            {
                "name": "idx_restaurant_invoices_tenant_invoice_date",
                "key": {"tenant_id": ASCENDING, "invoice_date": DESCENDING},
            },
        ]
    )

    await _create_indexes_safely(
        collection,
        [
            IndexModel(
                [("tenant_id", ASCENDING), ("invoice_date", DESCENDING)],
                name="idx_restaurant_documents_tenant_invoice_date",
            )
        ],
    )

    assert collection.create_calls == [["idx_restaurant_documents_tenant_invoice_date"]]
    assert collection.drop_calls == []
