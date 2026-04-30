from __future__ import annotations

from unittest.mock import patch
from types import SimpleNamespace

from app.tests.helpers import register_and_login, seed_subscription_plan


def test_aws_upload_config_status_and_precheck_endpoints(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "AWS Upload Check Owner",
            "email": "aws-upload-check@example.com",
            "password": "Passw0rd!",
            "phone_number": "+39000000011",
            "restaurant_name": "AWS Check Bistro",
            "restaurant_type": "Bistro",
            "city_location": "Rome",
            "number_of_seats": 22,
        },
    )

    config_response = client.get("/api/v1/upload/aws/config-status", headers=headers)
    assert config_response.status_code == 200
    config_payload = config_response.json()
    assert config_payload["provider"] == "aws_s3"
    assert "configured" in config_payload
    assert "missing_fields" in config_payload

    precheck_response = client.post(
        "/api/v1/upload/aws/image/precheck",
        headers=headers,
        files={"file": ("image.png", b"fake-image-bytes", "image/png")},
    )
    assert precheck_response.status_code == 200
    precheck_payload = precheck_response.json()
    assert precheck_payload["provider"] == "aws_s3"
    assert precheck_payload["file_name"] == "image.png"
    assert precheck_payload["content_type"] in {"image/png", "image/*"}
    assert precheck_payload["size_bytes"] > 0


def test_aws_upload_precheck_rejects_non_image_file(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "AWS Upload Invalid File Owner",
            "email": "aws-upload-invalid@example.com",
            "password": "Passw0rd!",
            "phone_number": "+39000000012",
            "restaurant_name": "AWS Invalid Bistro",
            "restaurant_type": "Bistro",
            "city_location": "Rome",
            "number_of_seats": 14,
        },
    )

    response = client.post(
        "/api/v1/upload/aws/image/precheck",
        headers=headers,
        files={"file": ("notes.txt", b"not-an-image", "text/plain")},
    )
    assert response.status_code == 422


def test_aws_upload_verify_reports_missing_configuration(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "AWS Verify Owner",
            "email": "aws-verify@example.com",
            "password": "Passw0rd!",
            "phone_number": "+39000000013",
            "restaurant_name": "AWS Verify Bistro",
            "restaurant_type": "Bistro",
            "city_location": "Rome",
            "number_of_seats": 16,
        },
    )

    with patch("app.api.v1.endpoints.upload.get_settings") as mocked_settings:
        mocked_settings.return_value = SimpleNamespace(
            aws_access_key_id=None,
            aws_secret_access_key=None,
            aws_s3_bucket=None,
            aws_region="eu-south-1",
        )
        response = client.post("/api/v1/upload/aws/verify", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "aws_s3"
    assert payload["configured"] is False
    assert payload["bucket_accessible"] is False
    assert payload["write_test_passed"] is False
    assert "missing_fields" in payload


def test_aws_upload_verify_reports_missing_sdk_when_configured(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "AWS Verify SDK Owner",
            "email": "aws-verify-sdk@example.com",
            "password": "Passw0rd!",
            "phone_number": "+39000000014",
            "restaurant_name": "AWS Verify SDK Bistro",
            "restaurant_type": "Bistro",
            "city_location": "Rome",
            "number_of_seats": 16,
        },
    )

    with patch("app.api.v1.endpoints.upload.get_settings") as mocked_settings:
        mocked_settings.return_value.aws_access_key_id = "key"
        mocked_settings.return_value.aws_secret_access_key = "secret"
        mocked_settings.return_value.aws_s3_bucket = "bucket"
        mocked_settings.return_value.aws_region = "eu-south-1"
        with patch.dict("sys.modules", {"boto3": None}):
            response = client.post("/api/v1/upload/aws/verify", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["sdk_available"] is False
    assert payload["bucket_accessible"] is False
    assert payload["write_test_passed"] is False
