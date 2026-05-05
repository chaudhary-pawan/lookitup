"""
test_face_engine.py — Standalone test for M5 (Face Engine)
============================================================
Run this FIRST before touching FastAPI or Celery.
It confirms InsightFace is installed correctly and embeddings work.

Usage:
    python tests/test_face_engine.py path/to/group_photo.jpg path/to/selfie.jpg

Expected output:
    [PASS] Loaded face model
    [PASS] Detected N faces in group photo
    [PASS] Extracted embeddings: shape (512,)
    [PASS] embed_single on selfie: shape (512,)
    [PASS] Cosine similarity between face 0 and selfie: 0.XXXX
"""

import sys
import os
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.face_engine import FaceEngine
from backend.face_engine.model_loader import get_face_analysis_model
from backend.face_engine.exceptions import NoFaceDetectedError


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    group_photo_path = sys.argv[1] if len(sys.argv) > 1 else None
    selfie_path = sys.argv[2] if len(sys.argv) > 2 else None

    # ── Test 1: Model loads ────────────────────────────────────────────────────
    print("Loading InsightFace model (first run downloads ~200MB)...")
    model = get_face_analysis_model()
    print(f"[PASS] Loaded face model: {model}")

    # ── Test 2: detect_and_embed on a group photo ──────────────────────────────
    if group_photo_path:
        with open(group_photo_path, "rb") as f:
            photo_bytes = f.read()

        embeddings = FaceEngine.detect_and_embed(photo_bytes)
        print(f"[PASS] Detected {len(embeddings)} face(s) in group photo")

        for i, emb in enumerate(embeddings):
            print(f"  Face {i}: confidence={emb.confidence:.3f}, bbox={emb.bbox}, vector shape={emb.vector.shape}")

    # ── Test 3: embed_single on a selfie ──────────────────────────────────────
    if selfie_path:
        with open(selfie_path, "rb") as f:
            selfie_bytes = f.read()

        try:
            selfie_vec = FaceEngine.embed_single(selfie_bytes)
            print(f"[PASS] embed_single on selfie: shape={selfie_vec.shape}")
        except NoFaceDetectedError as e:
            print(f"[FAIL] No face in selfie: {e}")
            return

    # ── Test 4: Similarity between selfie and first group photo face ───────────
    if group_photo_path and selfie_path and embeddings:
        sim = cosine_similarity(embeddings[0].vector, selfie_vec)
        print(f"[INFO] Cosine similarity (face 0 vs selfie): {sim:.4f}")
        if sim > 0.5:
            print("[PASS] Same person detected (similarity > 0.5)")
        else:
            print("[INFO] Different people (similarity < 0.5) — expected if using different test images")

    print("\nAll tests complete.")


if __name__ == "__main__":
    main()
