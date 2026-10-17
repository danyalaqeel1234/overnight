from __future__ import annotations
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppException
from app.domain.store import checkout, get_inventory

router = APIRouter()


@router.post("/audit/v1/checkout")
async def do_checkout(request: Request):
    try:
        data = json.loads(await request.body() or b"{}")
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
    status_code, result = checkout(data)
    return JSONResponse(status_code=status_code, content=result)


@router.get("/audit/v1/inventory/{variant_id}")
async def inventory(variant_id: str):
    result = get_inventory(variant_id)
    return JSONResponse(status_code=200, content=result)
