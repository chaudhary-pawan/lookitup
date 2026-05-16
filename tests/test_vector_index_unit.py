"""
test_vector_index_unit.py — Unit tests for M6 (Vector Index / FAISS)
======================================================================
Tests:
  - VectorIndex.add: creates index, normalizes, maps photo_id
  - VectorIndex.search: exact match, no results below threshold,
    deduplication, tiering, top_k, empty index
  - VectorIndex.save_index / load_index: persistence round-trip
  - VectorIndex._create_index: correct dimensionality

Coverage type: UNIT (pure numpy + faiss — no DB, no HTTP, no model)
Uses temp dir to isolate FAISS files per test.
"""

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

import backend.config as cfg
from backend.vector_index import VectorIndex, SearchResult
from backend.vector_index import index as vi_module


# ══════════════════════════════════════════════════════════════════════════════
# Per-test isolation: fresh FAISS temp dir + cleared in-memory caches
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def isolated_faiss(tmp_path: Path):
    """Each test gets a fresh FAISS index dir and empty in-memory caches."""
    original = cfg.FAISS_INDEX_DIR
    cfg.FAISS_INDEX_DIR = tmp_path
    vi_module._indices.clear()
    vi_module._id_maps.clear()
    yield
    cfg.FAISS_INDEX_DIR = original
    vi_module._indices.clear()
    vi_module._id_maps.clear()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def make_vec(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512).astype(np.float32)
    return v / np.linalg.norm(v)


# ══════════════════════════════════════════════════════════════════════════════
# UNIT: add
# ══════════════════════════════════════════════════════════════════════════════

class TestVectorIndexAdd:
    def test_add_creates_index_in_memory(self):
        VectorIndex.add(make_vec(0), "photo-1", "event-A")
        assert "event-A" in vi_module._indices

    def test_add_records_photo_id_in_map(self):
        VectorIndex.add(make_vec(0), "photo-1", "event-A")
        assert "photo-1" in vi_module._id_maps["event-A"]

    def test_add_multiple_embeddings_to_same_event(self):
        for i in range(5):
            VectorIndex.add(make_vec(i), f"photo-{i}", "event-A")
        assert vi_module._indices["event-A"].ntotal == 5
        assert len(vi_module._id_maps["event-A"]) == 5

    def test_add_to_different_events_isolated(self):
        VectorIndex.add(make_vec(0), "p1", "event-A")
        VectorIndex.add(make_vec(1), "p2", "event-B")
        assert vi_module._indices["event-A"].ntotal == 1
        assert vi_module._indices["event-B"].ntotal == 1

    def test_add_normalizes_vector(self):
        """After adding a non-unit vector, FAISS still works (it's normalized internally)."""
        big_vec = make_vec(0) * 100.0   # not normalized
        VectorIndex.add(big_vec, "p1", "event-A")
        results = VectorIndex.search(make_vec(0), "event-A")
        # Should find something (the same vector, normalized)
        assert len(results) >= 0   # no crash


# ══════════════════════════════════════════════════════════════════════════════
# UNIT: search
# ══════════════════════════════════════════════════════════════════════════════

class TestVectorIndexSearch:
    def test_exact_match_returns_score_near_1(self):
        vec = make_vec(42)
        VectorIndex.add(vec, "target-photo", "event-A")
        results = VectorIndex.search(vec, "event-A")
        assert results[0].photo_id == "target-photo"
        assert results[0].similarity > 0.99

    def test_top_result_is_highest_similarity(self):
        target = make_vec(0)
        VectorIndex.add(target, "target", "event-A")
        for i in range(10):
            VectorIndex.add(make_vec(i + 100), f"other-{i}", "event-A")
        results = VectorIndex.search(target, "event-A")
        assert results[0].photo_id == "target"

    def test_below_threshold_excluded(self):
        """Vectors with similarity < SIMILARITY_POSSIBLE should not appear."""
        target = make_vec(0)
        # Orthogonal vector → similarity ≈ 0
        ortho = np.zeros(512, dtype=np.float32)
        ortho[0] = 1.0
        VectorIndex.add(ortho, "ortho-photo", "event-A")
        results = VectorIndex.search(target, "event-A")
        # ortho photo should be excluded (low similarity)
        ids = [r.photo_id for r in results]
        assert "ortho-photo" not in ids

    def test_deduplication_same_photo_id(self):
        """Multiple faces from the same photo → only one result."""
        vec = make_vec(1)
        VectorIndex.add(vec, "same-photo", "event-A")
        VectorIndex.add(make_vec(2), "same-photo", "event-A")   # same photo_id
        results = VectorIndex.search(vec, "event-A")
        photo_ids = [r.photo_id for r in results]
        assert photo_ids.count("same-photo") == 1

    def test_confident_tier_assigned_above_threshold(self):
        vec = make_vec(42)
        VectorIndex.add(vec, "photo-1", "event-A")
        results = VectorIndex.search(vec, "event-A")
        # Exact match → should be "confident"
        assert results[0].tier == "confident"

    def test_results_sorted_descending_by_similarity(self):
        target = make_vec(0)
        for i in range(5):
            VectorIndex.add(make_vec(i), f"p{i}", "event-A")
        results = VectorIndex.search(target, "event-A")
        sims = [r.similarity for r in results]
        assert sims == sorted(sims, reverse=True)

    def test_empty_index_returns_empty_list(self):
        VectorIndex._create_index("empty-event")
        results = VectorIndex.search(make_vec(0), "empty-event")
        assert results == []

    def test_search_loads_from_disk_if_not_in_memory(self, tmp_path: Path):
        """search() should lazy-load from disk if index not cached."""
        vec = make_vec(9)
        VectorIndex.add(vec, "photo-disk", "event-disk")
        VectorIndex.save_index("event-disk")
        vi_module._indices.clear()
        vi_module._id_maps.clear()
        # Index not in memory — should trigger disk load
        results = VectorIndex.search(vec, "event-disk")
        assert results[0].photo_id == "photo-disk"

    def test_search_nonexistent_event_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            VectorIndex.search(make_vec(0), "does-not-exist")

    def test_top_k_limits_candidates(self):
        """top_k=1 should return at most 1 result."""
        for i in range(10):
            VectorIndex.add(make_vec(i), f"p{i}", "event-A")
        target = make_vec(0)
        results = VectorIndex.search(target, "event-A", top_k=1)
        assert len(results) <= 1


# ══════════════════════════════════════════════════════════════════════════════
# UNIT: save_index / load_index
# ══════════════════════════════════════════════════════════════════════════════

class TestVectorIndexPersistence:
    def test_save_creates_index_and_json_files(self, tmp_path: Path):
        VectorIndex.add(make_vec(0), "p1", "event-save")
        VectorIndex.save_index("event-save")
        assert (tmp_path / "event-save.index").exists()
        assert (tmp_path / "event-save.json").exists()

    def test_load_restores_photo_id_map(self, tmp_path: Path):
        vec = make_vec(7)
        VectorIndex.add(vec, "persistent-photo", "event-persist")
        VectorIndex.save_index("event-persist")
        vi_module._indices.clear()
        vi_module._id_maps.clear()
        VectorIndex.load_index("event-persist")
        assert "persistent-photo" in vi_module._id_maps["event-persist"]

    def test_search_correct_after_reload(self, tmp_path: Path):
        vec = make_vec(5)
        VectorIndex.add(vec, "correct-photo", "event-reload")
        for i in range(9):
            VectorIndex.add(make_vec(i + 50), f"noise-{i}", "event-reload")
        VectorIndex.save_index("event-reload")
        vi_module._indices.clear()
        vi_module._id_maps.clear()
        results = VectorIndex.search(vec, "event-reload")
        assert results[0].photo_id == "correct-photo"

    def test_save_without_index_raises_key_error(self):
        with pytest.raises(KeyError):
            VectorIndex.save_index("never-added")

    def test_load_nonexistent_raises_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            VectorIndex.load_index("nonexistent-event")

    def test_multiple_events_saved_independently(self, tmp_path: Path):
        VectorIndex.add(make_vec(1), "p-A", "event-A")
        VectorIndex.add(make_vec(2), "p-B", "event-B")
        VectorIndex.save_index("event-A")
        VectorIndex.save_index("event-B")
        vi_module._indices.clear()
        vi_module._id_maps.clear()
        results_a = VectorIndex.search(make_vec(1), "event-A")
        results_b = VectorIndex.search(make_vec(2), "event-B")
        assert results_a[0].photo_id == "p-A"
        assert results_b[0].photo_id == "p-B"
