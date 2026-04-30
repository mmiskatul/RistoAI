from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep
from mimetypes import guess_extension, guess_type
from pathlib import Path
import re
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
MAX_UPLOAD_ATTEMPTS = 3
RETRYABLE_UPLOAD_ERROR_MESSAGES = (
    "timeout",
    "tempor",
    "connection",
    "network",
    "reset",
    "unavailable",
    "429",
    "500",
    "502",
    "503",
    "504",
)


@dataclass(slots=True)
class UploadedImage:
    url: str
    key: str


@dataclass(slots=True)
class UploadedImageStatus:
    exists: bool
    key: str
    url: str


class ImageStorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def upload_file(self, *, file: UploadFile, prefix: str) -> UploadedImage:
        raise NotImplementedError

    async def get_upload_status(self, *, key: str | None = None, url: str | None = None) -> UploadedImageStatus:
        raise NotImplementedError


class CloudinaryImageStorageService(ImageStorageService):
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
            missing_label = ", ".join(missing)
            raise ValidationException(
                f"Cloudinary image upload settings are incomplete: {missing_label}",
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

    @staticmethod
    def _extract_key_from_url(url: str) -> str:
        marker = "/image/upload/"
        if marker not in url:
            raise ValidationException("Unsupported image URL", {"url": url})
        asset_path = url.split(marker, 1)[1].split("?", 1)[0].strip("/")
        if not asset_path:
            raise ValidationException("Unsupported image URL", {"url": url})
        parts = asset_path.split("/")
        if parts and re.fullmatch(r"v\d+", parts[0]):
            parts = parts[1:]
        if not parts:
            raise ValidationException("Unsupported image URL", {"url": url})
        public_id_with_extension = "/".join(parts)
        suffix = Path(public_id_with_extension).suffix
        if suffix:
            public_id_with_extension = public_id_with_extension[: -len(suffix)]
        return public_id_with_extension

    def _normalize_lookup(self, *, key: str | None = None, url: str | None = None) -> tuple[str, str]:
        normalized_key = str(key or "").strip().lstrip("/")
        if not normalized_key:
            normalized_url = str(url or "").strip()
            if not normalized_url:
                raise ValidationException("Either key or url is required")
            normalized_key = self._extract_key_from_url(normalized_url)
        normalized_url = str(self.resolve_public_url(url or normalized_key) or "").strip()
        return normalized_key, normalized_url

    @staticmethod
    def _is_retryable_upload_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(marker in message for marker in RETRYABLE_UPLOAD_ERROR_MESSAGES)

    @staticmethod
    def _resolve_uploaded_url(upload_result: dict) -> str:
        secure_url = str(upload_result.get("secure_url") or "").strip()
        if secure_url:
            return secure_url
        fallback_url = str(upload_result.get("url") or "").strip()
        if fallback_url:
            return fallback_url
        raise ValidationException("Cloudinary upload did not return a public URL")

    def _upload_sync(
        self,
        *,
        content_type: str,
        extension: str,
        file_bytes: bytes,
        prefix: str,
        original_file_name: str | None,
    ) -> UploadedImage:
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
        upload_name = Path(original_file_name or f"upload{extension}").name

        cloudinary.config(
            cloud_name=self.settings.cloudinary_cloud_name,
            api_key=self.settings.cloudinary_api_key,
            api_secret=self.settings.cloudinary_api_secret,
            secure=True,
        )

        upload_stream = BytesIO(file_bytes)
        upload_stream.name = upload_name

        upload_result: dict | None = None
        last_error: Exception | None = None
        for attempt in range(1, MAX_UPLOAD_ATTEMPTS + 1):
            try:
                upload_stream.seek(0)
                upload_result = cloudinary.uploader.upload(
                    upload_stream,
                    folder=asset_folder or None,
                    public_id=public_id,
                    resource_type="image",
                    filename=upload_name,
                    use_filename=False,
                )
                break
            except Exception as exc:
                last_error = exc
                if attempt >= MAX_UPLOAD_ATTEMPTS or not self._is_retryable_upload_error(exc):
                    raise ValidationException(
                        "Image upload failed",
                        {"provider": "cloudinary", "reason": str(exc)},
                    ) from exc
                sleep(0.5 * attempt)

        if upload_result is None:
            raise ValidationException(
                "Image upload failed",
                {"provider": "cloudinary", "reason": str(last_error) if last_error else "unknown"},
            )

        uploaded_public_id = str(upload_result.get("public_id") or "").strip()
        uploaded_url = self._resolve_uploaded_url(upload_result)
        if not uploaded_public_id or not uploaded_url:
            raise ValidationException("Cloudinary upload did not return a valid asset reference")

        return UploadedImage(url=uploaded_url, key=uploaded_public_id)

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
            original_file_name=file.filename,
        )

    def _get_upload_status_sync(self, *, key: str, url: str) -> UploadedImageStatus:
        self._validate_config()
        try:
            import cloudinary
            import cloudinary.api
        except ImportError as exc:  # pragma: no cover - dependency issue
            raise ValidationException("cloudinary is required for image uploads") from exc

        cloudinary.config(
            cloud_name=self.settings.cloudinary_cloud_name,
            api_key=self.settings.cloudinary_api_key,
            api_secret=self.settings.cloudinary_api_secret,
            secure=True,
        )

        try:
            resource = cloudinary.api.resource(key, resource_type="image")
        except Exception as exc:
            message = str(exc).lower()
            if "not found" in message or "404" in message:
                return UploadedImageStatus(exists=False, key=key, url=url)
            raise ValidationException(
                "Image status check failed",
                {"provider": "cloudinary", "reason": str(exc), "key": key},
            ) from exc

        secure_url = str(resource.get("secure_url") or url).strip() or url
        return UploadedImageStatus(exists=True, key=key, url=secure_url)

    async def get_upload_status(self, *, key: str | None = None, url: str | None = None) -> UploadedImageStatus:
        normalized_key, normalized_url = self._normalize_lookup(key=key, url=url)
        return await run_in_threadpool(
            self._get_upload_status_sync,
            key=normalized_key,
            url=normalized_url,
        )


class S3ImageStorageService(ImageStorageService):
    def _validate_config(self) -> None:
        missing = [
            name
            for name, value in {
                "AWS_ACCESS_KEY_ID": self.settings.aws_access_key_id,
                "AWS_SECRET_ACCESS_KEY": self.settings.aws_secret_access_key,
                "AWS_S3_BUCKET": self.settings.aws_s3_bucket,
                "AWS_REGION": self.settings.aws_region,
            }.items()
            if not value
        ]
        if missing:
            missing_label = ", ".join(missing)
            raise ValidationException(
                f"AWS S3 image upload settings are incomplete: {missing_label}",
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
        bucket = (self.settings.aws_s3_bucket or "").strip()
        region = (self.settings.aws_region or "").strip()
        normalized_key = key.lstrip("/")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{normalized_key}"

    def resolve_public_url(self, value: str | None) -> str | None:
        if not value:
            return value
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return self._build_public_url(value)

    @staticmethod
    def _extract_key_from_url(url: str) -> str:
        if ".amazonaws.com/" not in url:
            raise ValidationException("Unsupported image URL", {"url": url})
        asset_path = url.split(".amazonaws.com/", 1)[1].split("?", 1)[0].strip("/")
        if not asset_path:
            raise ValidationException("Unsupported image URL", {"url": url})
        return asset_path

    def _normalize_lookup(self, *, key: str | None = None, url: str | None = None) -> tuple[str, str]:
        normalized_key = str(key or "").strip().lstrip("/")
        if not normalized_key:
            normalized_url = str(url or "").strip()
            if not normalized_url:
                raise ValidationException("Either key or url is required")
            normalized_key = self._extract_key_from_url(normalized_url)
        normalized_url = str(self.resolve_public_url(url or normalized_key) or "").strip()
        return normalized_key, normalized_url

    @staticmethod
    def _is_retryable_upload_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(marker in message for marker in RETRYABLE_UPLOAD_ERROR_MESSAGES)

    def _build_object_key(self, *, prefix: str, extension: str) -> str:
        safe_prefix = prefix.strip("/").replace(" ", "-")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{safe_prefix}/{timestamp}-{uuid4().hex}{extension or '.jpg'}"

    def _create_client(self):
        try:
            import boto3  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency issue
            raise ValidationException("boto3 is required for AWS S3 image uploads") from exc
        return boto3.client(
            "s3",
            region_name=self.settings.aws_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
        )

    def _upload_sync(
        self,
        *,
        content_type: str,
        extension: str,
        file_bytes: bytes,
        prefix: str,
    ) -> UploadedImage:
        self._validate_config()
        object_key = self._build_object_key(prefix=prefix, extension=extension)
        s3_client = self._create_client()
        last_error: Exception | None = None

        for attempt in range(1, MAX_UPLOAD_ATTEMPTS + 1):
            try:
                s3_client.put_object(
                    Bucket=self.settings.aws_s3_bucket,
                    Key=object_key,
                    Body=file_bytes,
                    ContentType=content_type,
                )
                return UploadedImage(url=self._build_public_url(object_key), key=object_key)
            except Exception as exc:
                last_error = exc
                if attempt >= MAX_UPLOAD_ATTEMPTS or not self._is_retryable_upload_error(exc):
                    raise ValidationException(
                        "Image upload failed",
                        {"provider": "aws_s3", "reason": str(exc)},
                    ) from exc
                sleep(0.5 * attempt)

        raise ValidationException(
            "Image upload failed",
            {"provider": "aws_s3", "reason": str(last_error) if last_error else "unknown"},
        )

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

    def _get_upload_status_sync(self, *, key: str, url: str) -> UploadedImageStatus:
        self._validate_config()
        s3_client = self._create_client()
        try:
            s3_client.head_object(Bucket=self.settings.aws_s3_bucket, Key=key)
        except Exception as exc:
            message = str(exc).lower()
            if "not found" in message or "404" in message or "nosuchkey" in message:
                return UploadedImageStatus(exists=False, key=key, url=url)
            raise ValidationException(
                "Image status check failed",
                {"provider": "aws_s3", "reason": str(exc), "key": key},
            ) from exc
        return UploadedImageStatus(exists=True, key=key, url=url)

    async def get_upload_status(self, *, key: str | None = None, url: str | None = None) -> UploadedImageStatus:
        normalized_key, normalized_url = self._normalize_lookup(key=key, url=url)
        return await run_in_threadpool(
            self._get_upload_status_sync,
            key=normalized_key,
            url=normalized_url,
        )


class DummyImageStorageService(S3ImageStorageService):
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
        return UploadedImage(url=self._build_public_url(key), key=key)

    async def get_upload_status(self, *, key: str | None = None, url: str | None = None) -> UploadedImageStatus:
        normalized_key, normalized_url = self._normalize_lookup(key=key, url=url)
        exists = "missing" not in normalized_key.lower()
        return UploadedImageStatus(exists=exists, key=normalized_key, url=normalized_url)


def build_image_storage_service(settings: Settings) -> ImageStorageService:
    if settings.testing:
        return DummyImageStorageService(settings)
    if all(
        (
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
            settings.aws_s3_bucket,
            settings.aws_region,
        )
    ):
        return S3ImageStorageService(settings)
    return CloudinaryImageStorageService(settings)
