"""
M2 — Storage Module (Storage Service Interface)
=================================================
The single interface all other modules use for file I/O.
No other module touches file paths or Cloudinary/S3 directly.

The backend is selected by STORAGE_BACKEND in config.py:
  - "local"      → LocalStorage (default, no external deps)
  - "cloudinary" → CloudinaryStorage (production)

Usage:
    from backend.storage import StorageService
    photo_id = await StorageService.save_photo(photo_bytes, event_id, filename)
    url = StorageService.get_photo_url(photo_id)
"""

from backend.config import STORAGE_BACKEND

if STORAGE_BACKEND == "cloudinary":
    from backend.storage.cloud_storage import CloudinaryStorage as _Backend
else:
    from backend.storage.local_storage import LocalStorage as _Backend

# StorageService is whatever backend is configured — same interface either way
StorageService = _Backend
