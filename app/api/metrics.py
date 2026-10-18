from __future__ import annotations
from fastapi import APIRouter, Response
from app.domain.observability import observability_domain

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    content = observability_domain.get_metrics_prometheus_text()
    return Response(
        content=content,
        status_code=200,
        headers={"Content-Type": "text/plain; version=0.0.4"},
    )
