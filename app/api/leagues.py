from __future__ import annotations
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppException
from app.domain.leagues import create_league

router = APIRouter()


@router.post("/audit/v1/leagues")
async def register_league(request: Request):
    try:
        data = json.loads(await request.body() or b"{}")
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
    if not isinstance(data, dict):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
    result = create_league(data)
    return JSONResponse(status_code=201, content=result)
