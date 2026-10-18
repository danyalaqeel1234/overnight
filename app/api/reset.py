from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppException
from app.domain.models import db_state

router = APIRouter()


@router.post("/audit/v1/reset")
async def reset(request: Request):
    body = {}
    try:
        raw = await request.body()
        if raw:
            import json
            body = json.loads(raw)
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    if not isinstance(body, dict):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    seed = body.get("seed", 42)
    stock = body.get("stock", None)

    if not isinstance(seed, int) or isinstance(seed, bool):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": ["seed"]}, 400)

    custom_stock: dict | None = None
    if stock is not None:
        if not isinstance(stock, dict):
            raise AppException("VALIDATION_ERROR", "Validation error", {"fields": ["stock"]}, 400)
        custom_stock = stock

    db_state.seed_baseline(seed=seed, custom_stock=custom_stock)
    from app.domain.streaming import streaming_domain
    from app.domain.costream import costream_domain
    from app.domain.qr_guest import qr_guest_domain
    from app.domain.moderation_dlq import moderation_dlq_domain
    from app.domain.observability import observability_domain
    streaming_domain.reset()
    costream_domain.reset()
    qr_guest_domain.reset()
    moderation_dlq_domain.reset()
    observability_domain.reset()

    snap = db_state.stock_snapshot()
    return JSONResponse(
        status_code=200,
        content={
            "status": "reset_complete",
            "seed": seed,
            "sports": ["football", "basketball", "cricket", "esports"],
            "tenants": ["tenant-alpha", "tenant-beta"],
            "stock": snap,
        },
    )
