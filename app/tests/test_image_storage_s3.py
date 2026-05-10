from __future__ import annotations

from types import SimpleNamespace

from app.config.settings import Settings
from app.services.image_storage import (
    DummyImageStorageService,
    ImageStorageService,
    build_image_storage_service,
)


def _build_settings(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "testing": False,
        "AWS_ACCESS_KEY_ID": None,
        "AWS_SECRET_ACCESS_KEY": None,
        "AWS_S3_BUCKET": None,
        "AWS_REGION": None,
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

    assert isinstance(service, ImageStorageService)


def test_build_image_storage_service_uses_dummy_service_in_tests():
    service = build_image_storage_service(_build_settings(testing=True))
    assert isinstance(service, DummyImageStorageService)


def test_service_falls_back_to_inline_data_url_when_s3_not_configured():
    service = build_image_storage_service(_build_settings())

    class UploadFileStub:
        filename = "avatar.png"
        content_type = "image/png"

        async def read(self):
            return b"fake-image-bytes"

    uploaded = __import__("asyncio").run(
        service.upload_file(file=UploadFileStub(), prefix="uploads/user-123")
    )

    assert uploaded.key.startswith("inline/uploads/user-123/")
    assert uploaded.url.startswith("data:image/png;base64,")


def test_service_falls_back_to_inline_data_url_when_s3_upload_fails(monkeypatch):
    service = ImageStorageService(
        _build_settings(
            AWS_ACCESS_KEY_ID="access-key",
            AWS_SECRET_ACCESS_KEY="secret-key",
            AWS_S3_BUCKET="ristoai-assets",
            AWS_REGION="eu-central-1",
        )
    )

    def raise_upload_failure(**_: object):
        from app.core.exceptions import ValidationException

        raise ValidationException("Image upload failed", {"provider": "aws_s3", "reason": "network timeout"})

    monkeypatch.setattr(service, "_upload_sync", raise_upload_failure)

    class UploadFileStub:
        filename = "avatar.png"
        content_type = "image/png"

        async def read(self):
            return b"fake-image-bytes"

    uploaded = __import__("asyncio").run(
        service.upload_file(file=UploadFileStub(), prefix="uploads/user-123")
    )

    assert uploaded.key.startswith("inline/uploads/user-123/")
    assert uploaded.url.startswith("data:image/png;base64,")


def test_s3_service_upload_and_status_use_bucket_urls(monkeypatch):
    service = ImageStorageService(
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
    service = ImageStorageService(
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
