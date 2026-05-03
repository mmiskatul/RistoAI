from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.core.enums import SubscriptionPlan, SubscriptionStatus, UserRole
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



def test_dashboard_overview_returns_all_aggregated_data_for_admin():
    app, mock_db = _build_app_with_mock_db()

    admin_id = ObjectId()
    owner_id = ObjectId()
    manager_id = ObjectId()
    staff_id = ObjectId()

    asyncio.run(
        mock_db['users'].insert_many(
            [
                {
                    '_id': admin_id,
                    'email': 'admin@example.com',
                    'full_name': 'Admin User',
                    'hashed_password': 'x',
                    'role': UserRole.SUPER_ADMIN,
                    'is_active': True,
                    'email_verified': True,
                    'created_at': datetime(2026, 1, 10, tzinfo=UTC),
                    'updated_at': datetime(2026, 1, 10, tzinfo=UTC),
                },
                {
                    '_id': owner_id,
                    'email': 'owner@example.com',
                    'full_name': 'Owner User',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': True,
                    'email_verified': True,
                    'subscription_status': 'active',
                    'subscription_plan': '1_month',
                    'created_at': datetime(2026, 2, 5, tzinfo=UTC),
                    'updated_at': datetime(2026, 2, 5, tzinfo=UTC),
                },
                {
                    '_id': manager_id,
                    'email': 'manager@example.com',
                    'full_name': 'Manager User',
                    'hashed_password': 'x',
                    'role': UserRole.MANAGER,
                    'is_active': True,
                    'email_verified': False,
                    'subscription_status': 'trial',
                    'subscription_plan': '1_month',
                    'created_at': datetime(2026, 2, 18, tzinfo=UTC),
                    'updated_at': datetime(2026, 2, 18, tzinfo=UTC),
                },
                {
                    '_id': staff_id,
                    'email': 'staff@example.com',
                    'full_name': 'Staff User',
                    'hashed_password': 'x',
                    'role': UserRole.STAFF,
                    'is_active': False,
                    'email_verified': False,
                    'created_at': datetime(2026, 3, 1, tzinfo=UTC),
                    'updated_at': datetime(2026, 3, 1, tzinfo=UTC),
                },
            ]
        )
    )

    asyncio.run(
        mock_db['onboarding_profiles'].insert_many(
            [
                {
                    '_id': ObjectId(),
                    'user_id': str(owner_id),
                    'restaurant_name': 'Alpha',
                    'restaurant_type': 'Cafe',
                    'city_location': 'Dhaka',
                    'number_of_seats': 50,
                    'average_spend_per_customer': 20,
                    'main_business_goal': 'Growth',
                    'biggest_problem': 'Need more customers every week',
                    'improvement_focus': 'Marketing and retention',
                    'onboarding_completed': True,
                    'created_at': datetime(2026, 2, 20, tzinfo=UTC),
                    'updated_at': datetime(2026, 2, 20, tzinfo=UTC),
                },
                {
                    '_id': ObjectId(),
                    'user_id': str(manager_id),
                    'restaurant_name': 'Beta',
                    'restaurant_type': 'Bistro',
                    'city_location': 'Dhaka',
                    'number_of_seats': 80,
                    'average_spend_per_customer': 35,
                    'main_business_goal': 'Efficiency',
                    'biggest_problem': 'Operations are inconsistent across shifts',
                    'improvement_focus': 'Staff process improvements',
                    'onboarding_completed': True,
                    'created_at': datetime(2026, 3, 5, tzinfo=UTC),
                    'updated_at': datetime(2026, 3, 5, tzinfo=UTC),
                },
            ]
        )
    )

    future_time = datetime.now(UTC) + timedelta(minutes=30)
    past_time = datetime.now(UTC) - timedelta(minutes=30)
    asyncio.run(
        mock_db['auth_codes'].insert_many(
            [
                {
                    '_id': ObjectId(),
                    'user_id': owner_id,
                    'email': 'owner@example.com',
                    'purpose': 'restaurant_registration',
                    'code_hash': 'hash-1',
                    'expires_at': future_time,
                    'consumed_at': None,
                    'created_at': datetime(2026, 2, 6, tzinfo=UTC),
                    'updated_at': datetime(2026, 2, 6, tzinfo=UTC),
                },
                {
                    '_id': ObjectId(),
                    'user_id': manager_id,
                    'email': 'manager@example.com',
                    'purpose': 'restaurant_registration',
                    'code_hash': 'hash-2',
                    'expires_at': future_time,
                    'consumed_at': datetime(2026, 2, 6, tzinfo=UTC),
                    'created_at': datetime(2026, 2, 6, tzinfo=UTC),
                    'updated_at': datetime(2026, 2, 6, tzinfo=UTC),
                },
                {
                    '_id': ObjectId(),
                    'user_id': staff_id,
                    'email': 'staff@example.com',
                    'purpose': 'restaurant_registration',
                    'code_hash': 'hash-3',
                    'expires_at': past_time,
                    'consumed_at': None,
                    'created_at': datetime(2026, 3, 2, tzinfo=UTC),
                    'updated_at': datetime(2026, 3, 2, tzinfo=UTC),
                },
            ]
        )
    )

    access_token = token_manager.create_access_token(str(admin_id), UserRole.SUPER_ADMIN)

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/dashboard/overview?year=2026',
            headers={'Authorization': f'Bearer {access_token}'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['meta'] == {'year': 2026}
    assert payload['summary'] == {
        'total_users': 4,
        'active_users': 3,
        'verified_users': 2,
        'completed_onboarding': 2,
        'pending_verifications': 1,
        'active_subscriptions': 1,
        'trial_users': 1,
        'monthly_revenue': 30.0,
        'admins': 1,
        'restaurant_owners': 1,
        'managers': 1,
        'staff': 1,
    }
    assert payload['charts']['monthly_new_users'][0] == {'month': 1, 'label': 'Jan', 'value': 1}
    assert payload['charts']['monthly_new_users'][1] == {'month': 2, 'label': 'Feb', 'value': 2}
    assert payload['charts']['monthly_new_users'][2] == {'month': 3, 'label': 'Mar', 'value': 1}
    assert payload['charts']['monthly_completed_onboarding'][1] == {'month': 2, 'label': 'Feb', 'value': 1}
    assert payload['charts']['monthly_completed_onboarding'][2] == {'month': 3, 'label': 'Mar', 'value': 1}
    assert payload['charts']['monthly_revenue'][0] == {'key': '2026-01', 'label': 'JAN', 'value': 0.0}
    assert payload['charts']['monthly_revenue'][1] == {'key': '2026-02', 'label': 'FEB', 'value': 30.0}
    assert payload['charts']['monthly_revenue'][2] == {'key': '2026-03', 'label': 'MAR', 'value': 30.0}
    assert len(payload['charts']['weekly_revenue']) == 8
    assert payload['charts']['weekly_revenue'][0]['key'].startswith('2026-W')
    assert payload['charts']['users_by_role'] == [
        {'role': 'super_admin', 'label': 'Admins', 'value': 1},
        {'role': 'restaurant_owner', 'label': 'Restaurant Owners', 'value': 1},
        {'role': 'manager', 'label': 'Managers', 'value': 1},
        {'role': 'staff', 'label': 'Staff', 'value': 1},
    ]
    assert payload['charts']['subscription_breakdown'] == [
        {'label': 'Active Subscriptions', 'value': 1, 'percentage': 50.0, 'color_key': 'navy'},
        {'label': 'Trial Users', 'value': 1, 'percentage': 50.0, 'color_key': 'lavender'},
    ]



def test_dashboard_user_metrics_returns_counts_for_admin():
    app, mock_db = _build_app_with_mock_db()

    admin_id = ObjectId()
    asyncio.run(
        mock_db['users'].insert_one(
            {
                '_id': admin_id,
                'email': 'admin@example.com',
                'full_name': 'Admin User',
                'hashed_password': 'x',
                'role': UserRole.SUPER_ADMIN,
                'is_active': True,
                'email_verified': True,
                'created_at': datetime(2026, 1, 10, tzinfo=UTC),
                'updated_at': datetime(2026, 1, 10, tzinfo=UTC),
            }
        )
    )

    access_token = token_manager.create_access_token(str(admin_id), UserRole.SUPER_ADMIN)

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/dashboard/users/metrics',
            headers={'Authorization': f'Bearer {access_token}'},
        )

    assert response.status_code == 200
    assert response.json() == {
        'total_users': 1,
        'active_users': 1,
        'verified_users': 1,
        'admins': 1,
        'restaurant_owners': 0,
        'managers': 0,
        'staff': 0,
    }


def test_dashboard_analytics_returns_platform_metrics_for_admin():
    app, mock_db = _build_app_with_mock_db()

    now = datetime.now(UTC)
    admin_id = ObjectId()
    monthly_owner_id = ObjectId()
    yearly_owner_id = ObjectId()
    trial_owner_id = ObjectId()

    asyncio.run(
        mock_db['users'].insert_many(
            [
                {
                    '_id': admin_id,
                    'email': 'admin@example.com',
                    'full_name': 'Admin User',
                    'hashed_password': 'x',
                    'role': UserRole.SUPER_ADMIN,
                    'is_active': True,
                    'email_verified': True,
                    'created_at': now - timedelta(days=30),
                    'updated_at': now - timedelta(days=30),
                },
                {
                    '_id': monthly_owner_id,
                    'email': 'monthly@example.com',
                    'full_name': 'Monthly Owner',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': True,
                    'email_verified': True,
                    'subscription_status': SubscriptionStatus.ACTIVE,
                    'subscription_plan': SubscriptionPlan.ONE_MONTH,
                    'created_at': now - timedelta(days=3),
                    'updated_at': now - timedelta(days=3),
                },
                {
                    '_id': yearly_owner_id,
                    'email': 'yearly@example.com',
                    'full_name': 'Yearly Owner',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': True,
                    'email_verified': True,
                    'subscription_status': SubscriptionStatus.ACTIVE,
                    'subscription_plan': SubscriptionPlan.ONE_YEAR,
                    'created_at': now - timedelta(days=2),
                    'updated_at': now - timedelta(days=2),
                },
                {
                    '_id': trial_owner_id,
                    'email': 'trial@example.com',
                    'full_name': 'Trial Owner',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': True,
                    'email_verified': True,
                    'subscription_status': SubscriptionStatus.TRIAL,
                    'subscription_plan': SubscriptionPlan.ONE_MONTH,
                    'created_at': now - timedelta(days=1),
                    'updated_at': now - timedelta(days=1),
                },
            ]
        )
    )

    access_token = token_manager.create_access_token(str(admin_id), UserRole.SUPER_ADMIN)

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/dashboard/analytics?range_key=7d',
            headers={'Authorization': f'Bearer {access_token}'},
        )

    assert response.status_code == 200
    payload = response.json()
    stat_cards = {item['key']: item for item in payload['stat_cards']}

    assert payload['range_key'] == '7d'
    assert stat_cards['total_users']['value'] == 3.0
    assert stat_cards['active_subscriptions']['value'] == 2.0
    assert stat_cards['monthly_revenue']['value'] == 53.17
    assert stat_cards['monthly_revenue']['value_formatted'] == '$53.17'
    assert stat_cards['trial_conversion']['value'] == 66.67
    assert len(payload['user_growth']) == 7
    assert len(payload['revenue_growth']) == 7
    assert payload['subscription_status'] == [
        {'key': 'active', 'label': 'Active', 'value': 2, 'percentage': 66.67, 'color_key': 'primary'},
        {'key': 'trial', 'label': 'Trial', 'value': 1, 'percentage': 33.33, 'color_key': 'dark'},
        {'key': 'other', 'label': 'Other', 'value': 0, 'percentage': 0.0, 'color_key': 'muted'},
    ]
    assert payload['billing_cycle'] == [
        {'key': 'monthly', 'label': 'Monthly', 'value': 1, 'percentage': 50.0, 'color_key': 'primary'},
        {'key': 'yearly', 'label': 'Yearly', 'value': 1, 'percentage': 50.0, 'color_key': 'dark'},
    ]



def test_dashboard_overview_requires_admin_role():
    app, mock_db = _build_app_with_mock_db()

    owner_id = ObjectId()
    asyncio.run(
        mock_db['users'].insert_one(
            {
                '_id': owner_id,
                'email': 'owner@example.com',
                'full_name': 'Owner User',
                'hashed_password': 'x',
                'role': UserRole.RESTAURANT_OWNER,
                'is_active': True,
                'email_verified': True,
                'created_at': datetime(2026, 2, 5, tzinfo=UTC),
                'updated_at': datetime(2026, 2, 5, tzinfo=UTC),
            }
        )
    )

    access_token = token_manager.create_access_token(str(owner_id), UserRole.RESTAURANT_OWNER)

    with TestClient(app) as client:
        response = client.get(
            '/api/v1/dashboard/overview?year=2026',
            headers={'Authorization': f'Bearer {access_token}'},
        )

    assert response.status_code == 403
    assert response.json()['error']['code'] == 'forbidden'
