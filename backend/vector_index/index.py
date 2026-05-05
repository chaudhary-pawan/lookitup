"""
M6 — Vector Index Module (FAISS)
==================================
Stores and searches face embeddings using Facebook's FAISS library.

Each event has its own isolated FAISS index.
Searching 10,000 face embeddings takes <10ms — this is what makes LookItUp fast.

Public API:
    VectorIndex.add(embedding, photo_id, event_id)
    VectorIndex.search(query_embedding, event_id) -> List[SearchResult]
    VectorIndex.save_index(event_id)
    VectorIndex.load_index(event_id)
"""

import numpy as np
import faiss
import json
from pathlib import Path
from typing import List, Dict

from backend.config import (
    FAISS_INDEX_DIR,
    FACE_EMBEDDING_DIM,
    SIMILARITY_CONFIDENT,
    SIMILARITY_POSSIBLE,
)
from backend.vector_index.models import SearchResult


# In-memory cache: event_id → (faiss.Index, id_map)
# id_map: list of photo_ids parallel to FAISS internal indices
_indices: Dict[str, faiss.IndexFlatIP] = {}
_id_maps: Dict[str, List[str]] = {}


class VectorIndex:
    """
    Manages per-event FAISS flat inner-product indices.

    Why Inner Product (IP)?
        We L2-normalize all embeddings before storage, making IP equivalent
        to cosine similarity — the standard metric for face verification.
    """

    @staticmethod
    def add(embedding: np.ndarray, photo_id: str, event_id: str) -> None:
        """
        Adds a single face embedding to the event's FAISS index.

        Called by: M3 Ingestion Pipeline (once per face detected in a photo)

        Args:
            embedding: 512-dim float32 vector from FaceEngine.
            photo_id:  The photo this face belongs to (from M2/M4).
            event_id:  Which event's index to add to.
        """
        if event_id not in _indices:
            VectorIndex._create_index(event_id)

        # L2-normalize for cosine similarity via inner product
        vec = embedding.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)

        _indices[event_id].add(vec)
        _id_maps[event_id].append(photo_id)

    @staticmethod
    def search(
        query_embedding: np.ndarray,
        event_id: str,
        top_k: int = 50,
        threshold: float = SIMILARITY_POSSIBLE,
    ) -> List[SearchResult]:
        """
        Searches the event index for faces similar to the query embedding.

        Called by: M1 API Gateway (attendee selfie search)

        Args:
            query_embedding: 512-dim float32 vector from FaceEngine.embed_single()
            event_id:        Which event to search.
            top_k:           Max number of raw candidates to fetch from FAISS.
            threshold:       Minimum cosine similarity to include in results.

        Returns:
            List of SearchResult, sorted by similarity (descending).
            Each result has a confidence tier: "confident" or "possible".
        """
        if event_id not in _indices:
            VectorIndex.load_index(event_id)   # lazy load from disk

        index = _indices[event_id]
        id_map = _id_maps[event_id]

        if index.ntotal == 0:
            return []

        # Normalize query vector
        vec = query_embedding.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)

        # Search — returns scores and integer indices into the index
        actual_k = min(top_k, index.ntotal)
        scores, faiss_indices = index.search(vec, actual_k)

        results: List[SearchResult] = []
        seen_photo_ids = set()   # deduplicate: multiple faces from same photo

        for score, idx in zip(scores[0], faiss_indices[0]):
            if idx == -1 or score < threshold:
                continue

            photo_id = id_map[idx]

            # Deduplicate — take the best score for each photo
            if photo_id in seen_photo_ids:
                continue
            seen_photo_ids.add(photo_id)

            # Assign confidence tier
            if score >= SIMILARITY_CONFIDENT:
                tier = "confident"
            else:
                tier = "possible"

            results.append(SearchResult(
                photo_id=photo_id,
                similarity=float(score),
                tier=tier,
            ))

        return sorted(results, key=lambda r: r.similarity, reverse=True)

    @staticmethod
    def save_index(event_id: str) -> None:
        """
        Persists the FAISS index + id_map to disk.

        Called by: M3 Ingestion Pipeline (after all photos processed)

        Files created:
            {FAISS_INDEX_DIR}/{event_id}.index   ← FAISS binary index
            {FAISS_INDEX_DIR}/{event_id}.json    ← photo_id mapping
        """
        if event_id not in _indices:
            raise KeyError(f"No in-memory index found for event '{event_id}'")

        index_path = FAISS_INDEX_DIR / f"{event_id}.index"
        map_path = FAISS_INDEX_DIR / f"{event_id}.json"

        faiss.write_index(_indices[event_id], str(index_path))

        with open(map_path, "w") as f:
            json.dump(_id_maps[event_id], f)

    @staticmethod
    def load_index(event_id: str) -> None:
        """
        Loads a previously saved FAISS index from disk into memory.

        Called lazily by VectorIndex.search() if event not in memory.

        Raises:
            FileNotFoundError: If no saved index exists for this event.
        """
        index_path = FAISS_INDEX_DIR / f"{event_id}.index"
        map_path = FAISS_INDEX_DIR / f"{event_id}.json"

        if not index_path.exists():
            raise FileNotFoundError(
                f"No FAISS index on disk for event '{event_id}'. "
                "Ingestion may not be complete yet."
            )

        _indices[event_id] = faiss.read_index(str(index_path))

        with open(map_path, "r") as f:
            _id_maps[event_id] = json.load(f)

    @staticmethod
    def _create_index(event_id: str) -> None:
        """Internal: creates a new empty flat IP index for an event."""
        _indices[event_id] = faiss.IndexFlatIP(FACE_EMBEDDING_DIM)
        _id_maps[event_id] = []
