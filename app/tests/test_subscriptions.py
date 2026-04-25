from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.config.settings import Settings
from app.core.enums import CouponDiscountType, CouponStatus, SubscriptionPlan, SubscriptionStatus, UserRole
from app.core.security import token_manager
from app.db.mongodb import get_database
from app.dependencies.services import get_subscription_service
from app.main import create_app
from app.repositories.coupon import CouponRepository
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.user import UserRepository
from app.repositories.user_subscription import UserSubscriptionRepository
from app.services.bootstrap import BootstrapService
from app.services.subscription import SubscriptionService


def _build_app_with_mock_db():
    app = create_app(testing=True)
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client['ristoai_test']

    async def override_get_database():
        return mock_db

    app.dependency_overrides[get_database] = override_get_database
    return app, mock_db


def _admin_headers(admin_id: ObjectId) -> dict[str, str]:
    token = token_manager.create_access_token(str(admin_id), UserRole.SUPER_ADMIN)
    return {'Authorization': f'Bearer {token}'}


def _seed_subscription_data(mock_db):
    admin_id = ObjectId()
    owner_id = ObjectId()
    trial_id = ObjectId()
    canceled_id = ObjectId()
    now = datetime(2026, 6, 15, tzinfo=UTC)
    asyncio.run(
        mock_db['users'].insert_many(
            [
                {
                    '_id': admin_id,
                    'email': 'admin@example.com',
                    'full_name': 'Admin User',
                    'phone': '+10000000000',
                    'hashed_password': 'x',
                    'role': UserRole.SUPER_ADMIN,
                    'is_active': True,
                    'email_verified': True,
                    'created_at': now,
                    'updated_at': now,
                },
                {
                    '_id': owner_id,
                    'email': 'john@example.com',
                    'full_name': 'John Doe',
                    'phone': '+20000000000',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': True,
                    'email_verified': True,
                    'restaurant_name': 'The Golden Grill',
                    'location': 'Milan, Italy',
                    'subscription_plan_name': 'Core Plan',
                    'subscription_plan': SubscriptionPlan.ONE_YEAR,
                    'subscription_status': SubscriptionStatus.ACTIVE,
                    'subscription_started_at': datetime(2026, 1, 12, tzinfo=UTC),
                    'subscription_expires_at': datetime(2027, 1, 12, tzinfo=UTC),
                    'created_at': datetime(2026, 1, 12, tzinfo=UTC),
                    'updated_at': datetime(2026, 1, 12, tzinfo=UTC),
                },
                {
                    '_id': trial_id,
                    'email': 'sarah@example.com',
                    'full_name': 'Sarah Miller',
                    'phone': '+30000000000',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': True,
                    'email_verified': True,
                    'restaurant_name': 'Miller Bistro',
                    'location': 'Paris, France',
                    'subscription_plan_name': 'Core Plan',
                    'subscription_plan': SubscriptionPlan.ONE_MONTH,
                    'subscription_status': SubscriptionStatus.TRIAL,
                    'subscription_started_at': datetime(2026, 5, 28, tzinfo=UTC),
                    'subscription_expires_at': datetime(2026, 6, 28, tzinfo=UTC),
                    'created_at': datetime(2026, 5, 28, tzinfo=UTC),
                    'updated_at': datetime(2026, 5, 28, tzinfo=UTC),
                },
                {
                    '_id': canceled_id,
                    'email': 'tom@example.com',
                    'full_name': 'Tom Collins',
                    'phone': '+40000000000',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': False,
                    'email_verified': True,
                    'restaurant_name': 'Corner Cafe',
                    'location': 'Berlin, Germany',
                    'subscription_plan_name': 'Core Plan',
                    'subscription_plan': SubscriptionPlan.ONE_MONTH,
                    'subscription_status': SubscriptionStatus.CANCELED,
                    'subscription_started_at': datetime(2026, 2, 5, tzinfo=UTC),
                    'subscription_expires_at': datetime(2026, 3, 5, tzinfo=UTC),
                    'created_at': datetime(2026, 2, 5, tzinfo=UTC),
                    'updated_at': datetime(2026, 2, 5, tzinfo=UTC),
                },
            ]
        )
    )

    asyncio.run(
        mock_db['subscription_plan'].insert_one(
            {
                '_id': ObjectId(),
                'singleton_key': 'default_plan',
                'name': 'Core Plan',
                'monthly_price': 29.0,
                'annual_price': 290.0,
                'trial_days': 7,
                'features': ['Advanced AI insights', 'Revenue analytics'],
                'is_visible': True,
                'is_active': True,
                'is_best_plan': False,
                'created_at': now,
                'updated_at': now,
            }
        )
    )

    asyncio.run(
        mock_db['coupons'].insert_many(
            [
                {
                    '_id': ObjectId(),
                    'code': 'SAVE20',
                    'discount_type': CouponDiscountType.PERCENTAGE,
                    'value': 20,
                    'usage_limit': 100,
                    'usage_count': 15,
                    'expires_at': datetime.now(UTC) + timedelta(days=30),
                    'status': CouponStatus.ACTIVE,
                    'created_at': now,
                    'updated_at': now,
                },
                {
                    '_id': ObjectId(),
                    'code': 'WINTER10',
                    'discount_type': CouponDiscountType.PERCENTAGE,
                    'value': 10,
                    'usage_limit': 50,
                    'usage_count': 50,
                    'expires_at': datetime.now(UTC) - timedelta(days=1),
                    'status': CouponStatus.ACTIVE,
                    'created_at': now,
                    'updated_at': now,
                },
            ]
        )
    )
    return admin_id, owner_id


def test_bootstrap_seeds_default_subscription_plan_once():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client['ristoai_test']
    bootstrap_service = BootstrapService(UserRepository(mock_db), SubscriptionPlanRepository(mock_db))
    settings = Settings(
        SUBSCRIPTION_PLAN_NAME='Env Plan',
        SUBSCRIPTION_PLAN_MONTHLY_PRICE=45.0,
        SUBSCRIPTION_PLAN_ANNUAL_PRICE=500.0,
        SUBSCRIPTION_PLAN_TRIAL_DAYS=10,
        SUBSCRIPTION_PLAN_FEATURES=['Priority support'],
        SUBSCRIPTION_PLAN_IS_VISIBLE=True,
        SUBSCRIPTION_PLAN_IS_ACTIVE=True,
        SUBSCRIPTION_PLAN_IS_BEST=False,
    )

    asyncio.run(bootstrap_service.ensure_default_subscription_plan(settings))
    asyncio.run(bootstrap_service.ensure_default_subscription_plan(settings))

    plans = asyncio.run(mock_db['subscription_plan'].find().to_list(length=None))

    assert len(plans) == 1
    assert plans[0]['name'] == 'Env Plan'
    assert plans[0]['monthly_price'] == 45.0
    assert plans[0]['annual_price'] == 500.0
    assert plans[0]['singleton_key'] == 'default_plan'


def test_subscription_overview_returns_page_data():
    app, mock_db = _build_app_with_mock_db()
    admin_id, _ = _seed_subscription_data(mock_db)

    with TestClient(app) as client:
        response = client.get('/api/v1/subscriptions/overview?page=1&page_size=10&months=6', headers=_admin_headers(admin_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload['summary'] == {
        'active_subscriptions': 1,
        'trial_users': 1,
        'monthly_revenue_mrr': 24.17,
        'annual_revenue': 290.0,
    }
    assert payload['total'] == 3
    assert len(payload['revenue_chart']) == 6
    assert payload['items'][0]['plan_name'] is not None
    assert payload['items'][0]['billing_cycle'] is not None
    assert payload['items'][0]['status'] is not None
    assert payload['items'][0]['start_date'] is not None


def test_subscription_plan_management_returns_plans_and_coupons():
    app, mock_db = _build_app_with_mock_db()
    admin_id, _ = _seed_subscription_data(mock_db)

    with TestClient(app) as client:
        response = client.get('/api/v1/subscriptions/plans/management?page=1&page_size=10', headers=_admin_headers(admin_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload['plan']['name'] == 'Core Plan'
    assert payload['plan']['monthly_price'] == 29.0
    assert payload['plan']['annual_price'] == 290.0
    assert payload['plan']['trial_days'] == 7
    assert payload['plan']['is_visible'] is True
    assert payload['active_plan']['name'] == 'Core Plan'
    assert payload['active_plan']['visibility_enabled'] is True
    assert len(payload['plans']) == 1
    assert payload['plans'][0]['name'] == 'Core Plan'
    assert payload['coupons']['total'] == 2
    winter = next(item for item in payload['coupons']['items'] if item['code'] == 'WINTER10')
    assert winter['status'] == 'expired'


def test_create_and_update_subscription_plan_with_dynamic_routes():
    app, mock_db = _build_app_with_mock_db()
    admin_id, _ = _seed_subscription_data(mock_db)

    with TestClient(app) as client:
        create_plan = client.post(
            '/api/v1/subscriptions/plans',
            headers=_admin_headers(admin_id),
            json={
                'name': 'Enterprise AI',
                'monthly_price': 149,
                'annual_price': 1490,
                'trial_days': 14,
                'features': ['Enterprise reports'],
                'is_visible': True,
                'is_active': True,
                'is_best_plan': False,
            },
        )
        assert create_plan.status_code == 201
        created_plan_id = create_plan.json()['plan']['id']

        get_plan = client.get(
            f'/api/v1/subscriptions/plans/{created_plan_id}',
            headers=_admin_headers(admin_id),
        )
        update_plan = client.patch(
            f'/api/v1/subscriptions/plans/{created_plan_id}',
            headers=_admin_headers(admin_id),
            json={'annual_price': 1590, 'trial_days': 21, 'is_visible': False},
        )
        list_plans = client.get(
            '/api/v1/subscriptions/plans',
            headers=_admin_headers(admin_id),
        )

    assert get_plan.status_code == 200
    assert get_plan.json()['name'] == 'Enterprise AI'
    assert update_plan.status_code == 200
    assert update_plan.json()['plan']['annual_price'] == 1590.0
    assert update_plan.json()['plan']['is_visible'] is False
    assert list_plans.status_code == 200
    assert len(list_plans.json()) == 2
    assert any(plan['name'] == 'Enterprise AI' for plan in list_plans.json())


def test_create_and_pause_coupon():
    app, mock_db = _build_app_with_mock_db()
    admin_id, _ = _seed_subscription_data(mock_db)

    with TestClient(app) as client:
        create_coupon = client.post(
            '/api/v1/subscriptions/coupons',
            headers=_admin_headers(admin_id),
            json={
                'code': 'LAUNCH50',
                'discount_type': 'fixed',
                'value': 50,
                'usage_limit': 200,
                'expires_at': '2026-12-31T00:00:00Z',
                'status': 'active',
            },
        )
        coupon_id = create_coupon.json()['coupon']['id']
        pause_coupon = client.post(f'/api/v1/subscriptions/coupons/{coupon_id}/pause', headers=_admin_headers(admin_id))

    assert create_coupon.status_code == 201
    assert pause_coupon.status_code == 200
    assert pause_coupon.json()['coupon']['status'] == 'paused'


def test_subscriptions_requires_super_admin():
    app, mock_db = _build_app_with_mock_db()
    _, owner_id = _seed_subscription_data(mock_db)
    owner_token = token_manager.create_access_token(str(owner_id), UserRole.RESTAURANT_OWNER)

    with TestClient(app) as client:
        response = client.get('/api/v1/subscriptions/overview', headers={'Authorization': f'Bearer {owner_token}'})

    assert response.status_code == 403
    assert response.json()['error']['code'] == 'forbidden'



class _FakeStripeBillingService:
    def __init__(self) -> None:
        self.settings = type('Settings', (), {'stripe_publishable_key': 'pk_test_123', 'stripe_price_id_monthly': 'price_month', 'stripe_price_id_yearly': 'price_year'})()

    async def create_customer(self, *, email: str, name: str, metadata: dict[str, str]):
        return {'id': 'cus_test_123', 'email': email, 'name': name, 'metadata': metadata}

    async def create_checkout_session(self, *, customer_id: str, billing_cycle, metadata: dict[str, str], trial_days: int = 0):
        return {'id': 'cs_test_123', 'url': 'https://checkout.stripe.test/session', 'customer': customer_id, 'metadata': metadata, 'trial_days': trial_days}

    async def create_customer_portal_session(self, *, customer_id: str):
        return {'url': 'https://billing.stripe.test/portal', 'customer': customer_id}

    def construct_event(self, payload: bytes, sig_header: str | None):
        return {'type': 'checkout.session.completed', 'data': {'object': {'subscription': 'sub_test_123', 'customer': 'cus_test_123', 'metadata': {'user_id': self.user_id}}}}

    async def retrieve_subscription(self, subscription_id: str):
        return {
            'id': subscription_id,
            'customer': 'cus_test_123',
            'status': 'active',
            'metadata': {'user_id': self.user_id, 'plan_name': 'Core Plan'},
            'current_period_start': 1772486400,
            'current_period_end': 1775164800,
            'items': {'data': [{'price': {'id': 'price_month'}}]},
        }


def test_user_can_create_stripe_checkout_session_and_customer_portal():
    app, mock_db = _build_app_with_mock_db()
    _, owner_id = _seed_subscription_data(mock_db)
    owner_token = token_manager.create_access_token(str(owner_id), UserRole.RESTAURANT_OWNER)
    fake_stripe = _FakeStripeBillingService()
    fake_stripe.user_id = str(owner_id)

    async def override_subscription_service():
        return SubscriptionService(
            UserRepository(mock_db),
            SubscriptionPlanRepository(mock_db),
            CouponRepository(mock_db),
            UserSubscriptionRepository(mock_db),
            fake_stripe,
        )

    app.dependency_overrides[get_subscription_service] = override_subscription_service

    with TestClient(app) as client:
        checkout_response = client.post(
            '/api/v1/subscriptions/user/checkout-session',
            headers={'Authorization': f'Bearer {owner_token}'},
            json={'billing_cycle': '1_month', 'start_trial': False},
        )
        portal_response = client.post(
            '/api/v1/subscriptions/user/customer-portal',
            headers={'Authorization': f'Bearer {owner_token}'},
        )

    assert checkout_response.status_code == 200
    assert checkout_response.json() == {
        'session_id': 'cs_test_123',
        'checkout_url': 'https://checkout.stripe.test/session',
        'publishable_key': 'pk_test_123',
    }
    assert portal_response.status_code == 200
    assert portal_response.json() == {'portal_url': 'https://billing.stripe.test/portal'}

    user = asyncio.run(mock_db['users'].find_one({'_id': owner_id}))
    assert user['stripe_customer_id'] == 'cus_test_123'


def test_stripe_webhook_syncs_subscription_into_database():
    app, mock_db = _build_app_with_mock_db()
    _, owner_id = _seed_subscription_data(mock_db)
    fake_stripe = _FakeStripeBillingService()
    fake_stripe.user_id = str(owner_id)

    async def override_subscription_service():
        return SubscriptionService(
            UserRepository(mock_db),
            SubscriptionPlanRepository(mock_db),
            CouponRepository(mock_db),
            UserSubscriptionRepository(mock_db),
            fake_stripe,
        )

    app.dependency_overrides[get_subscription_service] = override_subscription_service

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/subscriptions/webhook',
            headers={'Stripe-Signature': 'sig_test'},
            content=b'{}',
        )

    assert response.status_code == 200
    assert response.json() == {'received': True, 'event_type': 'checkout.session.completed'}

    user = asyncio.run(mock_db['users'].find_one({'_id': owner_id}))
    assert user['stripe_customer_id'] == 'cus_test_123'
    assert user['stripe_subscription_id'] == 'sub_test_123'
    assert user['stripe_price_id'] == 'price_month'
    assert user['subscription_status'] == 'active'

    current_subscription = asyncio.run(mock_db['user_subscriptions'].find_one({'user_id': owner_id, 'stripe_subscription_id': 'sub_test_123'}))
    assert current_subscription is not None
    assert current_subscription['payment_provider'] == 'stripe'
    assert current_subscription['status'] == 'active'
