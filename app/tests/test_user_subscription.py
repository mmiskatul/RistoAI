from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.db.mongodb import get_database
from app.main import create_app
from app.tests.helpers import register_and_login, seed_subscription_plan, select_subscription_plan


def _build_app_with_mock_db():
    app = create_app(testing=True)
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client['ristoai_test']

    async def override_get_database():
        return mock_db

    app.dependency_overrides[get_database] = override_get_database
    return app, mock_db


def _seed_coupon(mock_db, *, code: str = 'SAVE20', usage_limit: int = 100, usage_count: int = 0):
    asyncio.run(
        mock_db['coupons'].insert_one(
            {
                '_id': ObjectId(),
                'code': code,
                'discount_type': 'percentage',
                'value': 20,
                'usage_limit': usage_limit,
                'usage_count': usage_count,
                'expires_at': datetime.now(UTC) + timedelta(days=30),
                'status': 'active',
                'created_at': datetime(2026, 3, 12, tzinfo=UTC),
                'updated_at': datetime(2026, 3, 12, tzinfo=UTC),
            }
        )
    )


def test_user_subscription_selection_flow_for_first_login():
    app, _ = _build_app_with_mock_db()
    seed_subscription_plan(app, name='Core Plan')

    with TestClient(app) as client:
        headers = register_and_login(
            client,
            {
                'full_name': 'Owner User',
                'email': 'owner@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550001111',
            },
        )

        current_response = client.get('/api/v1/subscriptions/user/current', headers=headers)
        plans_response = client.get('/api/v1/subscriptions/user/plans', headers=headers)

        assert current_response.status_code == 200
        assert current_response.json()['selection_required'] is True
        assert plans_response.status_code == 200
        assert plans_response.json()['selection_required'] is True
        assert len(plans_response.json()['plans']) == 1

        select_response = client.post(
            '/api/v1/subscriptions/user/select',
            headers=headers,
            json={
                'billing_cycle': '1_month',
                'start_trial': True,
            },
        )
        me_response = client.get('/api/v1/auth/me', headers=headers)

    assert select_response.status_code == 200
    assert select_response.json()['subscription']['selection_required'] is False
    assert select_response.json()['subscription']['plan_name'] == 'Core Plan'
    assert select_response.json()['subscription']['billing_cycle'] == '1_month'
    assert select_response.json()['subscription']['status'] == 'trial'
    assert me_response.status_code == 200
    assert me_response.json()['subscription_selection_required'] is False
    subscriptions = asyncio.run(_['user_subscriptions'].find().to_list(length=None))
    assert len(subscriptions) == 1
    assert str(subscriptions[0]['user_id']) == me_response.json()['id']
    assert subscriptions[0]['plan_name'] == 'Core Plan'
    assert subscriptions[0]['billing_cycle'] == '1_month'
    assert subscriptions[0]['status'] == 'trial'


def test_user_discount_preview_returns_discount_amounts():
    app, mock_db = _build_app_with_mock_db()
    seed_subscription_plan(app, name='Core Plan')
    _seed_coupon(mock_db)

    with TestClient(app) as client:
        headers = register_and_login(
            client,
            {
                'full_name': 'Preview User',
                'email': 'preview@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550003333',
            },
        )
        response = client.post(
            '/api/v1/subscriptions/user/discount-preview',
            headers=headers,
            json={'billing_cycle': '1_month', 'coupon_code': 'SAVE20'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['coupon_code'] == 'SAVE20'
    assert payload['original_amount'] == 29.0
    assert payload['discount_amount'] == 5.8
    assert payload['final_amount'] == 23.2


def test_user_discount_preview_rejects_invalid_coupon():
    app, _ = _build_app_with_mock_db()
    seed_subscription_plan(app, name='Core Plan')

    with TestClient(app) as client:
        headers = register_and_login(
            client,
            {
                'full_name': 'Invalid Coupon User',
                'email': 'invalid-coupon@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550004444',
            },
        )
        response = client.post(
            '/api/v1/subscriptions/user/discount-preview',
            headers=headers,
            json={'billing_cycle': '1_month', 'coupon_code': 'NOPE'},
        )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'
    assert response.json()['error']['message'] == 'Coupon is not valid'


def test_subscription_middleware_blocks_protected_routes_until_plan_selected():
    app, _ = _build_app_with_mock_db()
    seed_subscription_plan(app)

    with TestClient(app) as client:
        headers = register_and_login(
            client,
            {
                'full_name': 'Protected User',
                'email': 'protected@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550002222',
            },
        )

        blocked_response = client.get('/api/v1/onboarding/profile', headers=headers)
        allowed_subscription_response = client.get('/api/v1/subscriptions/user/plans', headers=headers)

        select_subscription_plan(client, headers)
        unblocked_response = client.get('/api/v1/onboarding/profile', headers=headers)

    assert blocked_response.status_code == 403
    assert blocked_response.json()['error']['code'] == 'subscription_required'
    assert blocked_response.json()['error']['details']['selection_required'] is True
    assert allowed_subscription_response.status_code == 200
    assert len(allowed_subscription_response.json()['plans']) == 1
    assert unblocked_response.status_code == 200
    assert unblocked_response.json() is None
