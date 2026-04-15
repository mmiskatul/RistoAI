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
