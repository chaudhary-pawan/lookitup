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
from typing import List

from backend.storage import StorageService
from backend.face_engine import FaceEngine
from backend.vector_index import VectorIndex

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Synchronous pipeline that processes one photo at a time.

    Designed to run inside a Celery worker (sync context).
    Uses synchronous StorageService.get_photo_bytes() — no asyncio needed here.
    """

    @staticmethod
    def process_single_photo(
        photo_id: str,
        storage_key: str,
        event_id: str,
    ) -> int:
        """
        Processes one photo: detect faces → embed → store in FAISS.

        Args:
            photo_id:    DB identifier for this photo.
            storage_key: M2 storage key to retrieve file bytes.
            event_id:    Which event this photo belongs to.

        Returns:
            Number of faces found in this photo.

        Note:
            DB updates (mark_photo_processed) are done in tasks.py
            after this returns, to keep pipeline logic clean.
        """
        logger.info(f"Processing photo {photo_id} for event {event_id}")

        # Step 1: Get photo bytes from storage
        photo_bytes = StorageService.get_photo_bytes(storage_key)

        # Step 2: Detect all faces + extract embeddings (M5)
        face_embeddings = FaceEngine.detect_and_embed(photo_bytes)
        face_count = len(face_embeddings)

        if face_count == 0:
            logger.info(f"No faces found in photo {photo_id} — skipping index update")
            return 0

        logger.info(f"Found {face_count} face(s) in photo {photo_id}")

        # Step 3: Add each embedding to the event's FAISS index (M6)
        for face in face_embeddings:
            VectorIndex.add(
                embedding=face.vector,
                photo_id=photo_id,
                event_id=event_id,
            )

        return face_count

    @staticmethod
    def finalize_event(event_id: str) -> None:
        """
        Persists the FAISS index to disk after all photos are processed.

        Called by tasks.py after the photo loop completes.
        After this, the event is ready for attendee queries.
        """
        VectorIndex.save_index(event_id)
        logger.info(f"FAISS index for event {event_id} saved to disk")
