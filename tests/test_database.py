"""
test_database.py — Unit tests for M4 (Database Layer)
=======================================================
Tests:
  - create_event
  - get_event_by_id / get_event_by_token
  - set_event_status
  - record_photo / mark_photo_processed
  - get_photos_by_ids
  - get_unprocessed_photos
  - get_all_photos_for_event       [NEW]
  - get_event_photo_counts         [NEW]

Coverage type: UNIT (pure DB layer, no HTTP)
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import crud
from backend.database.models import EventStatus


# ══════════════════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════════════════

async def _make_event(db: AsyncSession, name: str = "Test Event") -> object:
    return await crud.create_event(db, name=name)

async def _make_photo(db: AsyncSession, event_id: str, key: str = "evt/photo.jpg") -> object:
    return await crud.record_photo(db, event_id=event_id, storage_key=key)


# ══════════════════════════════════════════════════════════════════════════════
# UNIT: Event CRUD
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_creates_event_with_correct_name(self, async_db):
        event = await _make_event(async_db, "Summer Wedding 2024")
        assert event.name == "Summer Wedding 2024"

    @pytest.mark.asyncio
    async def test_auto_generates_uuid_id(self, async_db):
        event = await _make_event(async_db)
        assert event.id is not None
        assert len(event.id) == 36          # UUID4 format

    @pytest.mark.asyncio
    async def test_auto_generates_share_token(self, async_db):
        event = await _make_event(async_db)
        assert event.share_token is not None
        assert len(event.share_token) > 0

    @pytest.mark.asyncio
    async def test_share_tokens_are_unique(self, async_db):
        e1 = await _make_event(async_db)
        e2 = await _make_event(async_db)
        assert e1.share_token != e2.share_token

    @pytest.mark.asyncio
    async def test_default_status_is_uploading(self, async_db):
        event = await _make_event(async_db)
        assert event.status == EventStatus.uploading

    @pytest.mark.asyncio
    async def test_created_at_is_set(self, async_db):
        event = await _make_event(async_db)
        assert event.created_at is not None


class TestGetEvent:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_event(self, async_db):
        event = await _make_event(async_db)
        fetched = await crud.get_event_by_id(async_db, event.id)
        assert fetched is not None
        assert fetched.id == event.id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_unknown(self, async_db):
        result = await crud.get_event_by_id(async_db, "nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_token_returns_event(self, async_db):
        event = await _make_event(async_db)
        fetched = await crud.get_event_by_token(async_db, event.share_token)
        assert fetched is not None
        assert fetched.share_token == event.share_token

    @pytest.mark.asyncio
    async def test_get_by_token_returns_none_for_unknown(self, async_db):
        result = await crud.get_event_by_token(async_db, "badtoken")
        assert result is None


class TestSetEventStatus:
    @pytest.mark.asyncio
    async def test_updates_status_to_processing(self, async_db):
        event = await _make_event(async_db)
        await crud.set_event_status(async_db, event.id, EventStatus.processing)
        updated = await crud.get_event_by_id(async_db, event.id)
        assert updated.status == EventStatus.processing

    @pytest.mark.asyncio
    async def test_updates_status_to_ready(self, async_db):
        event = await _make_event(async_db)
        await crud.set_event_status(async_db, event.id, EventStatus.ready)
        updated = await crud.get_event_by_id(async_db, event.id)
        assert updated.status == EventStatus.ready

    @pytest.mark.asyncio
    async def test_updates_status_to_deleted(self, async_db):
        event = await _make_event(async_db)
        await crud.set_event_status(async_db, event.id, EventStatus.deleted)
        updated = await crud.get_event_by_id(async_db, event.id)
        assert updated.status == EventStatus.deleted


# ══════════════════════════════════════════════════════════════════════════════
# UNIT: Photo CRUD
# ══════════════════════════════════════════════════════════════════════════════

class TestRecordPhoto:
    @pytest.mark.asyncio
    async def test_creates_photo_record(self, async_db):
        event = await _make_event(async_db)
        photo = await _make_photo(async_db, event.id)
        assert photo.id is not None
        assert photo.event_id == event.id

    @pytest.mark.asyncio
    async def test_photo_default_not_processed(self, async_db):
        event = await _make_event(async_db)
        photo = await _make_photo(async_db, event.id)
        assert photo.processed is False

    @pytest.mark.asyncio
    async def test_photo_face_count_is_none_initially(self, async_db):
        event = await _make_event(async_db)
        photo = await _make_photo(async_db, event.id)
        assert photo.face_count is None

    @pytest.mark.asyncio
    async def test_storage_key_stored_correctly(self, async_db):
        event = await _make_event(async_db)
        photo = await crud.record_photo(async_db, event.id, "myevent/img001.jpg")
        assert photo.storage_key == "myevent/img001.jpg"


class TestMarkPhotoProcessed:
    @pytest.mark.asyncio
    async def test_marks_processed_true(self, async_db):
        event = await _make_event(async_db)
        photo = await _make_photo(async_db, event.id)
        await crud.mark_photo_processed(async_db, photo.id, face_count=3)
        updated = (await crud.get_photos_by_ids(async_db, [photo.id]))[0]
        assert updated.processed is True

    @pytest.mark.asyncio
    async def test_sets_face_count(self, async_db):
        event = await _make_event(async_db)
        photo = await _make_photo(async_db, event.id)
        await crud.mark_photo_processed(async_db, photo.id, face_count=5)
        updated = (await crud.get_photos_by_ids(async_db, [photo.id]))[0]
        assert updated.face_count == 5

    @pytest.mark.asyncio
    async def test_face_count_zero_is_valid(self, async_db):
        """Photos with no faces (landscapes) should be tracked too."""
        event = await _make_event(async_db)
        photo = await _make_photo(async_db, event.id)
        await crud.mark_photo_processed(async_db, photo.id, face_count=0)
        updated = (await crud.get_photos_by_ids(async_db, [photo.id]))[0]
        assert updated.face_count == 0
        assert updated.processed is True


class TestGetPhotosByIds:
    @pytest.mark.asyncio
    async def test_returns_matching_photos(self, async_db):
        event = await _make_event(async_db)
        p1 = await _make_photo(async_db, event.id, "e/a.jpg")
        p2 = await _make_photo(async_db, event.id, "e/b.jpg")
        results = await crud.get_photos_by_ids(async_db, [p1.id, p2.id])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_ignores_nonexistent_ids(self, async_db):
        event = await _make_event(async_db)
        p1 = await _make_photo(async_db, event.id)
        results = await crud.get_photos_by_ids(async_db, [p1.id, "ghost-id"])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_empty_id_list_returns_empty(self, async_db):
        results = await crud.get_photos_by_ids(async_db, [])
        assert results == []


class TestGetUnprocessedPhotos:
    @pytest.mark.asyncio
    async def test_returns_only_unprocessed(self, async_db):
        event = await _make_event(async_db)
        p1 = await _make_photo(async_db, event.id, "e/1.jpg")
        p2 = await _make_photo(async_db, event.id, "e/2.jpg")
        await crud.mark_photo_processed(async_db, p1.id, face_count=1)

        unprocessed = await crud.get_unprocessed_photos(async_db, event.id)
        ids = [p.id for p in unprocessed]
        assert p1.id not in ids
        assert p2.id in ids

    @pytest.mark.asyncio
    async def test_empty_when_all_processed(self, async_db):
        event = await _make_event(async_db)
        photo = await _make_photo(async_db, event.id)
        await crud.mark_photo_processed(async_db, photo.id, face_count=2)
        unprocessed = await crud.get_unprocessed_photos(async_db, event.id)
        assert unprocessed == []


# ══════════════════════════════════════════════════════════════════════════════
# UNIT: New CRUD helpers (get_all_photos_for_event, get_event_photo_counts)
# ══════════════════════════════════════════════════════════════════════════════

class TestGetAllPhotosForEvent:
    @pytest.mark.asyncio
    async def test_returns_all_photos_including_unprocessed(self, async_db):
        event = await _make_event(async_db)
        await _make_photo(async_db, event.id, "e/1.jpg")
        await _make_photo(async_db, event.id, "e/2.jpg")
        photos = await crud.get_all_photos_for_event(async_db, event.id)
        assert len(photos) == 2

    @pytest.mark.asyncio
    async def test_does_not_return_other_events_photos(self, async_db):
        e1 = await _make_event(async_db, "Event 1")
        e2 = await _make_event(async_db, "Event 2")
        await _make_photo(async_db, e1.id, "e1/a.jpg")
        await _make_photo(async_db, e2.id, "e2/b.jpg")
        photos = await crud.get_all_photos_for_event(async_db, e1.id)
        assert len(photos) == 1
        assert photos[0].event_id == e1.id

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_new_event(self, async_db):
        event = await _make_event(async_db)
        photos = await crud.get_all_photos_for_event(async_db, event.id)
        assert photos == []


class TestGetEventPhotoCounts:
    @pytest.mark.asyncio
    async def test_counts_total_and_processed(self, async_db):
        event = await _make_event(async_db)
        p1 = await _make_photo(async_db, event.id, "e/1.jpg")
        p2 = await _make_photo(async_db, event.id, "e/2.jpg")
        await _make_photo(async_db, event.id, "e/3.jpg")
        await crud.mark_photo_processed(async_db, p1.id, face_count=2)
        await crud.mark_photo_processed(async_db, p2.id, face_count=0)

        counts = await crud.get_event_photo_counts(async_db, event.id)
        assert counts["total"] == 3
        assert counts["processed"] == 2

    @pytest.mark.asyncio
    async def test_all_zeros_for_new_event(self, async_db):
        event = await _make_event(async_db)
        counts = await crud.get_event_photo_counts(async_db, event.id)
        assert counts == {"total": 0, "processed": 0}

    @pytest.mark.asyncio
    async def test_processed_equals_total_when_all_done(self, async_db):
        event = await _make_event(async_db)
        photos = [await _make_photo(async_db, event.id, f"e/{i}.jpg") for i in range(5)]
        for p in photos:
            await crud.mark_photo_processed(async_db, p.id, face_count=1)
        counts = await crud.get_event_photo_counts(async_db, event.id)
        assert counts["total"] == counts["processed"] == 5
