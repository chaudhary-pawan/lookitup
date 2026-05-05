"""
M1 — API Gateway: Search Route
================================
Handles the attendee selfie search.

Route:
    POST /api/events/{share_token}/search   (multipart: selfie image)

This is the "magic" endpoint — it's what makes LookItUp work:
  1. Extract face embedding from selfie (M5)
  2. Search FAISS index for similar faces (M6)
  3. Fetch photo metadata from DB (M4)
  4. Fetch photo URLs from storage (M2)
  5. Return tiered results (confident / possible)
"""

import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.database import crud
from backend.database.models import EventStatus
from backend.face_engine import FaceEngine, NoFaceDetectedError, MultipleFacesError
from backend.vector_index import VectorIndex
from backend.storage import StorageService

router = APIRouter(prefix="/api/events", tags=["search"])
logger = logging.getLogger(__name__)


@router.post("/{share_token}/search")
async def search_photos(
    share_token: str,
    selfie: UploadFile = File(..., description="Selfie photo — must contain exactly one face"),
    db: AsyncSession = Depends(get_db),
):
    """
    Finds all event photos containing the face in the submitted selfie.

    Args:
        share_token: The event's public share token (from the link).
        selfie:      Uploaded selfie image file.

    Response:
        {
          "event_id": "uuid",
          "query_face_detected": true,
          "results": {
            "confident": [{"photo_id": "...", "url": "...", "score": 0.89}],
            "possible":  [{"photo_id": "...", "url": "...", "score": 0.63}]
          },
          "total_matches": 5
        }
    """
    # ── Step 1: Validate event ─────────────────────────────────────────────────
    event = await crud.get_event_by_token(db, share_token)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status != EventStatus.ready:
        raise HTTPException(
            status_code=425,
            detail=f"Event is not ready yet (status: {event.status.value}). "
                   "Please wait for processing to complete."
        )

    # ── Step 2: Extract face embedding from selfie (M5) ───────────────────────
    selfie_bytes = await selfie.read()

    try:
        query_embedding = FaceEngine.embed_single(selfie_bytes)
    except NoFaceDetectedError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except MultipleFacesError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Face embedding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process selfie image.")

    # ── Step 3: Search FAISS index (M6) ───────────────────────────────────────
    try:
        search_results = VectorIndex.search(
            query_embedding=query_embedding,
            event_id=event.id,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Event index not found. Ingestion may have failed."
        )

    if not search_results:
        return {
            "event_id": event.id,
            "query_face_detected": True,
            "results": {"confident": [], "possible": []},
            "total_matches": 0,
        }

    # ── Step 4: Fetch photo metadata from DB (M4) ─────────────────────────────
    photo_ids = [r.photo_id for r in search_results]
    photos = await crud.get_photos_by_ids(db, photo_ids)
    photo_map = {p.id: p for p in photos}

    # ── Step 5: Build response with storage URLs (M2) ─────────────────────────
    confident_results = []
    possible_results = []

    for result in search_results:
        photo = photo_map.get(result.photo_id)
        if not photo:
            continue  # photo may have been deleted

        url = StorageService.get_photo_url(photo.storage_key)
        entry = {
            "photo_id": result.photo_id,
            "url": url,
            "score": round(result.similarity, 4),
        }

        if result.tier == "confident":
            confident_results.append(entry)
        else:
            possible_results.append(entry)

    total = len(confident_results) + len(possible_results)
    logger.info(
        f"Search complete: event={event.id}, "
        f"confident={len(confident_results)}, possible={len(possible_results)}"
    )

    return {
        "event_id": event.id,
        "query_face_detected": True,
        "results": {
            "confident": confident_results,
            "possible": possible_results,
        },
        "total_matches": total,
    }
