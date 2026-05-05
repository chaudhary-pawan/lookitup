"""
M4 — Database CRUD Operations
================================
All database reads and writes go through this module.
No other module touches SQLAlchemy Session objects directly.

This is the public interface of the DB Layer (M4).
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.database.models import Event, Photo, EventStatus


# ── Event operations ──────────────────────────────────────────────────────────

async def create_event(db: AsyncSession, name: str) -> Event:
    """
    Creates a new event record.

    Called by: M1 API Gateway → POST /events/create

    Returns the new Event object (with auto-generated id and share_token).
    """
    event = Event(name=name)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_event_by_id(db: AsyncSession, event_id: str) -> Optional[Event]:
    """Retrieves an event by its primary key."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def get_event_by_token(db: AsyncSession, share_token: str) -> Optional[Event]:
    """
    Retrieves an event by its share_token.

    Called by: M1 API Gateway → POST /events/{share_token}/search
    This is how attendees reach an event via shared link.
    """
    result = await db.execute(select(Event).where(Event.share_token == share_token))
    return result.scalar_one_or_none()


async def set_event_status(db: AsyncSession, event_id: str, status: EventStatus) -> None:
    """Updates the lifecycle status of an event."""
    await db.execute(
        update(Event).where(Event.id == event_id).values(status=status)
    )
    await db.commit()


# ── Photo operations ──────────────────────────────────────────────────────────

async def record_photo(
    db: AsyncSession,
    event_id: str,
    storage_key: str,
) -> Photo:
    """
    Records a newly uploaded photo in the DB (before ingestion).

    Called by: M1 API Gateway (right after M2 saves the file)
    """
    photo = Photo(event_id=event_id, storage_key=storage_key)
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


async def mark_photo_processed(
    db: AsyncSession,
    photo_id: str,
    face_count: int,
) -> None:
    """
    Marks a photo as processed and records how many faces were found.

    Called by: M3 Ingestion Pipeline (after each photo is processed)
    """
    await db.execute(
        update(Photo)
        .where(Photo.id == photo_id)
        .values(processed=True, face_count=face_count)
    )
    await db.commit()


async def get_photos_by_ids(
    db: AsyncSession,
    photo_ids: List[str],
) -> List[Photo]:
    """
    Fetches photo records by their IDs.

    Called by: M1 API Gateway (after M6 returns matching photo_ids)
    Used to get storage_keys → passed to M2 to generate URLs.
    """
    result = await db.execute(
        select(Photo).where(Photo.id.in_(photo_ids))
    )
    return list(result.scalars().all())


async def get_unprocessed_photos(
    db: AsyncSession,
    event_id: str,
) -> List[Photo]:
    """Returns all photos in an event that haven't been processed yet."""
    result = await db.execute(
        select(Photo).where(
            Photo.event_id == event_id,
            Photo.processed == False,  # noqa: E712
        )
    )
    return list(result.scalars().all())
