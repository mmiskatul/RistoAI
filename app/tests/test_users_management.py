from __future__ import annotations

import asyncio
from datetime import UTC, datetime

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



def _seed_users(mock_db):
    admin_id = ObjectId()
    owner_id = ObjectId()
    suspended_id = ObjectId()
    pending_id = ObjectId()
    now = datetime(2026, 3, 12, tzinfo=UTC)

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
                    'restaurant_name': None,
                    'location': None,
                    'subscription_plan_name': None,
                    'subscription_plan': None,
                    'subscription_status': None,
                    'subscription_started_at': None,
                    'subscription_expires_at': None,
                    'created_at': now,
                    'updated_at': now,
                },
                {
                    '_id': owner_id,
                    'email': 'owner@example.com',
                    'full_name': 'Owner User',
                    'phone': '+20000000000',
                    'hashed_password': 'x',
                    'role': UserRole.RESTAURANT_OWNER,
                    'is_active': True,
                    'email_verified': True,
                    'restaurant_name': 'La Trattoria Milano',
                    'location': 'Milan, Italy',
                    'subscription_plan_name': 'Pro Plan',
                    'subscription_plan': SubscriptionPlan.ONE_YEAR,
                    'subscription_status': SubscriptionStatus.ACTIVE,
                    'subscription_started_at': datetime(2026, 1, 1, tzinfo=UTC),
                    'subscription_expires_at': datetime(2026, 12, 31, tzinfo=UTC),
                    'created_at': datetime(2026, 2, 1, tzinfo=UTC),
                    'updated_at': datetime(2026, 2, 1, tzinfo=UTC),
                },
                {
                    '_id': suspended_id,
                    'email': 'suspended@example.com',
                    'full_name': 'Suspended User',
                    'phone': '+30000000000',
                    'hashed_password': 'x',
                    'role': UserRole.MANAGER,
                    'is_active': False,
                    'email_verified': True,
                    'restaurant_name': 'Kitchen Ops',
                    'location': 'Salento',
                    'subscription_plan_name': 'Growth Plan',
                    'subscription_plan': SubscriptionPlan.ONE_MONTH,
                    'subscription_status': SubscriptionStatus.SUSPENDED,
                    'subscription_started_at': datetime(2026, 1, 1, tzinfo=UTC),
                    'subscription_expires_at': datetime(2026, 2, 1, tzinfo=UTC),
                    'created_at': datetime(2026, 1, 20, tzinfo=UTC),
                    'updated_at': datetime(2026, 1, 20, tzinfo=UTC),
                },
                {
                    '_id': pending_id,
                    'email': 'pending@example.com',
                    'full_name': 'Pending User',
                    'phone': '+40000000000',
                    'hashed_password': 'x',
                    'role': UserRole.STAFF,
                    'is_active': True,
                    'email_verified': False,
                    'restaurant_name': 'Sushi Zen',
                    'location': 'Marches',
                    'subscription_plan_name': 'Starter Plan',
                    'subscription_plan': SubscriptionPlan.ONE_MONTH,
                    'subscription_status': SubscriptionStatus.TRIAL,
                    'subscription_started_at': datetime(2026, 1, 5, tzinfo=UTC),
                    'subscription_expires_at': datetime(2026, 2, 5, tzinfo=UTC),
                    'created_at': datetime(2026, 1, 5, tzinfo=UTC),
                    'updated_at': datetime(2026, 1, 5, tzinfo=UTC),
                },
            ]
        )
    )
    return admin_id, owner_id, suspended_id, pending_id



def _admin_headers(admin_id: ObjectId) -> dict[str, str]:
    token = token_manager.create_access_token(str(admin_id), UserRole.SUPER_ADMIN)
    return {'Authorization': f'Bearer {token}'}



def test_get_users_management_page_returns_summary_and_items():
    app, mock_db = _build_app_with_mock_db()
    admin_id, owner_id, _, _ = _seed_users(mock_db)

    with TestClient(app) as client:
        response = client.get('/api/v1/users/management?page=1&page_size=10', headers=_admin_headers(admin_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload['page_title'] == 'Users Management'
    assert payload['page_subtitle'] == 'Manage restaurant owners and user accounts across the platform.'
    assert payload['search_placeholder'] == 'Search users, restaurants...'
    assert payload['filter_button_label'] == 'Filters'
    assert payload['summary'] == {
        'total_users': 4,
        'active_users': 3,
        'suspended_users': 1,
        'trial_users': 1,
    }
    assert payload['summary_cards'][0]['label'] == 'Total Users'
    assert payload['summary_cards'][0]['value'] == 4
    assert payload['summary_cards'][1]['label'] == 'Active Users'
    assert payload['summary_cards'][2]['label'] == 'Suspended Users'
    assert payload['table_columns'][0] == {'key': 'user_name', 'label': 'User Name'}
    assert payload['pagination_label'] == 'Showing 1 to 4 of 4 users'
    assert payload['total'] == 4
    owner_item = next(item for item in payload['items'] if item['id'] == str(owner_id))
    assert owner_item['restaurant_name'] == 'La Trattoria Milano'
    assert owner_item['restaurant'] == 'La Trattoria Milano'
    assert owner_item['location'] == 'Milan, Italy'
    assert owner_item['subscription_plan_name'] == 'Pro Plan'
    assert owner_item['subscription_plan'] == '1_year'
    assert owner_item['subscription_status'] == 'active'
    assert owner_item['status'] == 'active'
    assert owner_item['status_label'] == 'ACTIVE'
    assert owner_item['status_color'] == 'green'
    assert owner_item['plan_label'] == '1 YEAR'
    assert owner_item['join_date_formatted'] == 'Feb 01, 2026'
    assert owner_item['view_endpoint'] == f"/api/v1/users/{owner_item['id']}"
    assert owner_item['edit_endpoint'] == f"/api/v1/users/{owner_item['id']}"
    assert owner_item['actions_menu'][0]['label'] == 'Suspend Account'
    assert owner_item['actions_menu'][1]['label'] == 'Delete User'



def test_get_users_management_page_supports_search():
    app, mock_db = _build_app_with_mock_db()
    admin_id, _, _, _ = _seed_users(mock_db)

    with TestClient(app) as client:
        response = client.get('/api/v1/users/management?search=trattoria', headers=_admin_headers(admin_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload['total'] == 1
    assert payload['items'][0]['email'] == 'owner@example.com'



def test_update_user_updates_user_details():
    app, mock_db = _build_app_with_mock_db()
    admin_id, owner_id, _, _ = _seed_users(mock_db)

    with TestClient(app) as client:
        response = client.patch(
            f'/api/v1/users/{owner_id}',
            headers=_admin_headers(admin_id),
            json={
                'full_name': 'Marco Rossi',
                'email': 'marco@example.com',
                'phone': '+8801700000000',
                'role': 'manager',
                'email_verified': True,
                'restaurant_name': 'Marco Bistro',
                'location': 'Rome, Italy',
                'subscription_plan_name': 'Growth Plan',
                'subscription_plan': '1_month',
                'subscription_status': 'trial',
                'subscription_started_at': '2026-03-01T00:00:00Z',
                'subscription_expires_at': '2026-04-01T00:00:00Z'
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['user']['full_name'] == 'Marco Rossi'
    assert payload['user']['email'] == 'marco@example.com'
    assert payload['user']['phone'] == '+8801700000000'
    assert payload['user']['role'] == 'manager'
    assert payload['user']['restaurant_name'] == 'Marco Bistro'
    assert payload['user']['location'] == 'Rome, Italy'
    assert payload['user']['subscription_plan_name'] == 'Growth Plan'
    assert payload['user']['subscription_plan'] == '1_month'
    assert payload['user']['subscription_status'] == 'trial'



def test_suspend_and_delete_user():
    app, mock_db = _build_app_with_mock_db()
    admin_id, owner_id, _, _ = _seed_users(mock_db)

    with TestClient(app) as client:
        suspend_response = client.post(f'/api/v1/users/{owner_id}/suspend', headers=_admin_headers(admin_id))
        delete_response = client.delete(f'/api/v1/users/{owner_id}', headers=_admin_headers(admin_id))
        list_response = client.get('/api/v1/users/management', headers=_admin_headers(admin_id))

    assert suspend_response.status_code == 200
    assert suspend_response.json()['user']['status'] == 'suspended'
    assert suspend_response.json()['user']['status_label'] == 'SUSPENDED'
    assert suspend_response.json()['user']['subscription_status'] == 'suspended'
    assert delete_response.status_code == 204
    assert all(item['id'] != str(owner_id) for item in list_response.json()['items'])



def test_users_management_requires_super_admin():
    app, mock_db = _build_app_with_mock_db()
    _, owner_id, _, _ = _seed_users(mock_db)
    owner_token = token_manager.create_access_token(str(owner_id), UserRole.RESTAURANT_OWNER)

    with TestClient(app) as client:
        response = client.get('/api/v1/users/management', headers={'Authorization': f'Bearer {owner_token}'})

    assert response.status_code == 403
    assert response.json()['error']['code'] == 'forbidden'
