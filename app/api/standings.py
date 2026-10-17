from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.domain.standings import _compute_standings

router = APIRouter()


@router.get("/audit/v1/standings/{league_id}")
async def get_standings(league_id: str):
    result = _compute_standings(league_id)
    return JSONResponse(status_code=200, content=result)
