"""
M5 — Face Engine Model Loader
===============================
Singleton pattern: loads the InsightFace FaceAnalysis model ONCE at startup.

Why a singleton?
- InsightFace loads ~200MB ONNX weights from disk.
- Loading per-request would add 3–5 seconds per API call.
- One shared instance is safe for concurrent reads (inference is read-only).

Usage:
    from backend.face_engine.model_loader import get_face_analysis_model
    model = get_face_analysis_model()   # returns cached instance

Note: insightface is imported lazily (inside _load_model) so this module can
be safely imported in test environments where insightface is not installed,
as long as get_face_analysis_model() itself is mocked.
"""

from typing import Any

from backend.config import INSIGHTFACE_MODEL_NAME
from backend.face_engine.exceptions import ModelNotLoadedError

_model_instance: Any = None


def get_face_analysis_model() -> Any:
    """
    Returns the global FaceAnalysis model, loading it on first call.

    The model is prepared for CPU inference by default.
    Set ctx_id=0 for GPU (CUDA device 0).
    """
    global _model_instance

    if _model_instance is None:
        _model_instance = _load_model()

    return _model_instance


def _load_model() -> Any:
    """Internal: loads and prepares the InsightFace model (lazy import)."""
    try:
        # Lazy import — insightface is only needed at runtime, not import time.
        # This allows test collection without insightface installed.
        from insightface.app import FaceAnalysis  # noqa: PLC0415

        app = FaceAnalysis(
            name=INSIGHTFACE_MODEL_NAME,
            providers=["CPUExecutionProvider"],   # swap to CUDAExecutionProvider for GPU
        )
        # det_size: detection input resolution.
        # (640, 640) balances accuracy and speed for group photos.
        app.prepare(ctx_id=-1, det_size=(640, 640))
        return app
    except Exception as e:
        raise ModelNotLoadedError(
            f"Failed to load InsightFace model '{INSIGHTFACE_MODEL_NAME}': {e}"
        ) from e
