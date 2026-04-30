from __future__ import annotations

from types import SimpleNamespace

from app.config.settings import Settings
from app.services.image_storage import (
    CloudinaryImageStorageService,
    S3ImageStorageService,
    build_image_storage_service,
)


def _build_settings(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "TESTING": False,
        "AWS_ACCESS_KEY_ID": None,
        "AWS_SECRET_ACCESS_KEY": None,
        "AWS_S3_BUCKET": None,
        "AWS_REGION": None,
        "CLOUDINARY_CLOUD_NAME": None,
        "CLOUDINARY_API_KEY": None,
        "CLOUDINARY_API_SECRET": None,
    }
    base.update(overrides)
    return Settings(**base)


def test_build_image_storage_service_prefers_s3_when_aws_is_configured():
    service = build_image_storage_service(
        _build_settings(
            AWS_ACCESS_KEY_ID="access-key",
            AWS_SECRET_ACCESS_KEY="secret-key",
            AWS_S3_BUCKET="ristoai-assets",
            AWS_REGION="eu-central-1",
        )
    )

    assert isinstance(service, S3ImageStorageService)


def test_build_image_storage_service_falls_back_to_cloudinary_when_aws_is_not_configured():
    service = build_image_storage_service(
        _build_settings(
            CLOUDINARY_CLOUD_NAME="demo",
            CLOUDINARY_API_KEY="key",
            CLOUDINARY_API_SECRET="secret",
        )
    )

    assert isinstance(service, CloudinaryImageStorageService)


def test_s3_service_upload_and_status_use_bucket_urls(monkeypatch):
    service = S3ImageStorageService(
        _build_settings(
            AWS_ACCESS_KEY_ID="access-key",
            AWS_SECRET_ACCESS_KEY="secret-key",
            AWS_S3_BUCKET="ristoai-assets",
            AWS_REGION="eu-central-1",
        )
    )

    calls: list[tuple[str, str]] = []

    class FakeS3Client:
        def put_object(self, *, Bucket, Key, Body, ContentType):
            calls.append(("put", Key))
            assert Bucket == "ristoai-assets"
            assert ContentType == "image/png"
            assert Body == b"fake-image-bytes"

        def head_object(self, *, Bucket, Key):
            calls.append(("head", Key))
            assert Bucket == "ristoai-assets"

    monkeypatch.setattr(service, "_create_client", lambda: FakeS3Client())

    uploaded = service._upload_sync(
        content_type="image/png",
        extension=".png",
        file_bytes=b"fake-image-bytes",
        prefix="uploads/user-123",
    )

    assert uploaded.key.startswith("uploads/user-123/")
    assert uploaded.key.endswith(".png")
    assert uploaded.url == f"https://ristoai-assets.s3.eu-central-1.amazonaws.com/{uploaded.key}"

    status = service._get_upload_status_sync(key=uploaded.key, url=uploaded.url)

    assert status.exists is True
    assert status.key == uploaded.key
    assert status.url == uploaded.url
    assert calls == [("put", uploaded.key), ("head", uploaded.key)]


def test_s3_service_status_returns_missing_when_object_does_not_exist(monkeypatch):
    service = S3ImageStorageService(
        _build_settings(
            AWS_ACCESS_KEY_ID="access-key",
            AWS_SECRET_ACCESS_KEY="secret-key",
            AWS_S3_BUCKET="ristoai-assets",
            AWS_REGION="eu-central-1",
        )
    )

    class FakeS3Client:
        def head_object(self, *, Bucket, Key):
            raise Exception("404 Not Found")

    monkeypatch.setattr(service, "_create_client", lambda: FakeS3Client())

    status = service._get_upload_status_sync(
        key="uploads/user-123/missing.png",
        url="https://ristoai-assets.s3.eu-central-1.amazonaws.com/uploads/user-123/missing.png",
    )

    assert status.exists is False
