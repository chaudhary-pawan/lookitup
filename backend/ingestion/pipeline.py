"""
M3 — Ingestion Pipeline (Core Orchestrator)
=============================================
Wires M2 (Storage) + M5 (Face Engine) + M6 (Vector Index) + M4 (DB) together.

This module runs as a background Celery task — it does NOT run in the FastAPI
request/response cycle. The API fires it off and returns immediately.

Flow per event:
    1. API uploads photos → M2 saves them → M4 records them
    2. API fires process_album_task.delay(event_id) → this module takes over
    3. For each photo:
         a. Get bytes from M2
         b. Detect + embed all faces with M5
         c. Add embeddings to M6 FAISS index
         d. Mark photo processed in M4
    4. Persist FAISS index to disk (M6)
    5. Mark event as "ready" in M4
"""

import logging
from typing import List, Tuple, Optional
from io import BytesIO
from PIL import Image

from backend.storage import StorageService
from backend.face_engine import FaceEngine

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Synchronous pipeline that processes one photo at a time.

    Designed to run inside a Celery worker (sync context).
    Uses synchronous StorageService.get_photo_bytes() — no asyncio needed here.
    """

    def process_single_photo(
        photo_id: str,
        storage_key: str,
        event_id: str,
    ) -> Tuple[int, str, Optional[list]]:
        """
        Processes one photo: generate thumbnail → detect faces → extract embedding.

        Args:
            photo_id:    DB identifier for this photo.
            storage_key: M2 storage key to retrieve file bytes.
            event_id:    Which event this photo belongs to.

        Returns:
            Tuple of (face_count, thumbnail_key, first_face_embedding)

        Note:
            DB updates (mark_photo_processed) are done in tasks.py
            after this returns, to keep pipeline logic clean.
        """
        logger.info(f"Processing photo {photo_id} for event {event_id}")

        # Step 1: Get photo bytes from storage
        photo_bytes = StorageService.get_photo_bytes(storage_key)

        # Step 1.5: Generate WebP Thumbnail
        with Image.open(BytesIO(photo_bytes)) as img:
            # Convert to RGB if necessary
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((400, 400)) # Maximum 400px
            thumb_io = BytesIO()
            img.save(thumb_io, format="WEBP", quality=80)
            thumb_bytes = thumb_io.getvalue()
        
        # Save thumbnail synchronously using asyncio.run since we are in a sync pipeline method
        # Wait, StorageService.save_photo is async.
        # But we are in a sync function. We must use asyncio.run to call it.
        import asyncio
        thumb_filename = f"thumb_{photo_id}.webp"
        thumbnail_key = asyncio.run(StorageService.save_photo(thumb_bytes, event_id, thumb_filename))

        # Step 2: Detect all faces + extract embeddings (M5)
        face_embeddings = FaceEngine.detect_and_embed(photo_bytes)
        face_count = len(face_embeddings)
        first_embedding = face_embeddings[0].vector.tolist() if face_count > 0 else None

        if face_count == 0:
            logger.info(f"No faces found in photo {photo_id} — skipping index update")
            return 0, thumbnail_key, None

        logger.info(f"Found {face_count} face(s) in photo {photo_id}")

        return face_count, thumbnail_key, first_embedding
