"""
test_batch_processor.py — Unit tests for M3 Batch Processor
=============================================================
Tests:
  - extract_images_from_zip: valid ZIP, empty ZIP, not-a-ZIP,
    skips hidden/dir entries, skips unsupported extensions,
    strips subdirectory paths, macOS MACOSX artifacts

Coverage type: UNIT (pure Python — no network, no DB, no model)
"""

import io
import zipfile
import pytest

from backend.ingestion.batch_processor import extract_images_from_zip


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_zip(entries: dict[str, bytes]) -> bytes:
    """
    Build an in-memory ZIP.
    entries: {filename_in_zip: file_content}
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
FAKE_PNG  = b"\x89PNG\r\n"      + b"\x00" * 100
FAKE_WEBP = b"RIFF"             + b"\x00" * 100


# ══════════════════════════════════════════════════════════════════════════════
# Happy path
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractImagesFromZip:
    def test_extracts_single_jpg(self):
        zip_bytes = _make_zip({"photo.jpg": FAKE_JPEG})
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1
        name, content = results[0]
        assert name == "photo.jpg"
        assert content == FAKE_JPEG

    def test_extracts_multiple_images(self):
        zip_bytes = _make_zip({
            "a.jpg": FAKE_JPEG,
            "b.png": FAKE_PNG,
            "c.webp": FAKE_WEBP,
        })
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 3

    def test_jpeg_extension_included(self):
        zip_bytes = _make_zip({"photo.jpeg": FAKE_JPEG})
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1

    def test_png_extension_included(self):
        zip_bytes = _make_zip({"img.png": FAKE_PNG})
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1

    def test_webp_extension_included(self):
        zip_bytes = _make_zip({"img.webp": FAKE_WEBP})
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Filtering behavior
# ══════════════════════════════════════════════════════════════════════════════

class TestZipFiltering:
    def test_skips_unsupported_extensions(self):
        zip_bytes = _make_zip({
            "photo.jpg": FAKE_JPEG,
            "document.pdf": b"fake-pdf",
            "script.py": b"print('hi')",
        })
        results = list(extract_images_from_zip(zip_bytes))
        names = [r[0] for r in results]
        assert len(results) == 1
        assert "photo.jpg" in names

    def test_skips_directory_entries(self):
        """ZIP entries ending with / are directories — skip them."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.mkdir("subdir/")        # directory entry
            zf.writestr("subdir/photo.jpg", FAKE_JPEG)
        zip_bytes = buf.getvalue()
        results = list(extract_images_from_zip(zip_bytes))
        # Should extract the photo, not the dir entry
        assert len(results) == 1

    def test_skips_macos_macosx_artifacts(self):
        zip_bytes = _make_zip({
            "__MACOSX/._photo.jpg": b"resource-fork-garbage",
            "photo.jpg": FAKE_JPEG,
        })
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1
        assert results[0][0] == "photo.jpg"

    def test_skips_hidden_dot_files(self):
        zip_bytes = _make_zip({
            ".DS_Store": b"hidden",
            "real.jpg": FAKE_JPEG,
        })
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1

    def test_strips_subdirectory_path_from_filename(self):
        """Filenames returned should be basename only, not full ZIP path."""
        zip_bytes = _make_zip({"albums/2024/wedding/photo.jpg": FAKE_JPEG})
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1
        assert results[0][0] == "photo.jpg"   # not "albums/2024/wedding/photo.jpg"

    def test_case_insensitive_extension_matching(self):
        """Uppercase .JPG, .PNG should be treated as supported."""
        zip_bytes = _make_zip({"PHOTO.JPG": FAKE_JPEG})
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Error cases
# ══════════════════════════════════════════════════════════════════════════════

class TestZipErrors:
    def test_not_a_zip_raises_value_error(self):
        with pytest.raises(ValueError, match="not a valid ZIP"):
            list(extract_images_from_zip(b"this is not a zip file"))

    def test_empty_zip_with_no_images_raises_value_error(self):
        """ZIP exists but contains no supported images."""
        zip_bytes = _make_zip({"README.txt": b"read me", "data.csv": b"a,b,c"})
        with pytest.raises(ValueError, match="no supported image"):
            list(extract_images_from_zip(zip_bytes))

    def test_completely_empty_zip_raises_value_error(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass  # empty ZIP
        with pytest.raises(ValueError):
            list(extract_images_from_zip(buf.getvalue()))

    def test_random_bytes_raises_value_error(self):
        with pytest.raises(ValueError):
            list(extract_images_from_zip(b"\x00" * 500))


# ══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestZipEdgeCases:
    def test_large_number_of_images(self):
        entries = {f"photo_{i:04d}.jpg": FAKE_JPEG for i in range(100)}
        zip_bytes = _make_zip(entries)
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 100

    def test_mixed_valid_and_invalid_files(self):
        zip_bytes = _make_zip({
            "a.jpg": FAKE_JPEG,
            "b.doc": b"word doc",
            "c.png": FAKE_PNG,
            "d.exe": b"malware",
        })
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 2

    def test_zero_byte_image_is_included(self):
        """Empty-content files are extracted — validation is not our job here."""
        zip_bytes = _make_zip({"empty.jpg": b""})
        results = list(extract_images_from_zip(zip_bytes))
        assert len(results) == 1
        assert results[0][1] == b""
