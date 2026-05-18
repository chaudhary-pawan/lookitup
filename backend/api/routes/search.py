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
from backend.config import SIMILARITY_CONFIDENT
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

    # ── Step 3: Search using pgvector (M4) ────────────────────────────────────
    query_embedding_list = query_embedding.tolist()
    search_results = await crud.search_photos_by_embedding(
        db, 
        event.id, 
        query_embedding_list, 
        limit=50
    )

    if not search_results:
        return {
            "event_id": event.id,
            "query_face_detected": True,
            "results": {"confident": [], "possible": []},
            "total_matches": 0,
        }

    # ── Step 4: Build response with storage URLs (M2) ─────────────────────────
    confident_results = []
    possible_results = []

    for photo, similarity in search_results:
        url = StorageService.get_photo_url(photo.storage_key)
        thumb_url = StorageService.get_photo_url(photo.thumbnail_key) if photo.thumbnail_key else url
        
        entry = {
            "photo_id": photo.id,
            "url": url,
            "thumbnail_url": thumb_url,
            "score": round(similarity, 4),
        }

        if similarity >= SIMILARITY_CONFIDENT:
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
