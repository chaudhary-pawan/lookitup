"""
M3 — Batch Processor
======================
Handles ZIP extraction and file batching before ingestion.

When an organizer uploads a ZIP file of event photos, this module:
1. Extracts all supported image files from the ZIP
2. Yields them as (filename, bytes) pairs for the API to save + queue
"""

import io
import zipfile
from typing import Iterator, Tuple

from backend.config import ALLOWED_IMAGE_EXTENSIONS


def extract_images_from_zip(zip_file_or_path):
    """
    Extracts all image files from a ZIP archive.

    Called by: M1 API Gateway (when organizer uploads a ZIP file)
    Also called by: unit tests (which pass raw bytes)

    Args:
        zip_file_or_path: Path to the ZIP file (str) OR raw ZIP bytes / file-like object.

    Yields:
        (filename, file_like_object) tuples for each supported image found.

    Raises:
        ValueError: If the file is not a valid ZIP archive.
        ValueError: If the ZIP contains no supported images.
    """
    if isinstance(zip_file_or_path, bytes):
        zip_file_or_path = io.BytesIO(zip_file_or_path)

    if not zipfile.is_zipfile(zip_file_or_path):
        raise ValueError("Uploaded file is not a valid ZIP archive.")

    found_count = 0

    with zipfile.ZipFile(zip_file_or_path, "r") as zf:
        for name in zf.namelist():
            # Skip directories
            if name.endswith("/"):
                continue

            # Skip hidden files and macOS meta artifacts anywhere in the path
            parts = name.split('/')
            if any(p.startswith('.') or p == '__MACOSX' for p in parts):
                continue

            suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if suffix not in ALLOWED_IMAGE_EXTENSIONS:
                continue

            # We yield an open file object for the image inside the zip
            image_file = zf.open(name)
            filename = name.split("/")[-1]   # strip any subdirectory path
            yield filename, image_file
            found_count += 1

    if found_count == 0:
        raise ValueError(
            f"ZIP contains no supported image files. "
            f"Accepted formats: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )
