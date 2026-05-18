"""
config.py — Application-wide settings.
Loaded from environment variables (or .env file via python-dotenv).
All modules import from here — never hardcode values elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Base paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

# ── Storage ───────────────────────────────────────────────────────────────────
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")   # "local" | "cloudinary"
LOCAL_UPLOAD_DIR: Path = BASE_DIR / "uploads"
LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────────────
DB_DIR: Path = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_DIR / 'lookitup.db'}")

# ── Celery / Redis ────────────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Face Engine ───────────────────────────────────────────────────────────────
INSIGHTFACE_MODEL_NAME: str = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")
FACE_EMBEDDING_DIM: int = 512

# ── Vector Index ──────────────────────────────────────────────────────────────
FAISS_INDEX_DIR: Path = BASE_DIR / "vector_index" / "index_store"
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
SIMILARITY_CONFIDENT: float = 0.75   # score > this → "confident"
SIMILARITY_POSSIBLE: float = 0.55    # score > this → "possible"

# ── API ───────────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200"))
ALLOWED_IMAGE_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".webp"}

# ── Cloudinary (only needed if STORAGE_BACKEND=cloudinary) ───────────────────
CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
