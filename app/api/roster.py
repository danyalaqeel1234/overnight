from __future__ import annotations
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppException
from app.domain.roster import setup_roster, transfer_player, get_history

router = APIRouter()


@router.post("/audit/v1/roster/setup")
async def roster_setup(request: Request):
    try:
        data = json.loads(await request.body() or b"{}")
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
    result = setup_roster(data)
    return JSONResponse(status_code=201, content=result)


@router.post("/audit/v1/roster/transfer")
async def roster_transfer(request: Request):
    try:
        data = json.loads(await request.body() or b"{}")
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
    status_code, result = transfer_player(data)
    return JSONResponse(status_code=status_code, content=result)


@router.get("/audit/v1/roster/history/{player_id}")
async def roster_history(player_id: str, as_of: str | None = None):
    result = get_history(player_id, as_of)
    return JSONResponse(status_code=200, content=result)
