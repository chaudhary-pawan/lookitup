"""
test_vector_index.py — Standalone test for M6 (Vector Index)
==============================================================
Tests FAISS index add, search, save, and load without touching the face engine.
Uses random vectors as mock embeddings.

Usage:
    python tests/test_vector_index.py
"""

import sys
import os
import numpy as np
import shutil
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.vector_index import VectorIndex, SearchResult
from backend import config

# Override index directory to a temp dir for testing
_temp_dir = tempfile.mkdtemp()
config.FAISS_INDEX_DIR = __import__("pathlib").Path(_temp_dir)


def make_embedding(seed: int = None) -> np.ndarray:
    """Random normalized 512-dim vector."""
    if seed is not None:
        np.random.seed(seed)
    vec = np.random.randn(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


def main():
    event_id = "test_event_001"
    target_photo_id = "photo_with_my_face"
    other_photo_ids = [f"photo_{i}" for i in range(20)]

    # ── Test 1: Add embeddings ─────────────────────────────────────────────────
    # Target: use seed 42 for reproducibility
    target_embedding = make_embedding(seed=42)
    VectorIndex.add(target_embedding, target_photo_id, event_id)

    for i, pid in enumerate(other_photo_ids):
        VectorIndex.add(make_embedding(seed=i + 100), pid, event_id)

    print(f"[PASS] Added {1 + len(other_photo_ids)} embeddings to index")

    # ── Test 2: Search — query with same vector (should return target) ─────────
    results = VectorIndex.search(
        query_embedding=target_embedding,   # exact match → score should be ~1.0
        event_id=event_id,
    )

    assert len(results) > 0, "Search returned no results"
    top_result = results[0]
    print(f"[PASS] Search returned {len(results)} result(s)")
    print(f"  Top result: photo_id={top_result.photo_id}, score={top_result.similarity:.4f}, tier={top_result.tier}")
    assert top_result.photo_id == target_photo_id, f"Expected {target_photo_id}, got {top_result.photo_id}"
    assert top_result.similarity > 0.99, f"Expected similarity ~1.0, got {top_result.similarity}"
    print(f"[PASS] Top result is the target photo with similarity {top_result.similarity:.4f}")

    # ── Test 3: Save and reload index ─────────────────────────────────────────
    VectorIndex.save_index(event_id)
    print(f"[PASS] Index saved to disk")

    # Clear in-memory cache
    from backend.vector_index import index as vi_module
    vi_module._indices.clear()
    vi_module._id_maps.clear()

    # Reload from disk and search again
    results_after_reload = VectorIndex.search(
        query_embedding=target_embedding,
        event_id=event_id,
    )
    assert results_after_reload[0].photo_id == target_photo_id
    print(f"[PASS] Index reloaded from disk — search still returns correct result")

    # ── Cleanup ────────────────────────────────────────────────────────────────
    shutil.rmtree(_temp_dir, ignore_errors=True)
    print("\nAll vector index tests passed.")


if __name__ == "__main__":
    main()
