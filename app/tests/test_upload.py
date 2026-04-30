from __future__ import annotations

from app.tests.helpers import register_and_login, seed_subscription_plan


def test_upload_image_status_reports_existing_asset_and_enforces_ownership(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Upload Status Owner",
            "email": "upload-status@example.com",
            "password": "Passw0rd!",
            "phone_number": "+39000000010",
            "restaurant_name": "Upload Bistro",
            "restaurant_type": "Bistro",
            "city_location": "Rome",
            "number_of_seats": 18,
        },
    )

    upload_response = client.post(
        "/api/v1/upload/image",
        headers=headers,
        files={"file": ("avatar.png", b"fake-image-bytes", "image/png")},
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.json()
    assert upload_payload["key"].startswith("uploads/")
    assert upload_payload["url"]

    status_by_key_response = client.get(
        "/api/v1/upload/image/status",
        headers=headers,
        params={"key": upload_payload["key"]},
    )
    assert status_by_key_response.status_code == 200
    status_by_key_payload = status_by_key_response.json()
    assert status_by_key_payload["exists"] is True
    assert status_by_key_payload["key"] == upload_payload["key"]

    status_by_url_response = client.get(
        "/api/v1/upload/image/status",
        headers=headers,
        params={"url": upload_payload["url"]},
    )
    assert status_by_url_response.status_code == 200
    status_by_url_payload = status_by_url_response.json()
    assert status_by_url_payload["exists"] is True
    assert status_by_url_payload["key"] == upload_payload["key"]

    forbidden_response = client.get(
        "/api/v1/upload/image/status",
        headers=headers,
        params={"key": "uploads/someone-else/asset.png"},
    )
    assert forbidden_response.status_code == 403
