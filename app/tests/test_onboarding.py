from __future__ import annotations

import asyncio

from app.tests.helpers import register_and_login, seed_subscription_plan, select_subscription_plan
from app.db.mongodb import get_database


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
            'interior_photo': ('interior.jpg', b'interior-image-bytes', 'image/jpeg'),
            'exterior_photo': ('exterior.png', b'exterior-image-bytes', 'image/png'),
        },
    )
    assert save_response.status_code == 200
    body = save_response.json()
    assert body['restaurant_name'] == payload['restaurant_name']
    assert body['onboarding_completed'] is True
    assert body['interior_photo_url'].startswith('https://')
    assert '/onboarding/' in body['interior_photo_url']
    assert body['exterior_photo_url'].startswith('https://')
    assert '/onboarding/' in body['exterior_photo_url']

    db = asyncio.run(app.dependency_overrides[get_database]())
    stored_profile = asyncio.run(db['onboarding_profiles'].find_one({'user_id': body['user_id']}))
    assert not stored_profile['interior_photo_url'].startswith('https://')
    assert '/onboarding/' in stored_profile['interior_photo_url']
    assert not stored_profile['exterior_photo_url'].startswith('https://')
    assert '/onboarding/' in stored_profile['exterior_photo_url']

    get_response = client.get('/api/v1/onboarding/profile', headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()['restaurant_type'] == payload['restaurant_type']

    me_response = client.get('/api/v1/auth/me', headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()['restaurant_name'] == payload['restaurant_name']
    assert me_response.json()['location'] == payload['city_location']

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
    assert profile_body['profile_image_url'].startswith('https://')
    assert '/onboarding/' in profile_body['profile_image_url']

    stored_user = asyncio.run(db['users'].find_one({'email': owner_credentials['email'].lower()}))
    assert stored_user['restaurant_name'] == payload['restaurant_name']
    assert stored_user['restaurant_type'] == payload['restaurant_type']
    assert stored_user['city_location'] == payload['city_location']
    assert stored_user['location'] == payload['city_location']
    assert stored_user['number_of_seats'] == payload['number_of_seats']
    assert stored_user['average_spend_per_customer'] == payload['average_spend_per_customer']
    assert stored_user['profile_image_url'] == stored_profile['interior_photo_url']
    assert stored_user['avatar_url'] == stored_profile['interior_photo_url']
