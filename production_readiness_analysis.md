# LookItUp Codebase Analysis & Production Readiness Report

## Executive Summary
This report analyzes the LookItUp codebase to assess its readiness for production deployment and outlines several critical architectural improvements, bug fixes, and security hardening recommendations.

The current system has transitioned from a local vector index (FAISS) to a cloud-friendly database vector engine (Supabase/PostgreSQL with `pgvector`). While this transition is a significant improvement for cloud scalability, there are several blocker-level bugs, design limitations, and security concerns that must be addressed before the app is production-ready.

---

## 1. Blocker: Single-Face Embedding Limitation (Critical Design Flaw)
### The Issue
Currently, the database schema (`Photo` model) and the ingestion pipeline store only **one** face embedding per photo.
- In `backend/database/models.py`, the `Photo` table has a single `embedding = Column(Vector(512), nullable=True)` column.
- In `backend/ingestion/pipeline.py` (lines 83-85), the ingestion process detects all faces in the photo, but selects only the first face and discards the rest:
  ```python
  face_embeddings = FaceEngine.detect_and_embed(photo_bytes)
  face_count = len(face_embeddings)
  first_embedding = face_embeddings[0].vector.tolist() if face_count > 0 else None
  ```
- **Impact:** In social events (weddings, parties, conferences), photos commonly feature group shots. If a photo has multiple people, only the first person detected by the engine will be searchable. The other attendees will not be able to find the photo, rendering the core value proposition of the app broken.

### Proposed Architectural Solution
We must decouple photos from face embeddings by introducing a one-to-many relationship:
1. **Create a `Face` (or `PhotoFace`) Table:**
   ```python
   class PhotoFace(Base):
       __tablename__ = "photo_faces"
       
       id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
       photo_id = Column(String(36), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True)
       bbox = Column(String(64), nullable=True)  # Bounding box coordinates [x1, y1, x2, y2]
       embedding = Column(Vector(512), nullable=False)
       confidence = Column(Float, nullable=True)
       
       photo = relationship("Photo", back_populates="faces")
   ```
2. **Update the Ingestion Pipeline:**
   Insert one row into `photo_faces` for *every* detected face in `face_embeddings`.
3. **Update the Search Logic (`crud.py`):**
   Query the `photo_faces` table to find matching faces, then join with `photos` to retrieve the unique photos containing those matches:
   ```python
   async def search_photos_by_embedding(db: AsyncSession, event_id: str, query_embedding: list, limit: int = 50, threshold: float = 0.55):
       similarity_expr = (1 - PhotoFace.embedding.cosine_distance(query_embedding)).label("similarity")
       
       result = await db.execute(
           select(Photo, similarity_expr)
           .join(PhotoFace, Photo.id == PhotoFace.photo_id)
           .where(Photo.event_id == event_id)
           .where(similarity_expr >= threshold)
           .order_by(similarity_expr.desc())
           .limit(limit)
       )
       return result.all()
   ```

---

## 2. Broken Test Suite & Missing Modules
### The Issue
The test suite is completely broken because of the `pgvector` migration.
1. **Deleted `vector_index` Module:**
   The `backend/vector_index` directory was deleted when moving to `pgvector`. However, `tests/test_api_search.py` and `tests/test_vector_index_unit.py` still attempt to import from and mock `backend.vector_index`.
2. **Missing Database Parameters in Tests:**
   In `test_database.py` and `test_api_search.py`, helper methods call `crud.create_event(async_db, name=...)` without passing `organizer_id`. Since `organizer_id` is now a non-nullable foreign key, all these tests fail with DB integrity errors.
3. **Missing Dependencies in Dev Environment:**
   If `STORAGE_BACKEND` is set to `cloudinary` in the `.env` file, the import statements in `backend/storage/storage_service.py` execute dynamic imports which raise `ModuleNotFoundError: No module named 'cloudinary'` unless `cloudinary` is installed.

### Recommendation
1. Delete obsolete `test_vector_index_unit.py`.
2. Refactor `test_api_search.py` to test the new `pgvector` search flow (mocking `crud.search_photos_by_embedding` instead of the nonexistent `VectorIndex.search`).
3. Update all test setups in `tests/test_database.py` and `tests/test_api_search.py` to create a mock organizer and pass `organizer_id` when calling `crud.create_event`.

---

## 3. ZIP File Handling & Processing Bugs
### The Issue
1. **API vs Test Type Mismatch:**
   In `backend/ingestion/batch_processor.py` (lines 34-35), `extract_images_from_zip(zip_path: str)` expects a file path string and runs `zipfile.is_zipfile(zip_path)`.
   However, `tests/test_batch_processor.py` passes raw ZIP `bytes` directly, causing `UnicodeDecodeError: 'utf-8' codec can't decode...` on Windows when `open` attempts to read the bytes object as a filepath.
2. **macOS/Hidden File Exclusion Regex Check:**
   The code tries to ignore system files using:
   ```python
   if name.endswith("/") or name.startswith("__MACOSX") or name.startswith("."):
       continue
   ```
   If files are inside subdirectories (e.g. `wedding_photos/__MACOSX/._photo.jpg` or `photos/.DS_Store`), they do *not* start with `__MACOSX` or `.`, so they bypass this filter and cause ingestion pipeline issues.

### Recommendation
1. Update `extract_images_from_zip` to accept both file-like objects (e.g. `BytesIO`, upload streams) and string paths:
   ```python
   import io
   def extract_images_from_zip(zip_file_or_path):
       if isinstance(zip_file_or_path, bytes):
           zip_file_or_path = io.BytesIO(zip_file_or_path)
       # ...
   ```
2. Refactor the path segment exclusion check:
   ```python
   parts = name.split('/')
   if any(p.startswith('.') or p == '__MACOSX' for p in parts):
       continue
   ```

---

## 4. Performance: Celery Event Loop Overhead
### The Issue
In `backend/ingestion/tasks.py` and `pipeline.py`, the Celery worker runs in a synchronous thread context. To call asynchronous storage and database operations, it invokes `asyncio.run(...)` on every loop iteration:
- `asyncio.run(StorageService.save_photo(...))` inside `process_single_photo`.
- `asyncio.run(_mark_processed(...))` for each photo processed in `process_album_task`.
- `asyncio.run(_mark_event_ready(...))` after processing.
- **Impact:** Spawning and destroying an asyncio event loop for every single photo adds significant thread/CPU overhead and makes connection pooling less efficient.

### Recommendation
Manage a single asyncio loop lifecycle per Celery task, or use synchronous database and storage clients inside the sync Celery tasks. Since Celery workers are already running in a synchronous process pool, making synchronous queries to PostgreSQL/Cloudinary would be simpler and perform better.

---

## 5. Deployment & DB Initialization Concerns
### The Issue
1. **Missing pgvector Extension Creation:**
   SQLAlchemy's `Base.metadata.create_all` does not automatically install the `pgvector` extension in PostgreSQL. If the extension is not pre-installed on the PostgreSQL host, app initialization fails.
2. **Missing index on Vector column:**
   There is no HNSW index created on the vector column. For larger albums (thousands of photos), a linear search will slow down.

### Recommendation
1. In `backend/database/db.py`, execute the extension check before tables are created:
   ```python
   async def init_db() -> None:
       async with engine.begin() as conn:
           await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))
           await conn.run_sync(Base.metadata.create_all)
   ```
2. Add an HNSW or IVFFlat index to the vector column in `models.py` to speed up similarity queries when scaling.

---

## 6. Security Hardening & Rate Limiting
### The Issue
1. **Hardcoded JWT Secret:**
   `SECRET_KEY` in `backend/api/auth.py` defaults to `"super-secret-key-change-in-prod"`.
2. **No Rate Limiting:**
   FastAPI endpoints like `/api/auth/register`, `/api/auth/login`, and `/api/events/{share_token}/search` are open to abuse. Since face detection and embedding extraction are highly resource-intensive, a simple flood of requests on `/search` can easily exhaust CPU/GPU resources and crash the service (DoS).

### Recommendation
1. Enforce environment variable check for `JWT_SECRET` in production and raise an exception if it is missing or set to the default dev key.
2. Implement rate-limiting middleware (e.g. using `slowapi` or Redis-based rate limiters) on public-facing endpoints, especially the selfie-search endpoint.
