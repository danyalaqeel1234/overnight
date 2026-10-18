from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppException
from app.domain.streaming import streaming_domain

router = APIRouter()


@router.post("/audit/v1/stream/key")
async def handle_stream_key(request: Request):
    try:
        raw = await request.body()
        if not raw:
            raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
        import json
        body = json.loads(raw)
    except AppException:
        raise
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    if not isinstance(body, dict):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    invalid_fields: list[str] = []
    action = body.get("action")
    if action not in ("generate", "rotate", "revoke"):
        invalid_fields.append("action")

    player_id = body.get("player_id")
    if not isinstance(player_id, str) or not player_id.strip():
        invalid_fields.append("player_id")

    label = body.get("label", "default")
    if label is not None:
        if not isinstance(label, str) or not (1 <= len(label) <= 64):
            invalid_fields.append("label")
    else:
        label = "default"

    override = body.get("stream_key_override")
    if override is not None and not isinstance(override, str):
        invalid_fields.append("stream_key_override")

    if invalid_fields:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": invalid_fields}, 400)

    if action == "generate":
        result = streaming_domain.generate_key(player_id, label=label, stream_key_override=override)
        return JSONResponse(status_code=201, content=result)
    elif action == "rotate":
        result = streaming_domain.rotate_key(player_id, label=label, stream_key_override=override)
        return JSONResponse(status_code=200, content=result)
    elif action == "revoke":
        result = streaming_domain.revoke_key(player_id)
        return JSONResponse(status_code=200, content=result)


@router.post("/audit/v1/stream/publish")
async def handle_publish_check(request: Request):
    body = await request.json() if await request.body() else {}
    stream_key = body.get("stream_key", "")
    streaming_domain.check_publish(stream_key)
    return JSONResponse(status_code=200, content={"status": "allowed", "stream_key": stream_key})


@router.post("/internal/media/auth")
async def handle_media_auth(request: Request):
    """
    Webhook handler invoked by MediaMTX when a publisher/viewer connects.
    """
    body = await request.json() if await request.body() else {}
    path = body.get("path", "")
    action = body.get("action", "publish")

    if path.startswith("live/"):
        key = path[5:]
        if action == "publish":
            try:
                streaming_domain.check_publish(key)
                return JSONResponse(status_code=200, content={"status": "ok"})
            except AppException as e:
                return JSONResponse(status_code=e.status_code, content={"error": e.code})
    return JSONResponse(status_code=200, content={"status": "ok"})
