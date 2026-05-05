"""
M6 — Vector Index Data Models
================================
Dataclasses for data flowing OUT of the Vector Index module.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class SearchResult:
    """
    A single photo match returned from VectorIndex.search().

    Produced by: M6 VectorIndex
    Consumed by: M1 API Gateway → serialized to JSON → M7 Frontend
    """
    photo_id: str
    similarity: float                          # cosine similarity: 0.0 – 1.0
    tier: Literal["confident", "possible"]     # "confident" > 0.75, "possible" > 0.55
