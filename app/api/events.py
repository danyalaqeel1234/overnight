from __future__ import annotations
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppException
from app.domain.scoring import add_event, project_match
from app.domain.models import db_state

router = APIRouter()


@router.post("/audit/v1/events")
async def post_event(request: Request):
    try:
        data = json.loads(await request.body() or b"{}")
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
    if not isinstance(data, dict):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
    status_code, result = add_event(data)
    if status_code in (200, 201):
        match_id = data.get("match_id")
        if match_id:
            proj = project_match(match_id)
            if proj:
                h = proj["home"]["score"]
                a = proj["away"]["score"]
                from app.core.realtime import realtime_hub
                await realtime_hub.broadcast(
                    f"match:{match_id}",
                    {
                        "type": "score_update",
                        "match_id": match_id,
                        "status": proj["status"],
                        "score": {"home": h, "away": a},
                        "display": f"{h} - {a}",
                        "seq": result.get("sequence", 1),
                    },
                )
    return JSONResponse(status_code=status_code, content=result)


@router.get("/audit/v1/score/{match_id}")
async def get_score(match_id: str):
    state = project_match(match_id)
    if state is None:
        raise AppException("MATCH_NOT_FOUND", f"Match '{match_id}' not found.", {}, 404)
    return JSONResponse(status_code=200, content=state)
