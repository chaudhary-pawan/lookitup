"""
M2 — Local Storage Backend
============================
Saves files to the local filesystem under backend/uploads/{event_id}/.

This is the default backend for development and demo.
No external dependencies required — works out of the box.

To switch to Cloudinary for production: set STORAGE_BACKEND=cloudinary in .env
"""

import uuid
import aiofiles
from pathlib import Path
from typing import Optional

import backend.config as cfg
from backend.config import ALLOWED_IMAGE_EXTENSIONS


class LocalStorage:
    """
    Stores photos on the local filesystem.
    Photos are organized by event: uploads/{event_id}/{photo_id}.{ext}
    """

    @staticmethod
    async def save_photo(
        photo_bytes: bytes,
        event_id: str,
        original_filename: str,
    ) -> str:
        """
        Saves a photo to disk.

        Called by: M1 API Gateway (during photo upload)

        Args:
            photo_bytes:       Raw image bytes.
            event_id:          Organizes photos into per-event directories.
            original_filename: Used only to preserve the file extension.

        Returns:
            storage_key: A unique identifier for this photo.
                         For LocalStorage: relative path like "{event_id}/{photo_id}.jpg"
                         This key is stored in M4 DB and used to retrieve the file later.
        """
        suffix = Path(original_filename).suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {suffix}")

        photo_id = str(uuid.uuid4())
        event_dir = cfg.LOCAL_UPLOAD_DIR / event_id
        event_dir.mkdir(parents=True, exist_ok=True)

        file_path = event_dir / f"{photo_id}{suffix}"

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(photo_bytes)

        # storage_key is relative to LOCAL_UPLOAD_DIR — portable
        return f"{event_id}/{photo_id}{suffix}"

    @staticmethod
    def get_photo_url(storage_key: str) -> str:
        """
        Returns the URL to serve the photo.

        For local storage: this is an API endpoint path.
        The actual file serving is handled by M1 (StaticFiles or /photos/ route).

        Args:
            storage_key: The key returned by save_photo().

        Returns:
            URL string the frontend can use to display the photo.
        """
        return f"/api/photos/{storage_key}"

    @staticmethod
    def get_photo_bytes(storage_key: str) -> bytes:
        """
        Reads and returns raw photo bytes from disk.

        Called by: M3 Ingestion Pipeline (to process photos)
        This is synchronous intentionally — Celery tasks run in worker threads.
        """
        file_path = cfg.LOCAL_UPLOAD_DIR / storage_key
        if not file_path.exists():
            raise FileNotFoundError(f"Photo not found: {storage_key}")

        return file_path.read_bytes()

    @staticmethod
    def get_photo_path(storage_key: str) -> Path:
        """Returns the absolute Path to the file. Used by FastAPI StaticFiles."""
        return cfg.LOCAL_UPLOAD_DIR / storage_key

    @staticmethod
    def delete_event_photos(event_id: str) -> None:
        """
        Deletes all photos for an event.

        Called by: M1 API Gateway → DELETE /events/{event_id}
        Privacy-first: organizer can wipe all photos after the event.
        """
        import shutil
        event_dir = cfg.LOCAL_UPLOAD_DIR / event_id
        if event_dir.exists():
            shutil.rmtree(event_dir)
