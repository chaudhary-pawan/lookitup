# ── Backend Dockerfile ────────────────────────────────────────────────────────
# Build context is the PROJECT ROOT (so `backend` is a proper Python package).
# Used for both the FastAPI service and the Celery worker.

FROM python:3.11-slim

# System libs needed by OpenCV-headless and InsightFace native bindings
# Note: libgl1-mesa-glx was removed in Debian 12 — use libgl1 instead
# build-essential provides g++ needed to compile insightface's Cython extension
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cached layer — only reruns if requirements.txt changes)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential

# Pre-download the InsightFace model weights (~200MB) at build time
# so containers start instantly. Skipped silently if download fails (CI/offline).
RUN python -c "\
from insightface.app import FaceAnalysis; \
m = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider']); \
m.prepare(ctx_id=-1, det_size=(640,640)); \
print('InsightFace model ready')" || echo "Model pre-download skipped"

# Copy the entire project so `import backend.xxx` works correctly
COPY backend/ ./backend/

EXPOSE 8000
