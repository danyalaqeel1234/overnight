from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.domain.models import db_state

router = APIRouter()


@router.get("/health")
def health_check():
    if not db_state.is_ready():
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
