"""
M5 — Face Engine Data Models
==============================
Dataclasses that define the data contracts flowing out of the Face Engine.
Other modules import these types — they do NOT import from engine.py directly.
"""

from dataclasses import dataclass, field
from typing import List
import numpy as np


@dataclass
class FaceEmbedding:
    """
    A single detected face + its embedding vector.

    Produced by: FaceEngine.detect_and_embed()
    Consumed by: M3 Ingestion Pipeline → M6 VectorIndex.add()
    """
    vector: np.ndarray      # shape: (512,), dtype: float32
    bbox: List[int]         # [x1, y1, x2, y2] — pixel coords in original image
    confidence: float       # detection confidence score: 0.0 – 1.0

    def __post_init__(self):
        assert self.vector.shape == (512,), f"Expected 512-dim vector, got {self.vector.shape}"
        assert 0.0 <= self.confidence <= 1.0, f"Confidence must be in [0, 1], got {self.confidence}"
