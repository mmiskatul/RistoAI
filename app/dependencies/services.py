from __future__ import annotations

from fastapi import Depends

from app.db.mongodb import get_database
from app.repositories.ai_insight import AIInsightRepository
from app.repositories.analytics_snapshot import AnalyticsSnapshotRepository
from app.repositories.branch import BranchRepository
from app.repositories.customer import CustomerRepository
from app.repositories.menu import MenuCategoryRepository, MenuItemRepository
from app.repositories.notification import NotificationRepository
from app.repositories.order import OrderRepository
from app.repositories.restaurant import RestaurantRepository
from app.repositories.user import UserRepository
from app.services.ai_insight import AIInsightService
from app.services.analytics import AnalyticsService
from app.services.auth import AuthService
from app.services.branch import BranchService
from app.services.customer import CustomerService
from app.services.menu import MenuService
from app.services.notification import NotificationService
from app.services.order import OrderService
from app.services.restaurant import RestaurantService
from app.services.staff import StaffService
from app.services.strategies.demand_forecast import DemandForecastStrategy
from app.services.strategies.menu_optimization import MenuOptimizationStrategy
from app.services.strategies.recommendations import RecommendationsStrategy
from app.services.strategies.waste_reduction import WasteReductionStrategy


async def get_auth_service(db=Depends(get_database)) -> AuthService:
    return AuthService(UserRepository(db))


async def get_restaurant_service(db=Depends(get_database)) -> RestaurantService:
    return RestaurantService(RestaurantRepository(db), UserRepository(db))


async def get_branch_service(db=Depends(get_database)) -> BranchService:
    return BranchService(BranchRepository(db), RestaurantRepository(db), UserRepository(db))


async def get_menu_service(db=Depends(get_database)) -> MenuService:
    return MenuService(MenuCategoryRepository(db), MenuItemRepository(db), RestaurantRepository(db), BranchRepository(db))


async def get_customer_service(db=Depends(get_database)) -> CustomerService:
    return CustomerService(CustomerRepository(db))


async def get_order_service(db=Depends(get_database)) -> OrderService:
    return OrderService(
        OrderRepository(db),
        MenuItemRepository(db),
        CustomerRepository(db),
        BranchRepository(db),
        RestaurantRepository(db),
        NotificationRepository(db),
    )


async def get_analytics_service(db=Depends(get_database)) -> AnalyticsService:
    return AnalyticsService(
        OrderRepository(db),
        MenuItemRepository(db),
        CustomerRepository(db),
        AnalyticsSnapshotRepository(db),
    )


async def get_ai_insight_service(
    db=Depends(get_database),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> AIInsightService:
    strategies = {
        RecommendationsStrategy.insight_type: RecommendationsStrategy(),
        DemandForecastStrategy.insight_type: DemandForecastStrategy(),
        WasteReductionStrategy.insight_type: WasteReductionStrategy(),
        MenuOptimizationStrategy.insight_type: MenuOptimizationStrategy(),
    }
    return AIInsightService(AIInsightRepository(db), analytics_service, strategies)


async def get_notification_service(db=Depends(get_database)) -> NotificationService:
    return NotificationService(NotificationRepository(db))


async def get_staff_service(db=Depends(get_database)) -> StaffService:
    return StaffService(UserRepository(db))
