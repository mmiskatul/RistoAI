from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from bson import ObjectId
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.core.enums import AccountStatus, SubscriptionStatus, UserRole
from app.core.security import password_manager
from app.db.mongodb import get_database
from app.main import create_app
from app.tests.helpers import register_and_login



def test_auth_restaurant_register_verify_login_and_me(client, owner_credentials):
    register_response = client.post('/api/v1/auth/restaurant/register', json=owner_credentials)
    assert register_response.status_code == 201
    register_payload = register_response.json()
    assert register_payload['verification_required'] is True
    assert register_payload['purpose'] == 'restaurant_registration'
    assert register_payload['debug_verification_code']

    verify_registration_response = client.post(
        '/api/v1/auth/restaurant/verify-registration',
        json={'email': owner_credentials['email'], 'code': register_payload['debug_verification_code']},
    )
    assert verify_registration_response.status_code == 200
    verified_user = verify_registration_response.json()['user']
    assert verified_user['email_verified'] is True
    assert verified_user['preferred_language'] == 'en'
    assert verified_user['subscription_status'] == 'trial'
    assert verified_user['subscription_plan_name'] == 'Core Plan'
    assert verified_user['subscription_plan'] == '1_month'
    assert verified_user['subscription_started_at'] is not None
    assert verified_user['subscription_expires_at'] is not None
    assert verified_user['subscription_selection_required'] is False

    login_response = client.post(
        '/api/v1/auth/restaurant/login',
        json={'email': owner_credentials['email'], 'password': owner_credentials['password']},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()['tokens']['access_token']

    me_response = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {access_token}'})
    assert me_response.status_code == 200
    assert me_response.json()['role'] == 'restaurant_owner'
    assert me_response.json()['preferred_language'] == 'en'
    assert me_response.json()['subscription_plan'] == '1_month'
    assert me_response.json()['subscription_plan_name'] == 'Core Plan'
    assert me_response.json()['subscription_status'] == 'trial'
    assert me_response.json()['subscription_selection_required'] is False



def test_update_language_preference(client, owner_credentials):
    headers = register_and_login(client, owner_credentials)

    get_response = client.get('/api/v1/auth/preferences/language', headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()['preferred_language'] == 'en'

    update_response = client.put(
        '/api/v1/auth/preferences/language',
        headers=headers,
        json={'preferred_language': 'it'},
    )
    assert update_response.status_code == 200
    assert update_response.json()['preferred_language'] == 'it'

    me_response = client.get('/api/v1/auth/me', headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()['preferred_language'] == 'it'



def test_reject_invalid_password_with_json_validation_error(client):
    response = client.post(
        '/api/v1/auth/restaurant/register',
        json={
            'full_name': 'Test User',
            'email': 'test@example.com',
            'password': 'stringst',
            'phone': '+15550001111',
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload['error']['code'] == 'validation_error'
    assert payload['error']['details']['errors'][0]['loc'] == ['body', 'password']
    assert 'Password must include letters and numbers' in payload['error']['details']['errors'][0]['msg']
    assert payload['error']['details']['errors'][0]['ctx']['error'] == 'Password must include letters and numbers'



def test_reject_invalid_restaurant_verification_code(client, owner_credentials):
    client.post('/api/v1/auth/restaurant/register', json=owner_credentials)
    response = client.post(
        '/api/v1/auth/restaurant/verify-registration',
        json={'email': owner_credentials['email'], 'code': '0000'},
    )
    assert response.status_code == 422



def test_restaurant_forgot_password_flow(client, owner_credentials):
    register_response = client.post('/api/v1/auth/restaurant/register', json=owner_credentials)
    register_code = register_response.json()['debug_verification_code']
    client.post(
        '/api/v1/auth/restaurant/verify-registration',
        json={'email': owner_credentials['email'], 'code': register_code},
    )

    forgot_response = client.post(
        '/api/v1/auth/restaurant/forgot-password',
        json={'email': owner_credentials['email']},
    )
    assert forgot_response.status_code == 200
    reset_code = forgot_response.json()['debug_verification_code']

    reset_response = client.post(
        '/api/v1/auth/restaurant/reset-password',
        json={
            'email': owner_credentials['email'],
            'code': reset_code,
            'new_password': 'NewOwnerPass123',
            'confirm_password': 'NewOwnerPass123',
        },
    )
    assert reset_response.status_code == 200

    login_response = client.post(
        '/api/v1/auth/restaurant/login',
        json={'email': owner_credentials['email'], 'password': 'NewOwnerPass123'},
    )
    assert login_response.status_code == 200



def test_reject_password_reset_when_password_confirmation_mismatch(client):
    response = client.post(
        '/api/v1/auth/restaurant/reset-password',
        json={
            'email': 'owner@example.com',
            'code': '123456',
            'new_password': 'NewOwnerPass123',
            'confirm_password': 'DifferentPass123',
        },
    )
    assert response.status_code == 422


def test_suspended_restaurant_user_can_login():
    app = create_app(testing=True)
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client['ristoai_test']

    async def override_get_database():
        return mock_db

    app.dependency_overrides[get_database] = override_get_database

    asyncio.run(
        mock_db['users'].insert_one(
            {
                '_id': ObjectId(),
                'email': 'suspended@example.com',
                'full_name': 'Suspended User',
                'hashed_password': password_manager.hash_password('SuspendedPass1'),
                'role': UserRole.RESTAURANT_OWNER,
                'is_active': False,
                'email_verified': True,
                'subscription_status': SubscriptionStatus.SUSPENDED,
                'account_status': AccountStatus.SUSPENDED,
                'preferred_language': 'en',
                'restaurant_name': 'Suspended Bistro',
                'location': 'Dhaka',
                'created_at': datetime.now(UTC),
                'updated_at': datetime.now(UTC),
            }
        )
    )

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/auth/restaurant/login',
            json={'email': 'suspended@example.com', 'password': 'SuspendedPass1'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['user']['is_active'] is False
    assert payload['user']['subscription_status'] == 'suspended'
    assert payload['user']['account_status'] == 'suspended'

    me_response = client.get(
        '/api/v1/auth/me',
        headers={'Authorization': f'Bearer {payload["tokens"]["access_token"]}'},
    )

    assert me_response.status_code == 200
    assert me_response.json()['account_status'] == 'suspended'


def test_restricted_restaurant_user_can_login():
    app = create_app(testing=True)
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client['ristoai_test']

    async def override_get_database():
        return mock_db

    app.dependency_overrides[get_database] = override_get_database

    asyncio.run(
        mock_db['users'].insert_one(
            {
                '_id': ObjectId(),
                'email': 'restricted@example.com',
                'full_name': 'Restricted User',
                'hashed_password': password_manager.hash_password('RestrictedPass1'),
                'role': UserRole.RESTAURANT_OWNER,
                'is_active': False,
                'email_verified': True,
                'subscription_status': SubscriptionStatus.ACTIVE,
                'account_status': AccountStatus.RESTRICTED,
                'preferred_language': 'en',
                'restaurant_name': 'Restricted Bistro',
                'location': 'Dhaka',
                'created_at': datetime.now(UTC),
                'updated_at': datetime.now(UTC),
            }
        )
    )

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/auth/restaurant/login',
            json={'email': 'restricted@example.com', 'password': 'RestrictedPass1'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['user']['is_active'] is False
    assert payload['user']['subscription_status'] == 'active'
    assert payload['user']['account_status'] == 'restricted'
