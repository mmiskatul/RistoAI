from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from mimetypes import guess_extension, guess_type
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.config.settings import Settings
from app.core.exceptions import ValidationException

IMAGE_CONTENT_TYPE_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/x-icon": "image/vnd.microsoft.icon",
}
SUPPORTED_IMAGE_EXTENSIONS = {
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".ico",
    ".jfif",
    ".jpeg",
    ".jpg",
    ".pjpeg",
    ".pjp",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
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
                "CLOUDINARY_CLOUD_NAME": self.settings.cloudinary_cloud_name,
                "CLOUDINARY_API_KEY": self.settings.cloudinary_api_key,
                "CLOUDINARY_API_SECRET": self.settings.cloudinary_api_secret,
            }.items()
            if not value
        ]
        if missing:
            raise ValidationException(
                "Cloudinary image upload settings are incomplete",
                {"missing_fields": missing},
            )

    def _resolve_image_metadata(self, *, file_name: str | None, content_type: str | None) -> tuple[str, str]:
        normalized_content_type = IMAGE_CONTENT_TYPE_ALIASES.get((content_type or "").lower(), (content_type or "").lower())
        file_extension = Path(file_name or "").suffix.lower()
        guessed_content_type = guess_type(file_name or "")[0]

        if not normalized_content_type or normalized_content_type == "application/octet-stream":
            normalized_content_type = guessed_content_type or ""
            normalized_content_type = IMAGE_CONTENT_TYPE_ALIASES.get(normalized_content_type, normalized_content_type)

        if not normalized_content_type.startswith("image/") and file_extension not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValidationException("Only image files are supported")

        if not normalized_content_type.startswith("image/"):
            normalized_content_type = "image/*"

        if file_extension in SUPPORTED_IMAGE_EXTENSIONS:
            return normalized_content_type, file_extension

        extension = guess_extension(normalized_content_type) or ""
        if extension == ".jpe":
            extension = ".jpg"
        return normalized_content_type, extension if extension in SUPPORTED_IMAGE_EXTENSIONS else ".jpg"

    def _build_public_url(self, key: str) -> str:
        cloud_name = self.settings.cloudinary_cloud_name or ""
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/{key.lstrip('/')}"

    def resolve_public_url(self, value: str | None) -> str | None:
        if not value:
            return value
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return self._build_public_url(value)

    def _upload_sync(self, *, content_type: str, extension: str, file_bytes: bytes, prefix: str) -> UploadedImage:
        self._validate_config()
        try:
            import cloudinary
            import cloudinary.uploader
        except ImportError as exc:  # pragma: no cover - dependency issue
            raise ValidationException("cloudinary is required for image uploads") from exc

        safe_prefix = prefix.strip("/").replace(" ", "-")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        folder_root = self.settings.cloudinary_folder.strip("/").replace(" ", "-")
        asset_folder = "/".join(part for part in [folder_root, safe_prefix] if part)
        public_id = f"{timestamp}-{uuid4().hex}"

        cloudinary.config(
            cloud_name=self.settings.cloudinary_cloud_name,
            api_key=self.settings.cloudinary_api_key,
            api_secret=self.settings.cloudinary_api_secret,
            secure=True,
        )

        upload_result = cloudinary.uploader.upload(
            file_bytes,
            folder=asset_folder or None,
            public_id=public_id,
            resource_type="image",
            format=extension.lstrip("."),
        )
        uploaded_public_id = str(upload_result.get("public_id") or "").strip()
        secure_url = str(upload_result.get("secure_url") or "").strip()

        if not uploaded_public_id or not secure_url:
            raise ValidationException("Cloudinary upload did not return a valid asset reference")

        return UploadedImage(url=secure_url, key=uploaded_public_id)

    async def upload_file(self, *, file: UploadFile, prefix: str) -> UploadedImage:
        content_type, extension = self._resolve_image_metadata(
            file_name=file.filename,
            content_type=file.content_type,
        )
        file_bytes = await file.read()
        if not file_bytes:
            raise ValidationException("Uploaded image is empty")
        return await run_in_threadpool(
            self._upload_sync,
            content_type=content_type,
            extension=extension,
            file_bytes=file_bytes,
            prefix=prefix,
        )


class DummyImageStorageService(ImageStorageService):
    async def upload_file(self, *, file: UploadFile, prefix: str) -> UploadedImage:
        _, extension = self._resolve_image_metadata(
            file_name=file.filename,
            content_type=file.content_type,
        )
        file_bytes = await file.read()
        if not file_bytes:
            raise ValidationException("Uploaded image is empty")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        key = f"{prefix.strip('/').replace(' ', '-')}/{timestamp}-{uuid4().hex}{extension}"
        return UploadedImage(url=f"https://example.com/{key}", key=key)


def build_image_storage_service(settings: Settings) -> ImageStorageService:
    if settings.testing:
        return DummyImageStorageService(settings)
    return ImageStorageService(settings)
