from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_image_storage_service

router = APIRouter()

class UploadImageResponse(BaseModel):
    url: str
    key: str

@router.post('/image', response_model=UploadImageResponse, status_code=status.HTTP_201_CREATED, summary="Upload Image", description="Uploads an image to Cloudinary and returns the public URL.")
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    image_storage = Depends(get_image_storage_service)
) -> UploadImageResponse:
    user_id = current_user.get("sub", "unknown")
    prefix = f"uploads/{user_id}"
    uploaded = await image_storage.upload_file(file=file, prefix=prefix)
    return UploadImageResponse(url=uploaded.url, key=uploaded.key)
