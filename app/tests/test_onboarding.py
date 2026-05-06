from __future__ import annotations

import asyncio

from app.tests.helpers import register_and_login, seed_subscription_plan, select_subscription_plan
from app.db.mongodb import get_database


def test_onboarding_feature_screens_are_localized(client) -> None:
    response = client.get('/api/v1/onboarding/feature-screens', headers={'Accept-Language': 'it'})

    assert response.status_code == 200
    body = response.json()
    assert body['language'] == 'it'
    assert [item['key'] for item in body['screens']] == [
        'profit_tracking',
        'invoice_photo_upload',
        'inventory',
        'vat_management',
    ]
    assert body['screens'][0]['title'] == 'Capisci cosa guida il profitto'
    assert len(body['screens'][0]['points']) == 3


def test_save_and_get_onboarding_profile(client, app, owner_credentials) -> None:
    seed_subscription_plan(app)
    headers = register_and_login(client, owner_credentials)
    select_subscription_plan(client, headers)
    payload = {
        'restaurant_name': 'The Italian Bistro',
        'restaurant_type': 'Fine Dining',
        'city_location': 'New York, NY',
        'number_of_seats': 45,
        'average_spend_per_customer': 25.0,
        'main_business_goal': 'Increase revenue',
        'biggest_problem': 'We struggle with slow weekday traffic and inconsistent table turnover.',
        'improvement_focus': 'Improve staff scheduling and reduce wasted inventory.',
    }

    save_response = client.post(
        '/api/v1/onboarding/profile',
        headers=headers,
        data=payload,
        files={
            'profile_image': ('profile.jpg', b'profile-image-bytes', 'image/jpeg'),
            'interior_photo': ('interior.jpg', b'interior-image-bytes', 'image/jpeg'),
            'exterior_photo': ('exterior.png', b'exterior-image-bytes', 'image/png'),
        },
    )
    assert save_response.status_code == 200
    body = save_response.json()
    assert body['restaurant_name'] == payload['restaurant_name']
    assert body['onboarding_completed'] is True
    assert body['profile_image_url'].startswith('https://')
    assert '/onboarding/' in body['profile_image_url']
    assert body['interior_photo_url'].startswith('https://')
    assert '/onboarding/' in body['interior_photo_url']
    assert body['exterior_photo_url'].startswith('https://')
    assert '/onboarding/' in body['exterior_photo_url']

    db = asyncio.run(app.dependency_overrides[get_database]())
    stored_profile = asyncio.run(db['onboarding_profiles'].find_one({'user_id': body['user_id']}))
    assert stored_profile['profile_image_url'].startswith('https://')
    assert '/onboarding/' in stored_profile['profile_image_url']
    assert stored_profile['interior_photo_url'].startswith('https://')
    assert '/onboarding/' in stored_profile['interior_photo_url']
    assert stored_profile['exterior_photo_url'].startswith('https://')
    assert '/onboarding/' in stored_profile['exterior_photo_url']

    get_response = client.get('/api/v1/onboarding/profile', headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()['restaurant_type'] == payload['restaurant_type']

    me_response = client.get('/api/v1/auth/me', headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()['restaurant_name'] == payload['restaurant_name']
    assert me_response.json()['location'] == payload['city_location']
    assert me_response.json()['onboarding_completed'] is True

    profile_response = client.get('/api/v1/restaurant/settings/profile', headers=headers)
    assert profile_response.status_code == 200
    profile_body = profile_response.json()
    assert profile_body['restaurant_name'] == payload['restaurant_name']
    assert profile_body['restaurant_type'] == payload['restaurant_type']
    assert profile_body['city_location'] == payload['city_location']
    assert profile_body['number_of_seats'] == payload['number_of_seats']
    assert profile_body['average_spend_per_customer'] == payload['average_spend_per_customer']
    assert profile_body['main_business_goal'] == payload['main_business_goal']
    assert profile_body['biggest_problem'] == payload['biggest_problem']
    assert profile_body['improvement_focus'] == payload['improvement_focus']
    assert profile_body['profile_image_url'] == body['profile_image_url']

    stored_user = asyncio.run(db['users'].find_one({'email': owner_credentials['email'].lower()}))
    assert stored_user['restaurant_name'] == payload['restaurant_name']
    assert stored_user['restaurant_type'] == payload['restaurant_type']
    assert stored_user['city_location'] == payload['city_location']
    assert stored_user['location'] == payload['city_location']
    assert stored_user['number_of_seats'] == payload['number_of_seats']
    assert stored_user['average_spend_per_customer'] == payload['average_spend_per_customer']
    assert stored_user['profile_image_url'] == stored_profile['profile_image_url']
    assert stored_user['avatar_url'] == stored_profile['profile_image_url']
    assert stored_user['onboarding_completed'] is True


def test_onboarding_allows_image_upload_before_completion(client, app, owner_credentials) -> None:
    seed_subscription_plan(app)
    headers = register_and_login(client, owner_credentials)
    select_subscription_plan(client, headers)

    upload_response = client.post(
        '/api/v1/upload/image',
        headers=headers,
        files={'file': ('interior.jpg', b'interior-image-bytes', 'image/jpeg')},
    )
    assert upload_response.status_code == 201
    image_url = upload_response.json()['url']
    assert image_url.startswith('https://')

    payload = {
        'restaurant_name': 'The Italian Bistro',
        'restaurant_type': 'Fine Dining',
        'city_location': 'New York, NY',
        'number_of_seats': 45,
        'average_spend_per_customer': 25.0,
        'main_business_goal': 'Increase revenue',
        'biggest_problem': 'We struggle with slow weekday traffic and inconsistent table turnover.',
        'improvement_focus': 'Improve staff scheduling and reduce wasted inventory.',
        'interior_photo_url': image_url,
        'exterior_photo_url': image_url,
    }
    save_response = client.post('/api/v1/onboarding/profile', headers=headers, data=payload)

    assert save_response.status_code == 200
    assert save_response.json()['interior_photo_url'] == image_url
    assert save_response.json()['exterior_photo_url'] == image_url


def test_restaurant_routes_require_completed_onboarding(client, app, owner_credentials) -> None:
    seed_subscription_plan(app)
    headers = register_and_login(client, owner_credentials)
    select_subscription_plan(client, headers)

    me_before = client.get('/api/v1/auth/me', headers=headers)
    assert me_before.status_code == 200
    assert me_before.json()['onboarding_completed'] is False

    blocked_response = client.get('/api/v1/restaurant/settings/profile', headers=headers)
    assert blocked_response.status_code == 403
    assert blocked_response.json()['error']['code'] == 'onboarding_required'

    payload = {
        'restaurant_name': 'The Italian Bistro',
        'restaurant_type': 'Fine Dining',
        'city_location': 'New York, NY',
        'number_of_seats': 45,
        'average_spend_per_customer': 25.0,
        'main_business_goal': 'Increase revenue',
        'biggest_problem': 'We struggle with slow weekday traffic and inconsistent table turnover.',
        'improvement_focus': 'Improve staff scheduling and reduce wasted inventory.',
    }
    save_response = client.post('/api/v1/onboarding/profile', headers=headers, data=payload)
    assert save_response.status_code == 200

    me_after = client.get('/api/v1/auth/me', headers=headers)
    assert me_after.status_code == 200
    assert me_after.json()['onboarding_completed'] is True

    allowed_response = client.get('/api/v1/restaurant/settings/profile', headers=headers)
    assert allowed_response.status_code == 200
    assert allowed_response.json()['restaurant_name'] == payload['restaurant_name']
