"""
M3 — Batch Processor
======================
Handles ZIP extraction and file batching before ingestion.

When an organizer uploads a ZIP file of event photos, this module:
1. Extracts all supported image files from the ZIP
2. Yields them as (filename, bytes) pairs for the API to save + queue
"""

import zipfile
from io import BytesIO
from typing import Iterator, Tuple

from backend.config import ALLOWED_IMAGE_EXTENSIONS


def extract_images_from_zip(zip_bytes: bytes) -> Iterator[Tuple[str, bytes]]:
    """
    Extracts all image files from a ZIP archive.

    Called by: M1 API Gateway (when organizer uploads a ZIP file)

    Args:
        zip_bytes: Raw bytes of the uploaded ZIP file.

    Yields:
        (filename, image_bytes) tuples for each supported image found.

    Raises:
        ValueError: If the bytes are not a valid ZIP file.
        ValueError: If the ZIP contains no supported images.
    """
    if not zipfile.is_zipfile(BytesIO(zip_bytes)):
        raise ValueError("Uploaded file is not a valid ZIP archive.")

    found_count = 0

    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            # Skip directories and hidden files (macOS __MACOSX artifacts, etc.)
            if name.endswith("/") or name.startswith("__MACOSX") or name.startswith("."):
                continue

            suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if suffix not in ALLOWED_IMAGE_EXTENSIONS:
                continue

            image_bytes = zf.read(name)
            filename = name.split("/")[-1]   # strip any subdirectory path
            yield filename, image_bytes
            found_count += 1

    if found_count == 0:
        raise ValueError(
            f"ZIP contains no supported image files. "
            f"Accepted formats: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )
