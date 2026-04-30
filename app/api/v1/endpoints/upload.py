from __future__ import annotations

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from pydantic import BaseModel
from uuid import uuid4

from app.config.settings import get_settings
from app.core.exceptions import AuthorizationException, ValidationException
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_image_storage_service
from app.services.image_storage import IMAGE_CONTENT_TYPE_ALIASES, SUPPORTED_IMAGE_EXTENSIONS

router = APIRouter()

class UploadImageResponse(BaseModel):
    url: str
    key: str


class UploadImageStatusResponse(BaseModel):
    exists: bool
    key: str
    url: str


class AwsUploadConfigStatusResponse(BaseModel):
    provider: str = "aws_s3"
    configured: bool
    bucket: str | None = None
    region: str | None = None
    missing_fields: list[str]


class AwsImageUploadPrecheckResponse(BaseModel):
    provider: str = "aws_s3"
    configured: bool
    can_upload: bool
    file_name: str
    content_type: str
    extension: str
    size_bytes: int
    bucket: str | None = None
    region: str | None = None
    missing_fields: list[str]
    reason: str | None = None


class AwsUploadVerifyResponse(BaseModel):
    provider: str = "aws_s3"
    configured: bool
    sdk_available: bool
    bucket_accessible: bool
    write_test_passed: bool
    bucket: str | None = None
    region: str | None = None
    missing_fields: list[str]
    verification_key: str | None = None
    reason: str | None = None


def _resolve_upload_prefix(current_user: dict) -> str:
    user_id = str(current_user.get("_id") or current_user.get("id") or "unknown")
    return f"uploads/{user_id}"


def _assert_upload_ownership(*, current_user: dict, key: str) -> None:
    allowed_prefix = f"{_resolve_upload_prefix(current_user).strip('/')}/"
    normalized_key = key.strip().lstrip("/")
    if not normalized_key.startswith(allowed_prefix):
        raise AuthorizationException(
            "You do not have permission to inspect this uploaded image",
            {"key": normalized_key},
        )


def _get_aws_missing_fields() -> list[str]:
    settings = get_settings()
    required_fields = {
        "AWS_ACCESS_KEY_ID": settings.aws_access_key_id,
        "AWS_SECRET_ACCESS_KEY": settings.aws_secret_access_key,
        "AWS_S3_BUCKET": settings.aws_s3_bucket,
        "AWS_REGION": settings.aws_region,
    }
    return [field_name for field_name, field_value in required_fields.items() if not field_value]


def _resolve_image_upload_metadata(file: UploadFile) -> tuple[str, str]:
    normalized_content_type = IMAGE_CONTENT_TYPE_ALIASES.get((file.content_type or "").lower(), (file.content_type or "").lower())
    extension = ""
    if file.filename and "." in file.filename:
        extension = f".{file.filename.rsplit('.', 1)[1].lower()}"

    if normalized_content_type.startswith("image/"):
        return normalized_content_type, extension
    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        return "image/*", extension
    raise ValidationException("Only image files are supported")

@router.post('/image', response_model=UploadImageResponse, status_code=status.HTTP_201_CREATED, summary="Upload Image", description="Uploads an image to AWS S3 and returns the public URL.")
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    image_storage = Depends(get_image_storage_service)
) -> UploadImageResponse:
    prefix = _resolve_upload_prefix(current_user)
    uploaded = await image_storage.upload_file(file=file, prefix=prefix)
    return UploadImageResponse(url=uploaded.url, key=uploaded.key)


@router.get(
    '/image/status',
    response_model=UploadImageStatusResponse,
    summary="Check Image Upload Status",
    description="Checks whether a previously uploaded image exists in storage by key or URL.",
)
async def get_upload_image_status(
    key: str | None = Query(default=None),
    url: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    image_storage = Depends(get_image_storage_service),
) -> UploadImageStatusResponse:
    if not key and not url:
        raise ValidationException("Either key or url is required")
    upload_status = await image_storage.get_upload_status(key=key, url=url)
    _assert_upload_ownership(current_user=current_user, key=upload_status.key)
    return UploadImageStatusResponse(
        exists=upload_status.exists,
        key=upload_status.key,
        url=upload_status.url,
    )


@router.get(
    '/aws/config-status',
    response_model=AwsUploadConfigStatusResponse,
    summary="Check AWS Upload Configuration",
    description="Returns whether AWS S3 image upload configuration is present on the backend.",
)
async def get_aws_upload_config_status(
    _: dict = Depends(get_current_user),
) -> AwsUploadConfigStatusResponse:
    settings = get_settings()
    missing_fields = _get_aws_missing_fields()
    return AwsUploadConfigStatusResponse(
        configured=not missing_fields,
        bucket=settings.aws_s3_bucket,
        region=settings.aws_region,
        missing_fields=missing_fields,
    )


@router.post(
    '/aws/image/precheck',
    response_model=AwsImageUploadPrecheckResponse,
    summary="Precheck AWS Image Upload",
    description="Validates whether an image file is eligible for AWS S3 upload and whether AWS upload configuration is complete.",
)
async def precheck_aws_image_upload(
    file: UploadFile = File(...),
    _: dict = Depends(get_current_user),
) -> AwsImageUploadPrecheckResponse:
    settings = get_settings()
    missing_fields = _get_aws_missing_fields()
    content_type, extension = _resolve_image_upload_metadata(file)
    file_bytes = await file.read()
    if not file_bytes:
        raise ValidationException("Uploaded image is empty")

    configured = not missing_fields
    can_upload = configured and len(file_bytes) > 0
    reason = None
    if missing_fields:
        reason = f"AWS upload is not configured: {', '.join(missing_fields)}"

    return AwsImageUploadPrecheckResponse(
        configured=configured,
        can_upload=can_upload,
        file_name=file.filename or 'upload-image',
        content_type=content_type,
        extension=extension or '',
        size_bytes=len(file_bytes),
        bucket=settings.aws_s3_bucket,
        region=settings.aws_region,
        missing_fields=missing_fields,
        reason=reason,
    )


@router.post(
    '/aws/verify',
    response_model=AwsUploadVerifyResponse,
    summary="Verify AWS S3 Upload Readiness",
    description="Verifies AWS SDK availability, bucket access, and a safe write/delete cycle for S3 image uploads.",
)
async def verify_aws_image_upload_backend(
    current_user: dict = Depends(get_current_user),
) -> AwsUploadVerifyResponse:
    settings = get_settings()
    missing_fields = _get_aws_missing_fields()
    if missing_fields:
        return AwsUploadVerifyResponse(
            configured=False,
            sdk_available=False,
            bucket_accessible=False,
            write_test_passed=False,
            bucket=settings.aws_s3_bucket,
            region=settings.aws_region,
            missing_fields=missing_fields,
            reason=f"AWS upload is not configured: {', '.join(missing_fields)}",
        )

    try:
        import boto3  # type: ignore
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError  # type: ignore
    except ImportError:
        return AwsUploadVerifyResponse(
            configured=True,
            sdk_available=False,
            bucket_accessible=False,
            write_test_passed=False,
            bucket=settings.aws_s3_bucket,
            region=settings.aws_region,
            missing_fields=[],
            reason="boto3 is not installed on the backend",
        )

    bucket_name = settings.aws_s3_bucket
    region_name = settings.aws_region
    user_id = str(current_user.get("_id") or current_user.get("id") or "unknown")
    verification_key = (
        f"healthchecks/{user_id}/"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex}.txt"
    )

    try:
        s3_client = boto3.client(
            "s3",
            region_name=region_name,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        s3_client.head_bucket(Bucket=bucket_name)
    except (BotoCoreError, ClientError, NoCredentialsError) as exc:
        return AwsUploadVerifyResponse(
            configured=True,
            sdk_available=True,
            bucket_accessible=False,
            write_test_passed=False,
            bucket=bucket_name,
            region=region_name,
            missing_fields=[],
            verification_key=verification_key,
            reason=str(exc),
        )

    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=verification_key,
            Body=b"upload verification",
            ContentType="text/plain",
        )
        s3_client.delete_object(Bucket=bucket_name, Key=verification_key)
    except (BotoCoreError, ClientError, NoCredentialsError) as exc:
        return AwsUploadVerifyResponse(
            configured=True,
            sdk_available=True,
            bucket_accessible=True,
            write_test_passed=False,
            bucket=bucket_name,
            region=region_name,
            missing_fields=[],
            verification_key=verification_key,
            reason=str(exc),
        )

    return AwsUploadVerifyResponse(
        configured=True,
        sdk_available=True,
        bucket_accessible=True,
        write_test_passed=True,
        bucket=bucket_name,
        region=region_name,
        missing_fields=[],
        verification_key=verification_key,
        reason=None,
    )
