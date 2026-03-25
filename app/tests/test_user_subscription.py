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
    app, mock_db = _build_app_with_mock_db()
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
        me_response = client.get('/api/v1/auth/me', headers=headers)

    assert current_response.status_code == 200
    assert current_response.json()['selection_required'] is False
    assert current_response.json()['plan_name'] == 'Core Plan'
    assert current_response.json()['billing_cycle'] == '1_month'
    assert current_response.json()['status'] == 'trial'
    assert plans_response.status_code == 200
    assert plans_response.json()['selection_required'] is False
    assert len(plans_response.json()['plans']) == 1
    assert me_response.status_code == 200
    assert me_response.json()['subscription_selection_required'] is False
    subscriptions = asyncio.run(mock_db['user_subscriptions'].find().to_list(length=None))
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


def test_reselecting_subscription_closes_previous_current_record_and_keeps_history():
    app, mock_db = _build_app_with_mock_db()
    seed_subscription_plan(app, name='Core Plan')

    with TestClient(app) as client:
        headers = register_and_login(
            client,
            {
                'full_name': 'Repeat User',
                'email': 'repeat@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550005555',
            },
        )

        first = client.post(
            '/api/v1/subscriptions/user/select',
            headers=headers,
            json={'billing_cycle': '1_month', 'start_trial': True},
        )
        second = client.post(
            '/api/v1/subscriptions/user/select',
            headers=headers,
            json={'billing_cycle': '1_year', 'start_trial': False},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    subscriptions = asyncio.run(mock_db['user_subscriptions'].find().sort('created_at', 1).to_list(length=None))
    assert len(subscriptions) == 3
    assert subscriptions[0]['is_current'] is False
    assert subscriptions[0]['status'] == 'canceled'
    assert subscriptions[0]['ended_at'] is not None
    assert subscriptions[1]['is_current'] is False
    assert subscriptions[1]['status'] == 'canceled'
    assert subscriptions[1]['ended_at'] is not None
    assert subscriptions[2]['is_current'] is True
    assert subscriptions[2]['billing_cycle'] == '1_year'
    assert subscriptions[2]['status'] == 'active'
    current_count = asyncio.run(mock_db['user_subscriptions'].count_documents({'is_current': True}))
    assert current_count == 1


def test_subscription_middleware_allows_protected_routes_after_automatic_trial_assignment():
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

        plans_response = client.get('/api/v1/subscriptions/user/plans', headers=headers)
        onboarding_response = client.get('/api/v1/onboarding/profile', headers=headers)

    assert plans_response.status_code == 200
    assert plans_response.json()['selection_required'] is False
    assert len(plans_response.json()['plans']) == 1
    assert onboarding_response.status_code == 200
    assert onboarding_response.json() is None
