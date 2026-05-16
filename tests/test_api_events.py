"""
test_api_events.py — Integration tests for M1 Event API routes
===============================================================
Tests all organizer-facing endpoints and the new attendee link endpoints:

  POST   /api/events/create
  POST   /api/events/{event_id}/upload
  GET    /api/events/{event_id}/status
  DELETE /api/events/{event_id}
  GET    /api/events/link/{share_token}       [NEW]
  GET    /api/events/link/{share_token}/photos [NEW]

Coverage type: INTEGRATION (real HTTP via httpx + real in-memory DB)
Face engine and storage are mocked so tests run without InsightFace installed.
"""

import io
import zipfile
import json
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient

from backend.database import crud
from backend.database.models import EventStatus


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_fake_zip(filenames: list[str]) -> bytes:
    """Creates an in-memory ZIP with dummy image content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in filenames:
            zf.writestr(name, b"\xff\xd8\xff" + b"\x00" * 100)  # minimal JPEG header
    return buf.getvalue()


FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200   # minimal JPEG bytes


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/events/create
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_create_returns_201(self, test_client: AsyncClient):
        resp = await test_client.post("/api/events/create", params={"name": "My Event"})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_returns_event_id_and_share_token(self, test_client: AsyncClient):
        resp = await test_client.post("/api/events/create", params={"name": "Concert"})
        data = resp.json()
        assert "event_id" in data
        assert "share_token" in data
        assert "share_link" in data

    @pytest.mark.asyncio
    async def test_share_link_contains_token(self, test_client: AsyncClient):
        resp = await test_client.post("/api/events/create", params={"name": "Concert"})
        data = resp.json()
        assert data["share_token"] in data["share_link"]

    @pytest.mark.asyncio
    async def test_missing_name_returns_422(self, test_client: AsyncClient):
        resp = await test_client.post("/api/events/create")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_two_events_get_different_tokens(self, test_client: AsyncClient):
        r1 = await test_client.post("/api/events/create", params={"name": "E1"})
        r2 = await test_client.post("/api/events/create", params={"name": "E2"})
        assert r1.json()["share_token"] != r2.json()["share_token"]


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/events/{event_id}/upload
# ══════════════════════════════════════════════════════════════════════════════

class TestUploadPhotos:
    @pytest.mark.asyncio
    async def test_upload_returns_202(self, test_client: AsyncClient):
        event_resp = await test_client.post("/api/events/create", params={"name": "E"})
        event_id = event_resp.json()["event_id"]

        with (
            patch("backend.storage.StorageService.save_photo", new_callable=AsyncMock,
                  return_value="evt/photo.jpg"),
            patch("backend.ingestion.tasks.process_album_task.delay"),
        ):
            resp = await test_client.post(
                f"/api/events/{event_id}/upload",
                files=[("files", ("photo.jpg", FAKE_JPEG, "image/jpeg"))],
            )
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_upload_reports_queued_count(self, test_client: AsyncClient):
        event_resp = await test_client.post("/api/events/create", params={"name": "E"})
        event_id = event_resp.json()["event_id"]

        with (
            patch("backend.storage.StorageService.save_photo", new_callable=AsyncMock,
                  return_value="evt/photo.jpg"),
            patch("backend.ingestion.tasks.process_album_task.delay"),
        ):
            resp = await test_client.post(
                f"/api/events/{event_id}/upload",
                files=[
                    ("files", ("a.jpg", FAKE_JPEG, "image/jpeg")),
                    ("files", ("b.jpg", FAKE_JPEG, "image/jpeg")),
                ],
            )
        assert resp.json()["queued_photos"] == 2

    @pytest.mark.asyncio
    async def test_upload_unknown_event_returns_404(self, test_client: AsyncClient):
        resp = await test_client.post(
            "/api/events/nonexistent-id/upload",
            files=[("files", ("photo.jpg", FAKE_JPEG, "image/jpeg"))],
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_to_deleted_event_returns_410(self, test_client: AsyncClient, async_db):
        from backend.database import crud as db_crud
        event = await db_crud.create_event(async_db, "Deleted Event")
        await db_crud.set_event_status(async_db, event.id, EventStatus.deleted)

        resp = await test_client.post(
            f"/api/events/{event.id}/upload",
            files=[("files", ("photo.jpg", FAKE_JPEG, "image/jpeg"))],
        )
        assert resp.status_code == 410

    @pytest.mark.asyncio
    async def test_upload_zip_file(self, test_client: AsyncClient):
        event_resp = await test_client.post("/api/events/create", params={"name": "Zip Event"})
        event_id = event_resp.json()["event_id"]
        zip_bytes = _make_fake_zip(["photo1.jpg", "photo2.jpg", "photo3.png"])

        with (
            patch("backend.storage.StorageService.save_photo", new_callable=AsyncMock,
                  return_value="evt/photo.jpg"),
            patch("backend.ingestion.tasks.process_album_task.delay"),
        ):
            resp = await test_client.post(
                f"/api/events/{event_id}/upload",
                files=[("files", ("album.zip", zip_bytes, "application/zip"))],
            )
        assert resp.status_code == 202
        assert resp.json()["queued_photos"] == 3

    @pytest.mark.asyncio
    async def test_upload_sets_event_status_to_processing(self, test_client: AsyncClient, async_db):
        event_resp = await test_client.post("/api/events/create", params={"name": "E"})
        event_id = event_resp.json()["event_id"]

        with (
            patch("backend.storage.StorageService.save_photo", new_callable=AsyncMock,
                  return_value="evt/photo.jpg"),
            patch("backend.ingestion.tasks.process_album_task.delay"),
        ):
            await test_client.post(
                f"/api/events/{event_id}/upload",
                files=[("files", ("photo.jpg", FAKE_JPEG, "image/jpeg"))],
            )

        event = await crud.get_event_by_id(async_db, event_id)
        assert event.status == EventStatus.processing


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/events/{event_id}/status
# ══════════════════════════════════════════════════════════════════════════════

class TestGetEventStatus:
    @pytest.mark.asyncio
    async def test_returns_status_for_known_event(self, test_client: AsyncClient):
        event_resp = await test_client.post("/api/events/create", params={"name": "E"})
        event_id = event_resp.json()["event_id"]
        resp = await test_client.get(f"/api/events/{event_id}/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "uploading"

    @pytest.mark.asyncio
    async def test_returns_share_link_only_when_ready(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Ready Event")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        resp = await test_client.get(f"/api/events/{event.id}/status")
        data = resp.json()
        assert data["status"] == "ready"
        assert "share_link" in data

    @pytest.mark.asyncio
    async def test_no_share_link_when_processing(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Processing Event")
        await crud.set_event_status(async_db, event.id, EventStatus.processing)
        resp = await test_client.get(f"/api/events/{event.id}/status")
        assert "share_link" not in resp.json()

    @pytest.mark.asyncio
    async def test_unknown_event_id_returns_404(self, test_client: AsyncClient):
        resp = await test_client.get("/api/events/does-not-exist/status")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/events/link/{share_token}  [NEW — attendee link validation]
# ══════════════════════════════════════════════════════════════════════════════

class TestGetEventByShareLink:
    @pytest.mark.asyncio
    async def test_valid_token_returns_200(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "My Party")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        resp = await test_client.get(f"/api/events/link/{event.share_token}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_event_metadata(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Birthday Bash")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        resp = await test_client.get(f"/api/events/link/{event.share_token}")
        data = resp.json()
        assert data["event_id"] == event.id
        assert data["name"] == "Birthday Bash"
        assert data["share_token"] == event.share_token
        assert data["ready"] is True

    @pytest.mark.asyncio
    async def test_includes_photo_counts(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Concert")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        p1 = await crud.record_photo(async_db, event.id, "e/1.jpg")
        p2 = await crud.record_photo(async_db, event.id, "e/2.jpg")
        await crud.mark_photo_processed(async_db, p1.id, face_count=1)

        resp = await test_client.get(f"/api/events/link/{event.share_token}")
        data = resp.json()
        assert data["total_photos"] == 2
        assert data["processed_photos"] == 1

    @pytest.mark.asyncio
    async def test_invalid_token_returns_404(self, test_client: AsyncClient):
        resp = await test_client.get("/api/events/link/totally-fake-token")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_deleted_event_returns_404(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Old Event")
        await crud.set_event_status(async_db, event.id, EventStatus.deleted)
        resp = await test_client.get(f"/api/events/link/{event.share_token}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_processing_event_is_accessible(self, test_client: AsyncClient, async_db):
        """Attendees can see event metadata even while photos are processing."""
        event = await crud.create_event(async_db, "Live Event")
        await crud.set_event_status(async_db, event.id, EventStatus.processing)
        resp = await test_client.get(f"/api/events/link/{event.share_token}")
        assert resp.status_code == 200
        assert resp.json()["ready"] is False

    @pytest.mark.asyncio
    async def test_includes_created_at_timestamp(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Timed Event")
        resp = await test_client.get(f"/api/events/link/{event.share_token}")
        assert resp.json()["created_at"] is not None


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/events/link/{share_token}/photos  [NEW]
# ══════════════════════════════════════════════════════════════════════════════

class TestListEventPhotos:
    @pytest.mark.asyncio
    async def test_returns_all_photos_for_ready_event(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Photo Fest")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        await crud.record_photo(async_db, event.id, "e/1.jpg")
        await crud.record_photo(async_db, event.id, "e/2.jpg")

        with patch("backend.storage.StorageService.get_photo_url", return_value="/api/photos/e/1.jpg"):
            resp = await test_client.get(f"/api/events/link/{event.share_token}/photos")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["photos"]) == 2

    @pytest.mark.asyncio
    async def test_photo_list_contains_expected_fields(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "E")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        p = await crud.record_photo(async_db, event.id, "e/a.jpg")
        await crud.mark_photo_processed(async_db, p.id, face_count=2)

        with patch("backend.storage.StorageService.get_photo_url", return_value="/api/photos/e/a.jpg"):
            resp = await test_client.get(f"/api/events/link/{event.share_token}/photos")

        photo = resp.json()["photos"][0]
        assert "photo_id" in photo
        assert "url" in photo
        assert "processed" in photo
        assert "face_count" in photo

    @pytest.mark.asyncio
    async def test_invalid_token_returns_404(self, test_client: AsyncClient):
        resp = await test_client.get("/api/events/link/ghost/photos")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_deleted_event_returns_404(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Old")
        await crud.set_event_status(async_db, event.id, EventStatus.deleted)
        resp = await test_client.get(f"/api/events/link/{event.share_token}/photos")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_uploading_status_returns_425(self, test_client: AsyncClient, async_db):
        """Photos unavailable if organizer hasn't uploaded yet."""
        event = await crud.create_event(async_db, "New")
        # Default status is "uploading"
        resp = await test_client.get(f"/api/events/link/{event.share_token}/photos")
        assert resp.status_code == 425

    @pytest.mark.asyncio
    async def test_includes_event_name_in_response(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Graduation Day")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)

        with patch("backend.storage.StorageService.get_photo_url", return_value="/api/photos/x"):
            resp = await test_client.get(f"/api/events/link/{event.share_token}/photos")

        assert resp.json()["event_name"] == "Graduation Day"


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/events/{event_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteEvent:
    @pytest.mark.asyncio
    async def test_delete_returns_204(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Doomed Event")

        with (
            patch("backend.storage.StorageService.delete_event_photos"),
            patch("pathlib.Path.exists", return_value=False),
        ):
            resp = await test_client.delete(f"/api/events/{event.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_marks_event_as_deleted(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Doomed")

        with (
            patch("backend.storage.StorageService.delete_event_photos"),
            patch("pathlib.Path.exists", return_value=False),
        ):
            await test_client.delete(f"/api/events/{event.id}")

        updated = await crud.get_event_by_id(async_db, event.id)
        assert updated.status == EventStatus.deleted

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, test_client: AsyncClient):
        resp = await test_client.delete("/api/events/no-such-event")
        assert resp.status_code == 404
