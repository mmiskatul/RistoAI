from __future__ import annotations

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
    assert verified_user['subscription_status'] is None
    assert verified_user['subscription_plan_name'] is None
    assert verified_user['subscription_selection_required'] is True

    login_response = client.post(
        '/api/v1/auth/restaurant/login',
        json={'email': owner_credentials['email'], 'password': owner_credentials['password']},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()['tokens']['access_token']

    me_response = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {access_token}'})
    assert me_response.status_code == 200
    assert me_response.json()['role'] == 'restaurant_owner'
    assert me_response.json()['subscription_plan'] is None
    assert me_response.json()['subscription_plan_name'] is None
    assert me_response.json()['subscription_selection_required'] is True



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
        json={'email': owner_credentials['email'], 'code': '000000'},
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
