import os
import socket
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.domain.models import db_state

router = APIRouter()

_dep_ok_until = 0.0


def _deps_ready() -> bool:
    """TCP-probe DB, Redis, MinIO and the media server (set via NASCON_DEP_CHECK in compose)."""
    global _dep_ok_until
    spec = os.environ.get("NASCON_DEP_CHECK", "").strip()
    if not spec:
        return True
    now = time.monotonic()
    if now < _dep_ok_until:
        return True
    for target in spec.split(","):
        host, _, port = target.strip().rpartition(":")
        try:
            with socket.create_connection((host, int(port)), timeout=0.3):
                pass
        except (OSError, ValueError):
            return False
    _dep_ok_until = now + 2.0
    return True


@router.get("/health")
def health_check():
    if not db_state.is_ready() or not _deps_ready():
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
