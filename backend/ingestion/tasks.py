"""
M3 — Ingestion Celery Tasks
=============================
Celery task definitions. These are the entry points for background processing.

The API Gateway calls: process_album_task.delay(event_id, photo_data)
Celery picks it up and runs it in a worker process.

Why Celery?
- Face detection + embedding extraction takes ~0.5–2s per photo
- For a 200-photo album, that's 100–400 seconds total
- This CANNOT run synchronously in an API request (client would timeout)
- Celery runs it in the background; API returns immediately with "processing"
"""

import logging
from typing import List, Dict
import asyncio

from backend.celery_app import celery_app
from backend.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


@celery_app.task(
    name="ingestion.process_album",
    bind=True,
    max_retries=3,
    default_retry_delay=60,    # retry after 60s if worker crashes
    acks_late=True,            # only ack after task completes (safer)
)
def process_album_task(
    self,
    event_id: str,
    photos: List[Dict],        # List of {"photo_id": str, "storage_key": str}
) -> Dict:
    """
    Background task: processes all photos in an event album.

    Args:
        event_id: The event to process.
        photos:   List of {"photo_id": ..., "storage_key": ...} dicts
                  (passed as JSON-serializable dict — no ORM objects in tasks)

    Returns:
        Summary dict: {processed: int, skipped: int, total_faces: int}

    Workflow:
        For each photo:
          1. IngestionPipeline.process_single_photo() → face detection + FAISS
          2. Mark photo as processed in DB
        After all photos:
          3. IngestionPipeline.finalize_event() → save FAISS index to disk
          4. Mark event as "ready" in DB
    """
    # Import here to avoid circular imports at module load time
    from backend.database.db import AsyncSessionLocal
    from backend.database import crud
    from backend.database.models import EventStatus

    processed_count = 0
    skipped_count = 0
    total_faces = 0

    logger.info(f"Starting album processing: event={event_id}, photos={len(photos)}")

    for photo_data in photos:
        photo_id = photo_data["photo_id"]
        storage_key = photo_data["storage_key"]

        try:
            face_count = IngestionPipeline.process_single_photo(
                photo_id=photo_id,
                storage_key=storage_key,
                event_id=event_id,
            )

            # Update DB synchronously using asyncio.run (we're in a sync Celery worker)
            asyncio.run(_mark_processed(photo_id, face_count))
            processed_count += 1
            total_faces += face_count

        except Exception as exc:
            logger.error(f"Failed to process photo {photo_id}: {exc}", exc_info=True)
            skipped_count += 1
            # Don't re-raise — one bad photo shouldn't abort the whole album
            continue

    # Persist FAISS index and mark event ready
    try:
        IngestionPipeline.finalize_event(event_id)
        asyncio.run(_mark_event_ready(event_id))
    except Exception as exc:
        logger.error(f"Failed to finalize event {event_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)

    summary = {
        "event_id": event_id,
        "processed": processed_count,
        "skipped": skipped_count,
        "total_faces": total_faces,
    }
    logger.info(f"Album processing complete: {summary}")
    return summary


# ── Async helpers (run inside sync Celery worker via asyncio.run) ──────────────

async def _mark_processed(photo_id: str, face_count: int) -> None:
    from backend.database.db import AsyncSessionLocal
    from backend.database import crud
    async with AsyncSessionLocal() as db:
        await crud.mark_photo_processed(db, photo_id, face_count)


async def _mark_event_ready(event_id: str) -> None:
    from backend.database.db import AsyncSessionLocal
    from backend.database import crud
    from backend.database.models import EventStatus
    async with AsyncSessionLocal() as db:
        await crud.set_event_status(db, event_id, EventStatus.ready)
