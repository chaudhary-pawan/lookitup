"""
M1 — API Gateway: Request Validation Middleware
================================================
Validates incoming requests before they reach route handlers.
Keeps validation logic out of route files.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.config import MAX_UPLOAD_SIZE_MB

MAX_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects requests whose Content-Length exceeds the configured limit.
    This is a fast early rejection — content is not read.

    Note: For chunked encoding (no Content-Length), limit is enforced
    per-file in the route handler instead.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request body too large. Max allowed: {MAX_UPLOAD_SIZE_MB}MB"
                )
        return await call_next(request)
