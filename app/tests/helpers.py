from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from bson import ObjectId
from fastapi.testclient import TestClient

from app.db.mongodb import get_database


def _resolve_mock_db(app):
    provider = app.dependency_overrides[get_database]
    return asyncio.run(provider())


def seed_subscription_plan(app, *, name: str = 'Core Plan') -> str:
    db = _resolve_mock_db(app)
    plan_id = ObjectId()
    asyncio.run(
        db['subscription_plan'].insert_one(
            {
                '_id': plan_id,
                'singleton_key': 'default_plan',
                'name': name,
                'monthly_price': 29.0,
                'annual_price': 290.0,
                'trial_days': 7,
                'features': ['Advanced AI insights'],
                'is_visible': True,
                'is_active': True,
                'is_best_plan': False,
                'created_at': datetime(2026, 3, 12, tzinfo=UTC),
                'updated_at': datetime(2026, 3, 12, tzinfo=UTC),
            }
        )
    )
    return str(plan_id)


def register_and_login(client: TestClient, owner_credentials: dict[str, str]) -> dict[str, str]:
    register_response = client.post('/api/v1/auth/restaurant/register', json=owner_credentials)
    register_code = register_response.json()['debug_verification_code']
    verify_registration = client.post(
        '/api/v1/auth/restaurant/verify-registration',
        json={'email': owner_credentials['email'], 'code': register_code},
    )
    assert verify_registration.status_code == 200

    login_response = client.post(
        '/api/v1/auth/restaurant/login',
        json={'email': owner_credentials['email'], 'password': owner_credentials['password']},
    )
    tokens = login_response.json()['tokens']
    return {'Authorization': f"Bearer {tokens['access_token']}"}


def select_subscription_plan(
    client: TestClient,
    headers: dict[str, str],
    *,
    billing_cycle: str = '1_month',
    start_trial: bool = True,
) -> None:
    response = client.post(
        '/api/v1/subscriptions/user/select',
        headers=headers,
        json={
            'billing_cycle': billing_cycle,
            'start_trial': start_trial,
        },
    )
    assert response.status_code == 200
