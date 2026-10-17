from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

from app.core.errors import AppException
from app.domain.models import db_state
from app.domain.sports import validate_and_normalise

router = APIRouter()


@router.post("/audit/v1/sports")
async def create_sport(request: Request):
    try:
        raw = await request.body()
        data = json.loads(raw) if raw else {}
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    if not isinstance(data, dict):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    config = validate_and_normalise(data)
    sport_id = config["sport_id"]

    if sport_id in db_state.sports:
        raise AppException("SPORT_EXISTS", f"Sport '{sport_id}' already exists.", {}, 409)

    db_state.sports[sport_id] = config

    return JSONResponse(
        status_code=201,
        content={"sport_id": sport_id, "status": "created", "config": config},
    )
