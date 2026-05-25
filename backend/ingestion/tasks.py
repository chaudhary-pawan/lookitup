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

    Returns:
        Summary dict: {processed: int, skipped: int, total_faces: int}
    """
    return asyncio.run(_process_album_async(self, event_id, photos))


async def _process_album_async(
    self,
    event_id: str,
    photos: List[Dict],
) -> Dict:
    # Import here to avoid circular imports at module load time
    from backend.database.db import AsyncSessionLocal
    from backend.database import crud
    from backend.database.models import EventStatus

    processed_count = 0
    skipped_count = 0
    total_faces = 0

    logger.info(f"Starting album processing: event={event_id}, photos={len(photos)}")

    async with AsyncSessionLocal() as db:
        for photo_data in photos:
            photo_id = photo_data["photo_id"]
            storage_key = photo_data["storage_key"]

            try:
                face_count, thumbnail_key, embeddings = await IngestionPipeline.process_single_photo(
                    photo_id=photo_id,
                    storage_key=storage_key,
                    event_id=event_id,
                )

                # Update DB asynchronously in the open session
                await crud.mark_photo_processed_with_faces(
                    db,
                    photo_id=photo_id,
                    face_count=face_count,
                    thumbnail_key=thumbnail_key,
                    embeddings=embeddings
                )
                processed_count += 1
                total_faces += face_count

            except Exception as exc:
                logger.error(f"Failed to process photo {photo_id}: {exc}", exc_info=True)
                skipped_count += 1
                # Don't re-raise — one bad photo shouldn't abort the whole album
                continue

        # Mark event ready
        try:
            await crud.set_event_status(db, event_id, EventStatus.ready)
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
