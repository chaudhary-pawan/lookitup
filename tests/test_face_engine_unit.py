"""
test_face_engine_unit.py — Unit tests for M5 (Face Engine)
===========================================================
Tests FaceEngine.detect_and_embed and FaceEngine.embed_single
by mocking the InsightFace model — no model download required.

Coverage type: UNIT (mock-based — no real model loading)
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from backend.face_engine.engine import FaceEngine
from backend.face_engine.exceptions import NoFaceDetectedError, MultipleFacesError
from backend.face_engine.models import FaceEmbedding


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


def _make_mock_face(embedding_seed: int = 0) -> MagicMock:
    """Builds a mock InsightFace Face object."""
    rng = np.random.default_rng(embedding_seed)
    vec = rng.standard_normal(512).astype(np.float32)
    face = MagicMock()
    face.embedding = vec
    face.bbox = [10.0, 20.0, 110.0, 120.0]
    face.det_score = 0.98
    return face


def _mock_model(faces: list) -> MagicMock:
    model = MagicMock()
    model.get.return_value = faces
    return model


# ══════════════════════════════════════════════════════════════════════════════
# detect_and_embed
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectAndEmbed:
    def test_returns_list_of_face_embeddings(self):
        mock_faces = [_make_mock_face(0), _make_mock_face(1)]
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model(mock_faces)),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            results = FaceEngine.detect_and_embed(FAKE_JPEG)
        assert len(results) == 2
        assert all(isinstance(r, FaceEmbedding) for r in results)

    def test_embedding_vector_is_512_dim(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([_make_mock_face(0)])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            results = FaceEngine.detect_and_embed(FAKE_JPEG)
        assert results[0].vector.shape == (512,)

    def test_embedding_vector_is_float32(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([_make_mock_face(0)])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            results = FaceEngine.detect_and_embed(FAKE_JPEG)
        assert results[0].vector.dtype == np.float32

    def test_returns_empty_list_for_no_faces(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            results = FaceEngine.detect_and_embed(FAKE_JPEG)
        assert results == []

    def test_corrupted_image_raises_value_error(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([])),
            patch("cv2.imdecode", return_value=None),   # cv2 fails to decode
        ):
            with pytest.raises(ValueError, match="Could not decode"):
                FaceEngine.detect_and_embed(b"not-an-image")

    def test_confidence_score_is_stored(self):
        mock_face = _make_mock_face(0)
        mock_face.det_score = 0.95
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([mock_face])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            results = FaceEngine.detect_and_embed(FAKE_JPEG)
        assert abs(results[0].confidence - 0.95) < 1e-5

    def test_bbox_is_stored_as_ints(self):
        mock_face = _make_mock_face(0)
        mock_face.bbox = [10.7, 20.3, 100.9, 200.1]
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([mock_face])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            results = FaceEngine.detect_and_embed(FAKE_JPEG)
        assert all(isinstance(x, int) for x in results[0].bbox)

    def test_five_faces_returns_five_embeddings(self):
        mock_faces = [_make_mock_face(i) for i in range(5)]
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model(mock_faces)),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            results = FaceEngine.detect_and_embed(FAKE_JPEG)
        assert len(results) == 5


# ══════════════════════════════════════════════════════════════════════════════
# embed_single
# ══════════════════════════════════════════════════════════════════════════════

class TestEmbedSingle:
    def test_returns_512_dim_vector_for_single_face(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([_make_mock_face(0)])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            result = FaceEngine.embed_single(FAKE_JPEG)
        assert result.shape == (512,)

    def test_raises_no_face_detected_error_for_empty_image(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            with pytest.raises(NoFaceDetectedError):
                FaceEngine.embed_single(FAKE_JPEG)

    def test_raises_multiple_faces_error_for_two_faces(self):
        mock_faces = [_make_mock_face(0), _make_mock_face(1)]
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model(mock_faces)),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            with pytest.raises(MultipleFacesError):
                FaceEngine.embed_single(FAKE_JPEG)

    def test_raises_multiple_faces_error_for_many_faces(self):
        mock_faces = [_make_mock_face(i) for i in range(10)]
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model(mock_faces)),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            with pytest.raises(MultipleFacesError) as exc_info:
                FaceEngine.embed_single(FAKE_JPEG)
            assert "10" in str(exc_info.value)

    def test_error_message_mentions_retake_for_no_face(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            with pytest.raises(NoFaceDetectedError) as exc_info:
                FaceEngine.embed_single(FAKE_JPEG)
            assert "retake" in str(exc_info.value).lower()

    def test_returns_numpy_array(self):
        with (
            patch("backend.face_engine.engine.get_face_analysis_model",
                  return_value=_mock_model([_make_mock_face(0)])),
            patch("cv2.imdecode", return_value=np.zeros((100, 100, 3), dtype=np.uint8)),
        ):
            result = FaceEngine.embed_single(FAKE_JPEG)
        assert isinstance(result, np.ndarray)
