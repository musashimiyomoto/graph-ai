"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Response

from api.metrics import render_latest

router = APIRouter(tags=["Metrics"])


@router.get(path="/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics in text exposition format (unauthenticated)."""
    payload, content_type = render_latest()
    return Response(content=payload, media_type=content_type)
