"""
test_storage.py — Unit tests for M2 (Local Storage Backend)
============================================================
Tests:
  - save_photo: path construction, extension preservation, UUID uniqueness
  - get_photo_url: URL format
  - get_photo_bytes: reads correct file, raises FileNotFoundError
  - get_photo_path: returns correct Path
  - delete_event_photos: removes directory

Coverage type: UNIT (filesystem only — no DB, no HTTP)
"""

import uuid
import pytest
import pytest_asyncio
from pathlib import Path

from backend.storage.local_storage import LocalStorage
import backend.config as cfg


# ══════════════════════════════════════════════════════════════════════════════
# save_photo
# ══════════════════════════════════════════════════════════════════════════════

class TestSavePhoto:
    @pytest.mark.asyncio
    async def test_returns_storage_key_string(self, temp_upload_dir: Path):
        key = await LocalStorage.save_photo(b"\xff\xd8\xff" + b"\x00" * 50, "evt1", "photo.jpg")
        assert isinstance(key, str)

    @pytest.mark.asyncio
    async def test_storage_key_contains_event_id(self, temp_upload_dir: Path):
        key = await LocalStorage.save_photo(b"\xff\xd8\xff" + b"\x00" * 50, "evt-xyz", "photo.jpg")
        assert key.startswith("evt-xyz/")

    @pytest.mark.asyncio
    async def test_storage_key_preserves_extension(self, temp_upload_dir: Path):
        key = await LocalStorage.save_photo(b"\x89PNG\r\n" + b"\x00" * 50, "evt1", "img.png")
        assert key.endswith(".png")

    @pytest.mark.asyncio
    async def test_file_is_written_to_disk(self, temp_upload_dir: Path):
        content = b"\xff\xd8\xff\xe0" + b"content" * 10
        key = await LocalStorage.save_photo(content, "evtA", "pic.jpg")
        path = temp_upload_dir / key
        assert path.exists()
        assert path.read_bytes() == content

    @pytest.mark.asyncio
    async def test_two_uploads_get_different_keys(self, temp_upload_dir: Path):
        k1 = await LocalStorage.save_photo(b"\xff\xd8" + b"\x00" * 50, "e", "a.jpg")
        k2 = await LocalStorage.save_photo(b"\xff\xd8" + b"\x00" * 50, "e", "b.jpg")
        assert k1 != k2

    @pytest.mark.asyncio
    async def test_creates_event_subdirectory(self, temp_upload_dir: Path):
        await LocalStorage.save_photo(b"\xff\xd8\xff" + b"\x00" * 50, "evt-newdir", "x.jpg")
        assert (temp_upload_dir / "evt-newdir").is_dir()

    @pytest.mark.asyncio
    async def test_unsupported_extension_raises_value_error(self, temp_upload_dir: Path):
        with pytest.raises(ValueError, match="Unsupported"):
            await LocalStorage.save_photo(b"data", "evt1", "malware.exe")

    @pytest.mark.asyncio
    async def test_webp_extension_is_supported(self, temp_upload_dir: Path):
        key = await LocalStorage.save_photo(b"RIFF" + b"\x00" * 50, "evt1", "img.webp")
        assert key.endswith(".webp")

    @pytest.mark.asyncio
    async def test_jpeg_extension_is_supported(self, temp_upload_dir: Path):
        key = await LocalStorage.save_photo(b"\xff\xd8\xff" + b"\x00" * 50, "evt1", "img.jpeg")
        assert key.endswith(".jpeg")


# ══════════════════════════════════════════════════════════════════════════════
# get_photo_url
# ══════════════════════════════════════════════════════════════════════════════

class TestGetPhotoUrl:
    def test_returns_api_path(self):
        url = LocalStorage.get_photo_url("evt1/photo123.jpg")
        assert url == "/api/photos/evt1/photo123.jpg"

    def test_url_starts_with_api_photos(self):
        url = LocalStorage.get_photo_url("any/key.png")
        assert url.startswith("/api/photos/")

    def test_storage_key_is_in_url(self):
        key = "event-abc/uuid-xyz.webp"
        assert key in LocalStorage.get_photo_url(key)


# ══════════════════════════════════════════════════════════════════════════════
# get_photo_bytes
# ══════════════════════════════════════════════════════════════════════════════

class TestGetPhotoBytes:
    @pytest.mark.asyncio
    async def test_reads_correct_bytes(self, temp_upload_dir: Path):
        content = b"\xff\xd8\xff\xe0" + b"real-image-data"
        key = await LocalStorage.save_photo(content, "e1", "img.jpg")
        result = LocalStorage.get_photo_bytes(key)
        assert result == content

    def test_missing_file_raises_file_not_found(self, temp_upload_dir: Path):
        with pytest.raises(FileNotFoundError):
            LocalStorage.get_photo_bytes("nonexistent/ghost.jpg")


# ══════════════════════════════════════════════════════════════════════════════
# get_photo_path
# ══════════════════════════════════════════════════════════════════════════════

class TestGetPhotoPath:
    def test_returns_path_object(self, temp_upload_dir: Path):
        path = LocalStorage.get_photo_path("evt/img.jpg")
        assert isinstance(path, Path)

    def test_path_is_under_upload_dir(self, temp_upload_dir: Path):
        path = LocalStorage.get_photo_path("evt/img.jpg")
        assert str(temp_upload_dir) in str(path)


# ══════════════════════════════════════════════════════════════════════════════
# delete_event_photos
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteEventPhotos:
    @pytest.mark.asyncio
    async def test_deletes_event_directory(self, temp_upload_dir: Path):
        await LocalStorage.save_photo(b"\xff\xd8\xff" + b"\x00" * 50, "to-delete", "img.jpg")
        assert (temp_upload_dir / "to-delete").exists()
        LocalStorage.delete_event_photos("to-delete")
        assert not (temp_upload_dir / "to-delete").exists()

    def test_no_error_if_directory_does_not_exist(self, temp_upload_dir: Path):
        """Should not raise even if event dir never existed."""
        LocalStorage.delete_event_photos("never-existed")  # must not raise

    @pytest.mark.asyncio
    async def test_only_deletes_target_event(self, temp_upload_dir: Path):
        await LocalStorage.save_photo(b"\xff\xd8\xff" + b"\x00" * 50, "keep-me", "img.jpg")
        await LocalStorage.save_photo(b"\xff\xd8\xff" + b"\x00" * 50, "delete-me", "img.jpg")
        LocalStorage.delete_event_photos("delete-me")
        assert (temp_upload_dir / "keep-me").exists()
        assert not (temp_upload_dir / "delete-me").exists()
