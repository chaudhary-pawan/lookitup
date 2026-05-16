"""
conftest.py — Shared pytest fixtures for LookItUp test suite.
==============================================================
Provides:
  - async_db        : isolated in-memory SQLite session per test
  - test_client     : FastAPI httpx async client
  - temp_upload_dir : temporary upload directory, cleaned up after each test
  - dummy_embedding : deterministic 512-dim unit vector helper
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
import numpy as np
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ── Ensure project root is importable ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Override config BEFORE importing anything backend-related ─────────────────
import backend.config as cfg

_TEMP_UPLOAD = tempfile.mkdtemp(prefix="lookitup_uploads_")
_TEMP_FAISS  = tempfile.mkdtemp(prefix="lookitup_faiss_")

cfg.LOCAL_UPLOAD_DIR = Path(_TEMP_UPLOAD)
cfg.FAISS_INDEX_DIR  = Path(_TEMP_FAISS)
cfg.DATABASE_URL     = "sqlite+aiosqlite:///:memory:"

from backend.database.models import Base
from backend.database.db import get_db


# ── In-memory async DB engine (shared across fixture scope) ───────────────────
TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    echo=False,
)
TestSessionLocal = async_sessionmaker(
    bind=TEST_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields a fresh async SQLite session with all tables created.
    Tables are dropped and recreated for each test to ensure isolation.
    """
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def test_client(async_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Yields an httpx AsyncClient wired to the FastAPI app,
    with the DB dependency overridden to use the test session.
    """
    from backend.api.main import app

    async def override_get_db():
        yield async_db

    app.dependency_overrides[get_db] = override_get_db

    # Bypass lifespan (face model loading) for API integration tests
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def temp_upload_dir(tmp_path: Path) -> Path:
    """Temporary directory for photo upload tests — auto-cleaned."""
    upload = tmp_path / "uploads"
    upload.mkdir()
    original = cfg.LOCAL_UPLOAD_DIR
    cfg.LOCAL_UPLOAD_DIR = upload
    yield upload
    cfg.LOCAL_UPLOAD_DIR = original


def make_embedding(seed: int = 0) -> np.ndarray:
    """Returns a deterministic L2-normalized 512-dim float32 vector."""
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


@pytest.fixture
def dummy_embedding() -> np.ndarray:
    return make_embedding(seed=42)
