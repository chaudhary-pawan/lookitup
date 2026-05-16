"""
test_middleware.py — Unit tests for M1 middleware
==================================================
Tests:
  - UploadSizeLimitMiddleware: allows small requests,
    rejects oversized ones via Content-Length,
    ignores GET requests

Coverage type: UNIT (middleware only, mounted on minimal Starlette app)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import Request

from backend.api.middleware.validation import UploadSizeLimitMiddleware
import backend.config as cfg


# ══════════════════════════════════════════════════════════════════════════════
# Minimal FastAPI app to test middleware in isolation
# ══════════════════════════════════════════════════════════════════════════════

def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(UploadSizeLimitMiddleware)

    @app.post("/upload")
    @app.get("/upload")
    async def upload_endpoint(request: Request):
        return JSONResponse({"ok": True})

    return app


@pytest.fixture
def middleware_client():
    return _make_app()


# ══════════════════════════════════════════════════════════════════════════════
# UploadSizeLimitMiddleware tests
# ══════════════════════════════════════════════════════════════════════════════

class TestUploadSizeLimitMiddleware:
    @pytest.mark.asyncio
    async def test_small_post_passes_through(self, middleware_client):
        transport = ASGITransport(app=middleware_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/upload",
                content=b"\x00" * 100,
                headers={"Content-Length": "100", "Content-Type": "application/octet-stream"},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_oversized_post_returns_413(self, middleware_client):
        max_bytes = cfg.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        transport = ASGITransport(app=middleware_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/upload",
                content=b"\x00",
                headers={
                    "Content-Length": str(max_bytes + 1),
                    "Content-Type": "application/octet-stream",
                },
            )
        assert resp.status_code == 413

    @pytest.mark.asyncio
    async def test_get_request_not_checked(self, middleware_client):
        """GET requests should never be rejected by the upload limit middleware."""
        max_bytes = cfg.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        transport = ASGITransport(app=middleware_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/upload",
                headers={"Content-Length": str(max_bytes + 999_999)},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_content_length_header_passes(self, middleware_client):
        """Chunked transfers (no Content-Length) should not be rejected by this middleware."""
        transport = ASGITransport(app=middleware_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/upload",
                content=b"\x00" * 50,
                # No Content-Length header
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_exactly_at_limit_passes(self, middleware_client):
        max_bytes = cfg.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        transport = ASGITransport(app=middleware_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/upload",
                content=b"\x00",
                headers={
                    "Content-Length": str(max_bytes),  # exactly at limit → should pass
                    "Content-Type": "application/octet-stream",
                },
            )
        assert resp.status_code == 200
