from __future__ import annotations

import asyncio
from fastapi.testclient import TestClient

from app.db.mongodb import get_database


def _resolve_mock_db(app):
    provider = app.dependency_overrides[get_database]
    return asyncio.run(provider())


def seed_subscription_plan(app, *, name: str = 'Core Plan') -> str:
    from datetime import UTC, datetime
    from bson import ObjectId

    db = _resolve_mock_db(app)
    plan_id = ObjectId()
    asyncio.run(
        db['subscription_plan'].insert_one(
            {
                '_id': plan_id,
                'singleton_key': 'default_plan',
                'name': name,
                'monthly_price': 30.0,
                'annual_price': 300.0,
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


def complete_onboarding_profile(
    client: TestClient,
    headers: dict[str, str],
    *,
    restaurant_name: str = 'The Italian Bistro',
    restaurant_type: str = 'Fine Dining',
    city_location: str = 'New York, NY',
    number_of_seats: int = 45,
    average_spend_per_customer: float = 25.0,
    main_business_goal: str = 'Increase revenue',
    biggest_problem: str = 'We struggle with slow weekday traffic and inconsistent table turnover.',
    improvement_focus: str = 'Improve staff scheduling and reduce wasted inventory.',
) -> None:
    response = client.post(
        '/api/v1/onboarding/profile',
        headers=headers,
        data={
            'restaurant_name': restaurant_name,
            'restaurant_type': restaurant_type,
            'city_location': city_location,
            'number_of_seats': str(number_of_seats),
            'average_spend_per_customer': str(average_spend_per_customer),
            'main_business_goal': main_business_goal,
            'biggest_problem': biggest_problem,
            'improvement_focus': improvement_focus,
        },
    )
    assert response.status_code == 200
