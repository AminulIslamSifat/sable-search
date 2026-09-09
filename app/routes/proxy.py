"""Raw SearXNG proxy — exposes SearXNG's port 8080 through SSE's public URL."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()

# SearXNG's public Render URL (Render services can't resolve each other by name)
import os
SEARXNG_INTERNAL = os.environ.get("SSE_SEARXNG_URL", "https://sable-searxng.onrender.com").rstrip("/")


@router.api_route("/searxng/{path:path}", methods=["GET", "POST", "HEAD"])
async def proxy_searxng(path: str, request: Request) -> Response:
    """Proxy any request directly to the SearXNG instance on port 8080.

    Usage: GET /searxng/search?q=test&format=json
    Forwards to: http://sable-searxng:8080/search?q=test&format=json
    """
    url = f"{SEARXNG_INTERNAL}/{path}"
    if request.query_params:
        url = f"{url}?{request.query_params}"

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "connection", "content-length")
    }

    body = await request.body() if request.method in ("POST", "PUT") else None

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )

    # Strip hop-by-hop headers
    excluded = {"transfer-encoding", "connection", "keep-alive"}
    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=resp.headers.get("content-type", "application/json"),
    )
