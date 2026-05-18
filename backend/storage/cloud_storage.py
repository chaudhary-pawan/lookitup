"""
M2 — Cloudinary Storage Backend (Production)
=============================================
Plug-in replacement for LocalStorage when STORAGE_BACKEND=cloudinary.

Implements the same interface as LocalStorage — no other module changes.

Requires:
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET in .env

Note: This is a stub. Implement when moving to production hosting.
"""

import cloudinary
import cloudinary.uploader
from io import BytesIO
from pathlib import Path

from backend.config import (
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
)

# Configure Cloudinary SDK on import
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)


class CloudinaryStorage:
    """
    Stores photos in Cloudinary.

    storage_key for Cloudinary = the Cloudinary public_id
    Format: "lookitup/{event_id}/{photo_id}"
    """

    @staticmethod
    async def save_photo(
        photo_data,
        event_id: str,
        original_filename: str,
    ) -> str:
        """Uploads photo to Cloudinary, returns public_id as storage_key."""
        import uuid
        photo_id = str(uuid.uuid4())
        public_id = f"lookitup/{event_id}/{photo_id}"

        # If it's bytes, wrap it in BytesIO. If it's a file, pass it directly.
        upload_target = BytesIO(photo_data) if isinstance(photo_data, bytes) else photo_data

        result = cloudinary.uploader.upload(
            upload_target,
            public_id=public_id,
            folder=f"lookitup/{event_id}",
            resource_type="image",
        )
        return result["public_id"]

    @staticmethod
    def get_photo_url(storage_key: str) -> str:
        """Returns a Cloudinary CDN URL for the photo."""
        return cloudinary.CloudinaryImage(storage_key).build_url(
            secure=True,
            quality="auto",
            fetch_format="auto",
        )

    @staticmethod
    def get_photo_bytes(storage_key: str) -> bytes:
        """Downloads photo bytes from Cloudinary. Used by Celery ingestion workers."""
        import requests
        url = cloudinary.CloudinaryImage(storage_key).build_url(secure=True)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content

    @staticmethod
    def get_photo_path(storage_key: str) -> Path:
        """Not applicable for cloud storage — raises NotImplementedError."""
        raise NotImplementedError("Cloud storage does not expose local file paths.")

    @staticmethod
    def delete_event_photos(event_id: str) -> None:
        """Deletes all photos in the event folder from Cloudinary."""
        cloudinary.api.delete_resources_by_prefix(f"lookitup/{event_id}/")
        cloudinary.api.delete_folder(f"lookitup/{event_id}/")
