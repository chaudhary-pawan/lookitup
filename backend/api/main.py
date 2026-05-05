"""
M1 — API Gateway: FastAPI Application
=======================================
Application entry point. Registers all routers, middleware, and startup events.

Run with:
    uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import events, search, photos
from backend.api.middleware.validation import UploadSizeLimitMiddleware
from backend.database.db import init_db
from backend.face_engine.model_loader import get_face_analysis_model
from backend.config import API_HOST, API_PORT

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup and once at shutdown.

    Startup:
        1. Create DB tables (idempotent — safe to run every start)
        2. Pre-load the InsightFace model into memory (avoids cold start on first request)
    """
    logger.info("Starting LookItUp API...")

    # Initialize database tables
    await init_db()
    logger.info("Database initialized")

    # Pre-load face recognition model (takes ~3–5s on first load)
    logger.info(f"Loading InsightFace model...")
    get_face_analysis_model()
    logger.info("Face model loaded — API is ready")

    yield

    # Shutdown cleanup (if needed)
    logger.info("LookItUp API shutting down")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="LookItUp API",
    description="Face-recognition photo retrieval for events",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(UploadSizeLimitMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(events.router)
app.include_router(search.router)
app.include_router(photos.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    """Quick liveness check — used by Docker Compose and deployment platforms."""
    return {"status": "ok", "service": "lookitup-api"}
