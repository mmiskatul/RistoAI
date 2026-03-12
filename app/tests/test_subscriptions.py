from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.core.enums import CouponDiscountType, CouponStatus, SubscriptionPlan, SubscriptionStatus, UserRole
from app.core.security import token_manager
from app.db.mongodb import get_database
from app.main import create_app



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
                    'subscription_plan_name': 'Pro Plan',
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
                    'subscription_plan_name': 'Growth Plan',
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
                    'subscription_plan_name': 'Starter Plan',
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
        mock_db['subscription_plans'].insert_many(
            [
                {
                    '_id': ObjectId(),
                    'name': 'Starter Plan',
                    'monthly_price': 19.0,
                    'annual_price': 190.0,
                    'trial_days': 7,
                    'features': ['Basic analytics'],
                    'is_visible': True,
                    'is_active': True,
                    'is_best_plan': False,
                    'created_at': now,
                    'updated_at': now,
                },
                {
                    '_id': ObjectId(),
                    'name': 'Growth Plan',
                    'monthly_price': 59.0,
                    'annual_price': 590.0,
                    'trial_days': 7,
                    'features': ['Performance reports'],
                    'is_visible': True,
                    'is_active': True,
                    'is_best_plan': False,
                    'created_at': now,
                    'updated_at': now,
                },
                {
                    '_id': ObjectId(),
                    'name': 'Pro Plan',
                    'monthly_price': 29.0,
                    'annual_price': 290.0,
                    'trial_days': 7,
                    'features': ['Advanced AI insights', 'Revenue analytics'],
                    'is_visible': True,
                    'is_active': True,
                    'is_best_plan': True,
                    'created_at': now,
                    'updated_at': now,
                },
            ]
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



def test_subscription_plan_management_returns_plans_and_coupons():
    app, mock_db = _build_app_with_mock_db()
    admin_id, _ = _seed_subscription_data(mock_db)

    with TestClient(app) as client:
        response = client.get('/api/v1/subscriptions/plans/management?page=1&page_size=10', headers=_admin_headers(admin_id))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload['plans']) == 3
    assert payload['coupons']['total'] == 2
    winter = next(item for item in payload['coupons']['items'] if item['code'] == 'WINTER10')
    assert winter['status'] == 'expired'



def test_create_update_and_pause_coupon_and_plan():
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
        plan_id = create_plan.json()['plan']['id']
        update_plan = client.patch(
            f'/api/v1/subscriptions/plans/{plan_id}',
            headers=_admin_headers(admin_id),
            json={'annual_price': 1590, 'trial_days': 21, 'is_visible': False},
        )
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

    assert create_plan.status_code == 201
    assert update_plan.status_code == 200
    assert update_plan.json()['plan']['annual_price'] == 1590.0
    assert update_plan.json()['plan']['is_visible'] is False
    assert create_coupon.status_code == 201
    assert pause_coupon.status_code == 200
    assert pause_coupon.json()['coupon']['status'] == 'paused'



def test_subscriptions_requires_super_admin():
    app, mock_db = _build_app_with_mock_db()
    admin_id, owner_id = _seed_subscription_data(mock_db)
    owner_token = token_manager.create_access_token(str(owner_id), UserRole.RESTAURANT_OWNER)

    with TestClient(app) as client:
        response = client.get('/api/v1/subscriptions/overview', headers={'Authorization': f'Bearer {owner_token}'})

    assert response.status_code == 403
    assert response.json()['error']['code'] == 'forbidden'
