"""
test_api_search.py — Integration tests for M1 Search Route
===========================================================
Tests:
  POST /api/events/{share_token}/search

Coverage type: INTEGRATION
Face engine and FAISS are fully mocked — no model loading required.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

from backend.database import crud
from backend.database.models import EventStatus
from backend.face_engine.exceptions import NoFaceDetectedError, MultipleFacesError


# ── Helpers ───────────────────────────────────────────────────────────────────

FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200

def _make_embedding(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


# ══════════════════════════════════════════════════════════════════════════════
# Integration: POST /api/events/{share_token}/search
# ══════════════════════════════════════════════════════════════════════════════

class TestSearchPhotos:
    @pytest.mark.asyncio
    async def test_search_returns_200_with_results(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Wedding")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        photo = await crud.record_photo(async_db, event.id, "e/1.jpg")

        mock_results = [
            (photo, 0.92)
        ]

        with (
            patch("backend.face_engine.FaceEngine.embed_single",
                  return_value=_make_embedding()),
            patch("backend.database.crud.search_photos_by_embedding",
                  return_value=mock_results),
            patch("backend.storage.StorageService.get_photo_url",
                  return_value="/api/photos/e/1.jpg"),
        ):
            resp = await test_client.post(
                f"/api/events/{event.share_token}/search",
                files=[("selfie", ("me.jpg", FAKE_JPEG, "image/jpeg"))],
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query_face_detected"] is True
        assert len(data["results"]["confident"]) == 1
        assert data["results"]["confident"][0]["score"] == 0.92

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_no_match(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "No Match Event")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)

        with (
            patch("backend.face_engine.FaceEngine.embed_single",
                  return_value=_make_embedding()),
            patch("backend.database.crud.search_photos_by_embedding", return_value=[]),
        ):
            resp = await test_client.post(
                f"/api/events/{event.share_token}/search",
                files=[("selfie", ("me.jpg", FAKE_JPEG, "image/jpeg"))],
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_matches"] == 0
        assert data["results"]["confident"] == []
        assert data["results"]["possible"] == []

    @pytest.mark.asyncio
    async def test_search_invalid_token_returns_404(self, test_client: AsyncClient):
        with (
            patch("backend.face_engine.FaceEngine.embed_single",
                  return_value=_make_embedding()),
        ):
            resp = await test_client.post(
                "/api/events/bad-token/search",
                files=[("selfie", ("me.jpg", FAKE_JPEG, "image/jpeg"))],
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_search_on_processing_event_returns_425(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Still Processing")
        await crud.set_event_status(async_db, event.id, EventStatus.processing)

        resp = await test_client.post(
            f"/api/events/{event.share_token}/search",
            files=[("selfie", ("me.jpg", FAKE_JPEG, "image/jpeg"))],
        )
        assert resp.status_code == 425

    @pytest.mark.asyncio
    async def test_no_face_in_selfie_returns_422(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "E")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)

        with patch("backend.face_engine.FaceEngine.embed_single",
                   side_effect=NoFaceDetectedError("No face detected")):
            resp = await test_client.post(
                f"/api/events/{event.share_token}/search",
                files=[("selfie", ("blank.jpg", FAKE_JPEG, "image/jpeg"))],
            )

        assert resp.status_code == 422
        assert "No face" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_multiple_faces_in_selfie_returns_422(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "E")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)

        with patch("backend.face_engine.FaceEngine.embed_single",
                   side_effect=MultipleFacesError("2 faces detected")):
            resp = await test_client.post(
                f"/api/events/{event.share_token}/search",
                files=[("selfie", ("group.jpg", FAKE_JPEG, "image/jpeg"))],
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_separates_confident_and_possible(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "Mixed Results")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        p1 = await crud.record_photo(async_db, event.id, "e/1.jpg")
        p2 = await crud.record_photo(async_db, event.id, "e/2.jpg")

        mock_results = [
            (p1, 0.88),
            (p2, 0.61),
        ]

        with (
            patch("backend.face_engine.FaceEngine.embed_single",
                  return_value=_make_embedding()),
            patch("backend.database.crud.search_photos_by_embedding",
                  return_value=mock_results),
            patch("backend.storage.StorageService.get_photo_url",
                  return_value="/api/photos/e/1.jpg"),
        ):
            resp = await test_client.post(
                f"/api/events/{event.share_token}/search",
                files=[("selfie", ("me.jpg", FAKE_JPEG, "image/jpeg"))],
            )

        data = resp.json()
        assert len(data["results"]["confident"]) == 1
        assert len(data["results"]["possible"]) == 1
        assert data["total_matches"] == 2

    @pytest.mark.asyncio
    async def test_search_no_selfie_returns_422(self, test_client: AsyncClient, async_db):
        event = await crud.create_event(async_db, "E")
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        resp = await test_client.post(f"/api/events/{event.share_token}/search")
        assert resp.status_code == 422
