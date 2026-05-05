"""
M4 — Database Layer
=====================
All structured metadata lives here: events, photos, processing status.
Face embeddings do NOT live here — those are in M6 (FAISS).

Uses SQLAlchemy ORM with async support.
- Development: SQLite (zero config)
- Production:  PostgreSQL (swap DATABASE_URL in config)
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Enum, ForeignKey
)
from sqlalchemy.orm import declarative_base
import enum

Base = declarative_base()


class EventStatus(str, enum.Enum):
    """Lifecycle states of an event album."""
    uploading   = "uploading"    # organizer is uploading photos
    processing  = "processing"   # Celery task running (M3 ingestion)
    ready       = "ready"        # attendees can search
    deleted     = "deleted"      # organizer deleted — photos purged


class Event(Base):
    """
    Represents an event album created by an organizer.

    share_token:  URL-safe token used in attendee links
                  e.g. /event/abc123xyz → maps to event_id
    """
    __tablename__ = "events"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String(255), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    status      = Column(Enum(EventStatus), default=EventStatus.uploading, nullable=False)
    share_token = Column(String(64), unique=True, nullable=False,
                         default=lambda: uuid.uuid4().hex)

    def __repr__(self):
        return f"<Event id={self.id!r} name={self.name!r} status={self.status!r}>"


class Photo(Base):
    """
    Represents a single photo uploaded to an event.

    storage_key:  Opaque identifier used by M2 StorageService to retrieve the file.
                  For local storage: relative file path.
                  For Cloudinary: public_id.
    face_count:   Number of faces detected in this photo (set during ingestion).
    processed:    True once M3 ingestion has finished for this photo.
    """
    __tablename__ = "photos"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id    = Column(String(36), ForeignKey("events.id"), nullable=False)
    storage_key = Column(String(512), nullable=False)
    face_count  = Column(Integer, nullable=True)          # None until processed
    processed   = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Photo id={self.id!r} event={self.event_id!r} processed={self.processed!r}>"
