# LookItUp

> Face-recognition-powered photo retrieval for events.  
> Attendees find all their photos from a 500-photo album — with a single selfie.

---

## Project Architecture

7 modules, each with a single responsibility:

| Module | Folder | Role |
|--------|--------|------|
| M1 — API Gateway | `backend/api/` | HTTP routing & validation |
| M2 — Storage | `backend/storage/` | File I/O (local → Cloudinary) |
| M3 — Ingestion Pipeline | `backend/ingestion/` | Orchestrates batch processing |
| M4 — Database Layer | `backend/database/` | Event & photo metadata (SQLite/PostgreSQL) |
| M5 — Face Engine ⭐ | `backend/face_engine/` | InsightFace/ArcFace — core ML |
| M6 — Vector Index | `backend/vector_index/` | FAISS nearest-neighbor search |
| M7 — Frontend | `frontend/` | React + Vite + Webcam API |

---

## Quick Start (Development)

### 1. Install backend dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set up environment
```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 3. Start Redis (required for Celery)
```bash
# Option A: Docker
docker run -d -p 6379:6379 redis:7-alpine

# Option B: Windows WSL
wsl redis-server
```

### 4. Run the API
```bash
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```
API docs: http://localhost:8000/docs

### 5. Run the Celery worker (separate terminal)
```bash
celery -A backend.celery_app worker --loglevel=info --concurrency=1
```

### 6. Run the frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Development Build Order

Build and test each module in isolation before wiring together:

```
Step 1: M5 Face Engine    → tests/test_face_engine.py
Step 2: M6 Vector Index   → tests/test_vector_index.py
Step 3: M4 DB Layer       → (covered by API integration tests)
Step 4: M2 Storage        → (simple file I/O, tested inline)
Step 5: M3 Ingestion      → wire M2 + M5 + M6 together
Step 6: M1 API Gateway    → expose everything via HTTP
Step 7: M7 Frontend       → build when API is stable
```

---

## Full Stack (Docker Compose)

```bash
docker-compose up --build
```

Services:
- **API**: http://localhost:8000
- **Frontend**: http://localhost:5173
- **Redis**: localhost:6379

---

## Tech Stack

- **Face Detection + Embedding**: InsightFace (ArcFace model)
- **Vector Search**: FAISS (cosine similarity)
- **Backend**: FastAPI + SQLAlchemy + Celery + Redis
- **Database**: SQLite (dev) → PostgreSQL (prod)
- **Storage**: Local disk (dev) → Cloudinary (prod)
- **Frontend**: React + Vite + Webcam API
- **Infra**: Docker Compose

---

## Resume Highlights

- **Product:** LookItUp is an AI-powered full-stack photo retrieval platform that allows event attendees to instantly find their photos from massive albums using a single selfie.
- **Target Audience:** Designed for event organizers (weddings, corporate events, parties) to seamlessly distribute media, and for attendees to effortlessly retrieve their personal photos.
- **Impact & Traction:** Eliminates the need to manually scroll through hundreds of images, saving hours of search time per attendee while drastically increasing photo engagement and download rates for organizers.
- **Technical Achievements:** Engineered a scalable, privacy-first backend utilizing InsightFace (ArcFace) for extracting 512-dimensional face embeddings, pgvector/FAISS for high-speed similarity search, and Celery + Redis for asynchronous processing of large image batches.
