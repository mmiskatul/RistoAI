from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from mimetypes import guess_extension
from uuid import uuid4

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.config.settings import Settings
from app.core.exceptions import ValidationException

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


@dataclass(slots=True)
class UploadedImage:
    url: str
    key: str


class ImageStorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _validate_config(self) -> None:
        missing = [
            name
            for name, value in {
                "AWS_ACCESS_KEY_ID": self.settings.aws_access_key_id,
                "AWS_SECRET_ACCESS_KEY": self.settings.aws_secret_access_key,
                "AWS_REGION": self.settings.aws_region,
                "AWS_S3_BUCKET_NAME": self.settings.aws_s3_bucket_name,
            }.items()
            if not value
        ]
        if missing:
            raise ValidationException(
                "AWS image upload settings are incomplete",
                {"missing_fields": missing},
            )

    def _normalize_extension(self, content_type: str) -> str:
        extension = guess_extension(content_type) or ""
        if extension == ".jpe":
            return ".jpg"
        if extension in {".jpg", ".jpeg", ".png", ".webp"}:
            return extension
        return ".jpg"

    def _build_public_url(self, key: str) -> str:
        if self.settings.aws_s3_public_base_url:
            return f"{self.settings.aws_s3_public_base_url.rstrip('/')}/{key}"
        region = self.settings.aws_region or "us-east-1"
        bucket = self.settings.aws_s3_bucket_name or ""
        if region == "us-east-1":
            return f"https://{bucket}.s3.amazonaws.com/{key}"
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    def resolve_public_url(self, value: str | None) -> str | None:
        if not value:
            return value
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return self._build_public_url(value)

    def _upload_sync(self, *, file_name: str, content_type: str, file_bytes: bytes, prefix: str) -> UploadedImage:
        self._validate_config()
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - dependency issue
            raise ValidationException("boto3 is required for AWS image uploads") from exc

        extension = self._normalize_extension(content_type)
        safe_prefix = prefix.strip("/").replace(" ", "-")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        key = f"{safe_prefix}/{timestamp}-{uuid4().hex}{extension}"

        client = boto3.client(
            "s3",
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
            region_name=self.settings.aws_region,
        )
        client.put_object(
            Bucket=self.settings.aws_s3_bucket_name,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return UploadedImage(url=self._build_public_url(key), key=key)

    async def upload_file(self, *, file: UploadFile, prefix: str) -> UploadedImage:
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationException("Only JPG, JPEG, PNG, and WEBP images are supported")
        file_bytes = await file.read()
        if not file_bytes:
            raise ValidationException("Uploaded image is empty")
        return await run_in_threadpool(
            self._upload_sync,
            file_name=file.filename or "upload-image",
            content_type=content_type,
            file_bytes=file_bytes,
            prefix=prefix,
        )


class DummyImageStorageService(ImageStorageService):
    async def upload_file(self, *, file: UploadFile, prefix: str) -> UploadedImage:
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationException("Only JPG, JPEG, PNG, and WEBP images are supported")
        file_bytes = await file.read()
        if not file_bytes:
            raise ValidationException("Uploaded image is empty")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        extension = self._normalize_extension(content_type)
        key = f"{prefix.strip('/').replace(' ', '-')}/{timestamp}-{uuid4().hex}{extension}"
        return UploadedImage(url=f"https://example.com/{key}", key=key)


def build_image_storage_service(settings: Settings) -> ImageStorageService:
    if settings.testing:
        return DummyImageStorageService(settings)
    return ImageStorageService(settings)
