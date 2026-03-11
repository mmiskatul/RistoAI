from __future__ import annotations

from app.repositories.customer import CustomerRepository
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class CustomerService(BaseService):
    def __init__(self, customer_repository: CustomerRepository) -> None:
        self.customer_repository = customer_repository

    async def create_customer(self, current_user: dict, payload: CustomerCreate) -> CustomerRead:
        self.ensure_restaurant_access(current_user, payload.restaurant_id)
        customer = await self.customer_repository.create(
            {
                "restaurant_id": self.customer_repository.to_object_id(payload.restaurant_id),
                "branch_id": self.customer_repository.to_object_id(payload.branch_id) if payload.branch_id else None,
                **payload.model_dump(exclude={"restaurant_id", "branch_id"}),
                "total_orders": 0,
                "total_spent": 0.0,
                "last_order_at": None,
            }
        )
        return CustomerRead(**self.serialize(customer))

    async def list_customers(self, current_user: dict, restaurant_id: str, page: int, page_size: int) -> PaginatedResponse[CustomerRead]:
        self.ensure_restaurant_access(current_user, restaurant_id)
        customers, total = await self.customer_repository.list_by_restaurant(restaurant_id, page, page_size)
        items = [CustomerRead(**document) for document in self.serialize_list(customers)]
        return PaginatedResponse[CustomerRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=items)

    async def get_customer(self, current_user: dict, customer_id: str) -> CustomerRead:
        customer = await self.customer_repository.get_by_id(customer_id)
        self.ensure_restaurant_access(current_user, str(customer["restaurant_id"]))
        return CustomerRead(**self.serialize(customer))

    async def update_customer(self, current_user: dict, customer_id: str, payload: CustomerUpdate) -> CustomerRead:
        customer = await self.customer_repository.get_by_id(customer_id)
        self.ensure_restaurant_access(current_user, str(customer["restaurant_id"]))
        update_payload = payload.model_dump(exclude_none=True)
        if "branch_id" in update_payload and update_payload["branch_id"]:
            update_payload["branch_id"] = self.customer_repository.to_object_id(update_payload["branch_id"])
        customer = await self.customer_repository.update(customer_id, update_payload)
        return CustomerRead(**self.serialize(customer))
