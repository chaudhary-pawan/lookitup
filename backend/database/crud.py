"""
M4 — Database CRUD Operations
================================
All database reads and writes go through this module.
No other module touches SQLAlchemy Session objects directly.

This is the public interface of the DB Layer (M4).
"""

from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from backend.database.models import Event, Photo, EventStatus


# ── Event operations ──────────────────────────────────────────────────────────

async def create_event(db: AsyncSession, name: str, organizer_id: str) -> Event:
    """
    Creates a new event record.

    Called by: M1 API Gateway → POST /events/create

    Returns the new Event object (with auto-generated id and share_token).
    """
    event = Event(name=name, organizer_id=organizer_id)
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
    thumbnail_key: Optional[str] = None,
    embedding: Optional[list] = None,
) -> None:
    """
    Marks a photo as processed and records how many faces were found.
    Also saves the thumbnail key and the vector embedding (if any).

    Called by: M3 Ingestion Pipeline (after each photo is processed)
    """
    values = {"processed": True, "face_count": face_count}
    if thumbnail_key:
        values["thumbnail_key"] = thumbnail_key
    if embedding is not None:
        values["embedding"] = embedding

    await db.execute(
        update(Photo)
        .where(Photo.id == photo_id)
        .values(**values)
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


async def get_all_photos_for_event(
    db: AsyncSession,
    event_id: str,
) -> List[Photo]:
    """
    Returns ALL photos belonging to an event (processed or not).

    Called by: GET /api/events/link/{share_token}/photos
    Used by attendees to browse the full event gallery.
    """
    result = await db.execute(
        select(Photo)
        .where(Photo.event_id == event_id)
        .order_by(Photo.uploaded_at.asc())
    )
    return list(result.scalars().all())


async def get_event_photo_counts(
    db: AsyncSession,
    event_id: str,
) -> Dict[str, int]:
    """
    Returns the total and processed photo counts for an event.

    Called by: GET /api/events/link/{share_token}
    Lets the attendee UI show "142/142 photos indexed" or a progress bar.
    """
    total_result = await db.execute(
        select(func.count(Photo.id)).where(Photo.event_id == event_id)
    )
    total = total_result.scalar_one() or 0

    processed_result = await db.execute(
        select(func.count(Photo.id)).where(
            Photo.event_id == event_id,
            Photo.processed == True,  # noqa: E712
        )
    )
    processed = processed_result.scalar_one() or 0

    return {"total": total, "processed": processed}


async def search_photos_by_embedding(
    db: AsyncSession,
    event_id: str,
    query_embedding: list,
    limit: int = 50,
    threshold: float = 0.55
) -> List[tuple[Photo, float]]:
    """
    Uses pgvector to find the most similar photos in the database.
    Calculates cosine distance and converts it to cosine similarity.
    Returns a list of tuples (Photo, similarity_score).
    """
    # pgvector's cosine_distance returns (1 - cosine_similarity)
    # We want similarity, so we compute: 1 - cosine_distance
    similarity_expr = (1 - Photo.embedding.cosine_distance(query_embedding)).label("similarity")

    result = await db.execute(
        select(Photo, similarity_expr)
        .where(Photo.event_id == event_id)
        .where(Photo.embedding != None)
        .where(similarity_expr >= threshold)
        .order_by(similarity_expr.desc())
        .limit(limit)
    )
    
    return result.all()
