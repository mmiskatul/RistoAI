from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pytest
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.config.settings import Settings
from app.services.image_storage import DummyImageStorageService, ImageStorageService
from app.core.exceptions import ValidationException


def test_dummy_image_storage_accepts_supported_upload_and_returns_public_url() -> None:
    service = DummyImageStorageService(Settings(testing=True))
    upload = UploadFile(file=BytesIO(b"fake-image-bytes"), filename="photo.jpg")

    result = __import__("asyncio").run(service.upload_file(file=upload, prefix="onboarding/user/interior"))

    assert result.url.startswith("https://example.com/onboarding/user/interior/")
    assert result.key.startswith("onboarding/user/interior/")
    assert result.url.endswith(".jpg")


def test_cloudinary_public_url_resolution_keeps_existing_url() -> None:
    settings = Settings(
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="key",
        CLOUDINARY_API_SECRET="secret",
    )
    service = ImageStorageService(settings)

    url = "https://res.cloudinary.com/demo-cloud/image/upload/v1/sample.jpg"

    assert service.resolve_public_url(url) == url


def test_cloudinary_public_url_resolution_builds_url_from_public_id() -> None:
    settings = Settings(
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="key",
        CLOUDINARY_API_SECRET="secret",
    )
    service = ImageStorageService(settings)

    assert (
        service.resolve_public_url("ristoai/onboarding/user/image")
        == "https://res.cloudinary.com/demo-cloud/image/upload/ristoai/onboarding/user/image"
    )


def test_cloudinary_upload_retries_transient_failure_and_returns_secure_url() -> None:
    settings = Settings(
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="key",
        CLOUDINARY_API_SECRET="secret",
    )
    service = ImageStorageService(settings)
    responses = [
        RuntimeError("temporary network timeout"),
        {
            "public_id": "ristoai/onboarding/user/image",
            "secure_url": "https://res.cloudinary.com/demo-cloud/image/upload/ristoai/onboarding/user/image.jpg",
        },
    ]

    def fake_upload(*args, **kwargs):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch.object(cloudinary, "config"), patch.object(cloudinary.uploader, "upload", side_effect=fake_upload):
        uploaded = service._upload_sync(
            content_type="image/jpeg",
            extension=".jpg",
            file_bytes=b"fake-image-bytes",
            prefix="onboarding/user/interior",
            original_file_name="photo.jpg",
        )

    assert uploaded.key == "ristoai/onboarding/user/image"
    assert uploaded.url.endswith(".jpg")


def test_cloudinary_upload_raises_validation_error_for_invalid_provider_response() -> None:
    settings = Settings(
        CLOUDINARY_CLOUD_NAME="demo-cloud",
        CLOUDINARY_API_KEY="key",
        CLOUDINARY_API_SECRET="secret",
    )
    service = ImageStorageService(settings)

    with patch.object(cloudinary, "config"), patch.object(
        cloudinary.uploader,
        "upload",
        return_value={"public_id": "ristoai/onboarding/user/image"},
    ):
        with pytest.raises(ValidationException, match="public URL"):
            service._upload_sync(
                content_type="image/jpeg",
                extension=".jpg",
                file_bytes=b"fake-image-bytes",
                prefix="onboarding/user/interior",
                original_file_name="photo.jpg",
            )
