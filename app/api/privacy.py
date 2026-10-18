from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.domain.observability import observability_domain

router = APIRouter()


@router.delete("/audit/v1/privacy/user/{user_id}")
async def anonymize_user_data(user_id: str):
    res = observability_domain.anonymize_user(user_id)
    return JSONResponse(status_code=200, content=res)
