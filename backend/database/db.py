"""
M4 — Database Connection & Session Factory
============================================
Provides the SQLAlchemy engine and session factory used by crud.py.

Usage in FastAPI:
    from backend.database.db import get_db

    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db)):
        ...
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.config import DATABASE_URL
from backend.database.models import Base


# SQLite in dev → asyncio-compatible URL requires "sqlite+aiosqlite://"
# PostgreSQL in prod → "postgresql+asyncpg://..."
def _make_async_url(url: str) -> str:
    """Converts sync SQLAlchemy URL to async driver URL."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


ASYNC_DATABASE_URL = _make_async_url(DATABASE_URL)

engine_kwargs = {
    "echo": False,
}
if "sqlite" in ASYNC_DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    **engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Creates all tables. Called once at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """
    FastAPI dependency — yields a database session per request.

    Usage:
        db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        yield session
