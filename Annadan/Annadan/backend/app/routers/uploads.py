"""Authenticated image upload endpoint backed by Cloudinary."""

from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.dependencies import require_roles
from app.models.entities import User
from app.models.enums import UserRole

router = APIRouter(prefix="/uploads", tags=["Media uploads"])
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/donation-image", status_code=status.HTTP_201_CREATED)
async def upload_donation_image(
    image: UploadFile = File(...),
    _donor: User = Depends(require_roles(UserRole.DONOR)),
):
    if not settings.cloudinary_url:
        raise HTTPException(status_code=503, detail="Food image storage is not configured yet.")
    if image.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")

    content = await image.read(settings.upload_max_bytes + 1)
    if not content or len(content) > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB.")
    try:
        with Image.open(BytesIO(content)) as decoded:
            decoded.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid image.")

    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(cloudinary_url=settings.cloudinary_url, secure=True)
        result = cloudinary.uploader.upload(
            BytesIO(content),
            folder=settings.cloudinary_folder,
            public_id=f"donation-{uuid4().hex}",
            resource_type="image",
            overwrite=False,
            allowed_formats=["jpg", "jpeg", "png", "webp"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Image storage could not process the upload.") from exc

    return {"image_url": result["secure_url"], "public_id": result["public_id"]}
