"""
M1 — API Gateway: Photo Serving Route
=======================================
Serves individual photos by their storage key.

Used only by local storage backend — Cloudinary/S3 return direct CDN URLs.

Route:
    GET /api/photos/{event_id}/{photo_id}.{ext}
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.storage.local_storage import LocalStorage
from backend.config import LOCAL_UPLOAD_DIR

router = APIRouter(prefix="/api/photos", tags=["photos"])


@router.get("/{event_id}/{filename}")
async def serve_photo(event_id: str, filename: str):
    """
    Serves a photo file from local storage.

    This endpoint is only active when STORAGE_BACKEND=local.
    In production with Cloudinary, photo URLs point directly to CDN.

    Args:
        event_id: Event directory.
        filename: Photo filename (photo_id + extension).
    """
    storage_key = f"{event_id}/{filename}"

    try:
        file_path = LocalStorage.get_photo_path(storage_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Photo not found")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Photo not found")

    return FileResponse(
        path=str(file_path),
        media_type="image/jpeg",    # FastAPI infers from extension if None
        filename=filename,
    )
