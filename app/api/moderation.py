from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppException
from app.domain.moderation_dlq import moderation_dlq_domain

router = APIRouter()


@router.post("/audit/v1/moderation/test")
async def test_moderation(request: Request):
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

    chat_room_id = body.get("chat_room_id")
    if not isinstance(chat_room_id, str) or not chat_room_id.strip():
        invalid_fields.append("chat_room_id")

    incoming_messages = body.get("incoming_messages")
    if not isinstance(incoming_messages, list):
        invalid_fields.append("incoming_messages")
    else:
        for m in incoming_messages:
            if not isinstance(m, dict):
                invalid_fields.append("incoming_messages")
                break
            if not isinstance(m.get("message_id"), str) or not isinstance(m.get("sender"), str) or not isinstance(m.get("text"), str):
                invalid_fields.append("incoming_messages")
                break

    check_dlq = body.get("check_dlq", True)
    if not isinstance(check_dlq, bool):
        invalid_fields.append("check_dlq")

    sim_failed = body.get("simulate_failed_notifications", 0)
    if isinstance(sim_failed, bool) or not isinstance(sim_failed, int) or sim_failed < 0:
        invalid_fields.append("simulate_failed_notifications")

    if invalid_fields:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": invalid_fields}, 400)

    result = moderation_dlq_domain.process_moderation(
        chat_room_id=chat_room_id,
        incoming_messages=incoming_messages,
        check_dlq=check_dlq,
        simulate_failed_notifications=sim_failed,
    )
    return JSONResponse(status_code=200, content=result)
