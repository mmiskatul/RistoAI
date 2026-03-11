from __future__ import annotations

from app.core.constants import ALLOWED_ORDER_TRANSITIONS
from app.core.enums import NotificationType, OrderStatus, UserRole
from app.core.exceptions import AuthorizationException, ValidationException
from app.repositories.branch import BranchRepository
from app.repositories.customer import CustomerRepository
from app.repositories.menu import MenuItemRepository
from app.repositories.notification import NotificationRepository
from app.repositories.order import OrderRepository
from app.repositories.restaurant import RestaurantRepository
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.order import OrderCreate, OrderRead, OrderReadItem, OrderStatusUpdate
from app.services.base import BaseService
from app.utils.datetime import utc_now
from app.utils.pagination import build_pagination_meta


class OrderService(BaseService):
    def __init__(
        self,
        order_repository: OrderRepository,
        menu_item_repository: MenuItemRepository,
        customer_repository: CustomerRepository,
        branch_repository: BranchRepository,
        restaurant_repository: RestaurantRepository,
        notification_repository: NotificationRepository,
    ) -> None:
        self.order_repository = order_repository
        self.menu_item_repository = menu_item_repository
        self.customer_repository = customer_repository
        self.branch_repository = branch_repository
        self.restaurant_repository = restaurant_repository
        self.notification_repository = notification_repository

    async def create_order(self, current_user: dict, payload: OrderCreate) -> OrderRead:
        self.ensure_restaurant_access(current_user, payload.restaurant_id)
        if current_user["role"] == UserRole.STAFF:
            self.ensure_branch_access(current_user, payload.branch_id)
        branch = await self.branch_repository.get_by_id(payload.branch_id)
        if str(branch["restaurant_id"]) != payload.restaurant_id:
            raise ValidationException("Branch does not belong to the restaurant")
        items_payload, subtotal = await self._build_order_items(payload.restaurant_id, payload.branch_id, payload.items)
        restaurant = await self.restaurant_repository.get_by_id(payload.restaurant_id)
        tax_rate = float(restaurant.get("settings", {}).get("tax_rate", 0.1))
        tax = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax - payload.discount, 2)
        if total < 0:
            raise ValidationException("Discount cannot exceed order total")
        order = await self.order_repository.create(
            {
                "restaurant_id": self.order_repository.to_object_id(payload.restaurant_id),
                "branch_id": self.order_repository.to_object_id(payload.branch_id),
                "customer_id": self.order_repository.to_object_id(payload.customer_id) if payload.customer_id else None,
                "items": items_payload,
                "subtotal": subtotal,
                "tax": tax,
                "discount": payload.discount,
                "total": total,
                "payment_status": payload.payment_status,
                "order_status": OrderStatus.PENDING,
            }
        )
        if payload.customer_id:
            await self._sync_customer_metrics(payload.customer_id, total)
        await self.notification_repository.create(
            {
                "user_id": current_user["_id"],
                "restaurant_id": self.notification_repository.to_object_id(payload.restaurant_id),
                "title": "Order Created",
                "message": f"Order {order['_id']} was created successfully.",
                "type": NotificationType.ORDER,
                "is_read": False,
                "metadata": {"order_id": order["_id"]},
                "read_at": None,
            }
        )
        return self._to_order_read(order)

    async def list_orders(
        self,
        current_user: dict,
        restaurant_id: str,
        page: int,
        page_size: int,
        branch_id: str | None = None,
    ) -> PaginatedResponse[OrderRead]:
        self.ensure_restaurant_access(current_user, restaurant_id)
        if current_user["role"] == UserRole.STAFF and branch_id:
            self.ensure_branch_access(current_user, branch_id)
        orders, total = await self.order_repository.list_by_restaurant(restaurant_id, page, page_size, branch_id)
        items = [self._to_order_read(order) for order in orders]
        return PaginatedResponse[OrderRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=items)

    async def get_order(self, current_user: dict, order_id: str) -> OrderRead:
        order = await self.order_repository.get_by_id(order_id)
        self.ensure_restaurant_access(current_user, str(order["restaurant_id"]))
        return self._to_order_read(order)

    async def update_order_status(self, current_user: dict, order_id: str, payload: OrderStatusUpdate) -> OrderRead:
        order = await self.order_repository.get_by_id(order_id)
        self.ensure_restaurant_access(current_user, str(order["restaurant_id"]))
        current_status = OrderStatus(order["order_status"])
        if payload.order_status not in ALLOWED_ORDER_TRANSITIONS[current_status]:
            raise ValidationException("Invalid order status transition")
        order = await self.order_repository.update(order_id, {"order_status": payload.order_status})
        await self.notification_repository.create(
            {
                "user_id": current_user["_id"],
                "restaurant_id": order["restaurant_id"],
                "title": "Order Status Updated",
                "message": f"Order {order['_id']} is now {payload.order_status}.",
                "type": NotificationType.ORDER,
                "is_read": False,
                "metadata": {"order_id": order["_id"], "order_status": payload.order_status},
                "read_at": None,
            }
        )
        return self._to_order_read(order)

    async def cancel_order(self, current_user: dict, order_id: str) -> OrderRead:
        return await self.update_order_status(current_user, order_id, OrderStatusUpdate(order_status=OrderStatus.CANCELLED))

    async def _build_order_items(self, restaurant_id: str, branch_id: str, items: list) -> tuple[list[dict], float]:
        menu_items = await self.menu_item_repository.get_by_ids([item.menu_item_id for item in items])
        menu_lookup = {str(item["_id"]): item for item in menu_items}
        if len(menu_lookup) != len(items):
            raise ValidationException("One or more menu items were not found")
        order_items: list[dict] = []
        subtotal = 0.0
        for order_item in items:
            menu_item = menu_lookup[order_item.menu_item_id]
            if str(menu_item["restaurant_id"]) != restaurant_id:
                raise ValidationException("Menu item does not belong to the restaurant")
            if not menu_item["availability"]:
                raise ValidationException(f"Menu item '{menu_item['name']}' is unavailable")
            if menu_item.get("branch_id") and str(menu_item["branch_id"]) != branch_id:
                raise ValidationException(f"Menu item '{menu_item['name']}' is not available in this branch")
            line_total = round(menu_item["price"] * order_item.quantity, 2)
            subtotal += line_total
            order_items.append(
                {
                    "menu_item_id": menu_item["_id"],
                    "name": menu_item["name"],
                    "quantity": order_item.quantity,
                    "unit_price": menu_item["price"],
                    "line_total": line_total,
                    "notes": order_item.notes,
                }
            )
        return order_items, round(subtotal, 2)

    async def _sync_customer_metrics(self, customer_id: str, order_total: float) -> None:
        customer = await self.customer_repository.get_by_id(customer_id)
        await self.customer_repository.update(
            customer_id,
            {
                "total_orders": customer.get("total_orders", 0) + 1,
                "total_spent": round(customer.get("total_spent", 0.0) + order_total, 2),
                "last_order_at": utc_now().isoformat(),
            },
        )

    def _to_order_read(self, order: dict) -> OrderRead:
        serialized = self.serialize(order)
        serialized["items"] = [OrderReadItem(**self.serialize_value(item)) for item in order.get("items", [])]
        return OrderRead(**serialized)
