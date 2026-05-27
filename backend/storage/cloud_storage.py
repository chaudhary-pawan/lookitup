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
import cloudinary.api
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
        import io
        from PIL import Image
        import logging

        logger = logging.getLogger(__name__)
        photo_id = str(uuid.uuid4())
        public_id = f"lookitup/{event_id}/{photo_id}"

        # Get bytes from input
        if isinstance(photo_data, bytes):
            img_bytes = photo_data
        else:
            # File-like object (e.g., SpooledTemporaryFile or UploadFile.file)
            photo_data.seek(0)
            img_bytes = photo_data.read()
            photo_data.seek(0)

        # Cloudinary free tier limit is 10MB. Proactively compress if close (>9.5MB)
        MAX_SIZE_BYTES = 9.5 * 1024 * 1024
        if len(img_bytes) > MAX_SIZE_BYTES:
            logger.info(f"Image {original_filename} ({len(img_bytes)} bytes) exceeds Cloudinary free limit. Compressing...")
            try:
                img = Image.open(io.BytesIO(img_bytes))
                
                # Downscale if extremely large (e.g., > 2048px on the longest side)
                max_dim = 2048
                width, height = img.size
                if max(width, height) > max_dim:
                    if width > height:
                        new_width = max_dim
                        new_height = int(height * (max_dim / width))
                    else:
                        new_height = max_dim
                        new_width = int(width * (max_dim / height))
                    
                    resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
                    img = img.resize((new_width, new_height), resample_filter)
                    logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")

                # Save as JPEG with compression
                output = io.BytesIO()
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output, format="JPEG", quality=85, optimize=True)
                img_bytes = output.getvalue()
                logger.info(f"Compression finished. New size: {len(img_bytes)} bytes.")
            except Exception as e:
                logger.warning(f"Failed to compress image {original_filename}: {e}. Uploading original.")

        upload_target = io.BytesIO(img_bytes)

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
        try:
            cloudinary.api.delete_resources_by_prefix(f"lookitup/{event_id}/")
            cloudinary.api.delete_folder(f"lookitup/{event_id}/")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to delete Cloudinary resources for {event_id}: {e}")
