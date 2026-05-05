"""
M5 — Face Processing Engine
============================
The ML core of LookItUp. This is the only module that knows about InsightFace.
Everything else in the system is ML-agnostic.

Public API:
    FaceEngine.detect_and_embed(image_bytes) -> List[FaceEmbedding]
    FaceEngine.embed_single(image_bytes)     -> np.ndarray
"""

import cv2
import numpy as np
from typing import List

from backend.face_engine.model_loader import get_face_analysis_model
from backend.face_engine.models import FaceEmbedding
from backend.face_engine.exceptions import NoFaceDetectedError, MultipleFacesError


class FaceEngine:
    """
    Stateless class that wraps InsightFace (ArcFace) for face detection
    and embedding extraction.

    The underlying model is loaded once at process startup via model_loader.py
    (singleton pattern) to avoid repeated disk I/O.
    """

    @staticmethod
    def detect_and_embed(image_bytes: bytes) -> List[FaceEmbedding]:
        """
        Detects all faces in an image and returns one embedding per face.

        Used by: M3 Ingestion Pipeline (batch processing event photos)

        Args:
            image_bytes: Raw bytes of an image file (JPEG, PNG, WebP).

        Returns:
            List of FaceEmbedding objects — one per detected face.
            Empty list if no faces are found (non-fatal for event photos).

        Pipeline:
            bytes → cv2.imdecode → insightface.get(img) → List[FaceEmbedding]
        """
        model = get_face_analysis_model()

        # Decode bytes to numpy array (BGR format, OpenCV standard)
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Could not decode image bytes. File may be corrupted.")

        # InsightFace returns Face objects with .embedding (512-dim) and .bbox
        faces = model.get(img)

        results: List[FaceEmbedding] = []
        for face in faces:
            embedding = FaceEmbedding(
                vector=face.embedding.astype(np.float32),
                bbox=[int(x) for x in face.bbox],
                confidence=float(face.det_score),
            )
            results.append(embedding)

        return results

    @staticmethod
    def embed_single(image_bytes: bytes) -> np.ndarray:
        """
        Extracts a single face embedding from a selfie image.

        Used by: M1 API Gateway (when an attendee submits their selfie for search)

        Args:
            image_bytes: Raw bytes of the selfie image.

        Returns:
            512-dimensional float32 numpy array — the face embedding.

        Raises:
            NoFaceDetectedError: If no face is found in the selfie.
            MultipleFacesError:  If more than one face is detected (ambiguous selfie).
        """
        embeddings = FaceEngine.detect_and_embed(image_bytes)

        if len(embeddings) == 0:
            raise NoFaceDetectedError("No face detected in the selfie. Please retake.")

        if len(embeddings) > 1:
            raise MultipleFacesError(
                f"{len(embeddings)} faces detected. Please submit a selfie with only your face."
            )

        return embeddings[0].vector
