"""
M1 — API Gateway: Event Routes
================================
Handles event lifecycle: create, upload photos, check status, delete.

Routes:
    POST /api/events/create
    POST /api/events/{event_id}/upload
    GET  /api/events/{event_id}/status
    DELETE /api/events/{event_id}
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.database import crud
from backend.database.models import EventStatus
from backend.storage import StorageService
from backend.ingestion.tasks import process_album_task
from backend.ingestion.batch_processor import extract_images_from_zip
from backend.config import MAX_UPLOAD_SIZE_MB

router = APIRouter(prefix="/api/events", tags=["events"])
logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_event(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new event album.

    Request body: ?name=Summer+Wedding+2024

    Response:
        {
          "event_id": "uuid",
          "share_token": "abc123",
          "share_link": "/event/abc123"
        }
    """
    event = await crud.create_event(db, name=name)
    logger.info(f"Created event: {event.id} — '{event.name}'")

    return {
        "event_id": event.id,
        "share_token": event.share_token,
        "share_link": f"/event/{event.share_token}",
    }


@router.post("/{event_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_photos(
    event_id: str,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts photo uploads (individual files or a single ZIP).
    Saves them to storage, records in DB, fires Celery processing task.

    Request: multipart/form-data, field "files"
    Accepts: multiple .jpg/.png/.webp files OR a single .zip

    Response:
        {
          "status": "processing",
          "queued_photos": 42,
          "message": "..."
        }
    """
    event = await crud.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == EventStatus.deleted:
        raise HTTPException(status_code=410, detail="Event has been deleted")

    photos_to_process = []    # [{"photo_id": ..., "storage_key": ...}]

    for upload_file in files:
        file_bytes = await upload_file.read()

        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{upload_file.filename}' exceeds {MAX_UPLOAD_SIZE_MB}MB limit"
            )

        # Handle ZIP extraction
        if upload_file.filename.lower().endswith(".zip"):
            try:
                for img_name, img_bytes in extract_images_from_zip(file_bytes):
                    photo_info = await _save_and_record(db, img_bytes, event_id, img_name)
                    photos_to_process.append(photo_info)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
        else:
            photo_info = await _save_and_record(db, file_bytes, event_id, upload_file.filename)
            photos_to_process.append(photo_info)

    if not photos_to_process:
        raise HTTPException(status_code=422, detail="No valid photos found in upload")

    # Update event status to "processing"
    await crud.set_event_status(db, event_id, EventStatus.processing)

    # Fire background Celery task — returns immediately
    process_album_task.delay(event_id, photos_to_process)

    logger.info(f"Queued {len(photos_to_process)} photos for event {event_id}")

    return {
        "status": "processing",
        "queued_photos": len(photos_to_process),
        "message": "Photos uploaded successfully. Processing in background.",
    }


@router.get("/{event_id}/status")
async def get_event_status(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the current processing status of an event.
    Frontend polls this endpoint every 5s after upload.

    Response:
        {
          "event_id": "uuid",
          "status": "processing" | "ready" | "uploading",
          "share_link": "/event/abc123"   ← only present when status=ready
        }
    """
    event = await crud.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    response = {
        "event_id": event.id,
        "status": event.status.value,
    }
    if event.status == EventStatus.ready:
        response["share_link"] = f"/event/{event.share_token}"

    return response


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes all photos for an event (privacy cleanup).
    Marks event as deleted in DB. FAISS index is also removed.
    """
    event = await crud.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Delete files from storage
    StorageService.delete_event_photos(event_id)

    # Remove FAISS index files
    from backend.config import FAISS_INDEX_DIR
    for ext in [".index", ".json"]:
        index_file = FAISS_INDEX_DIR / f"{event_id}{ext}"
        if index_file.exists():
            index_file.unlink()

    await crud.set_event_status(db, event_id, EventStatus.deleted)
    logger.info(f"Event {event_id} deleted — all photos purged")


# ── Internal helper ────────────────────────────────────────────────────────────

async def _save_and_record(
    db: AsyncSession,
    image_bytes: bytes,
    event_id: str,
    filename: str,
) -> dict:
    """Saves one image to storage + records it in DB. Returns serializable dict."""
    storage_key = await StorageService.save_photo(image_bytes, event_id, filename)
    photo = await crud.record_photo(db, event_id=event_id, storage_key=storage_key)
    return {"photo_id": photo.id, "storage_key": storage_key}
