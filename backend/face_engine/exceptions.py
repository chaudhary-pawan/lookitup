"""
M5 — Face Engine Exceptions
=============================
Custom exceptions raised by the Face Engine.
The API Gateway catches these and converts them to appropriate HTTP responses.
"""


class NoFaceDetectedError(Exception):
    """Raised when a selfie image contains no detectable face."""
    pass


class MultipleFacesError(Exception):
    """
    Raised when a selfie contains more than one face.
    Selfie queries must be unambiguous — exactly one face.
    """
    pass


class ModelNotLoadedError(Exception):
    """Raised if the InsightFace model singleton failed to initialize."""
    pass
