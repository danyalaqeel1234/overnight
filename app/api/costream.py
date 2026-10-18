from __future__ import annotations

import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppException
from app.core.crypto import sign_day2
from app.domain.models import db_state

router = APIRouter()

_ALLOWED_LAYOUTS = ("solo", "grid_2", "grid_4", "spotlight")


@router.post("/audit/v1/costream/session")
async def create_costream_session(request: Request):
    try:
        raw = await request.body()
        if not raw:
            raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
        body = json.loads(raw)
    except AppException:
        raise
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    if not isinstance(body, dict):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    # 1. Schema validation
    invalid_fields: list[str] = []

    session_id = body.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        invalid_fields.append("session_id")

    host_player_id = body.get("host_player_id")
    if not isinstance(host_player_id, str) or not host_player_id:
        invalid_fields.append("host_player_id")

    participants = body.get("participants")
    if not isinstance(participants, list) or len(participants) == 0:
        invalid_fields.append("participants")
    elif len(participants) != len(set(participants)):
        invalid_fields.append("participants")
    elif not all(isinstance(p, str) for p in participants):
        invalid_fields.append("participants")

    layout = body.get("layout", "grid_4")
    if layout not in _ALLOWED_LAYOUTS:
        invalid_fields.append("layout")

    simulate_host_drop = body.get("simulate_host_drop", False)
    if not isinstance(simulate_host_drop, bool):
        invalid_fields.append("simulate_host_drop")

    if invalid_fields:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": invalid_fields}, 400)

    # host_player_id must be in participants
    if isinstance(participants, list) and isinstance(host_player_id, str):
        if host_player_id not in participants:
            raise AppException("VALIDATION_ERROR", "host_player_id must be in participants", {"fields": ["host_player_id"]}, 400)

    # 2. Participant existence
    all_players = list(set(participants) | {host_player_id})
    for pid in all_players:
        if pid not in db_state.players:
            raise AppException("PLAYER_NOT_FOUND", f"Player {pid} not found", {"player_id": pid}, 404)

    # 3. Maximum capacity
    if len(participants) > 4:
        raise AppException("COSTREAM_SESSION_FULL", "Co-stream session is full", {}, 409)

    # 4. Layout capacity
    if simulate_host_drop and len(participants) >= 2:
        effective_active_count = len(participants) - 1
    elif simulate_host_drop and len(participants) == 1:
        effective_active_count = 0
    else:
        effective_active_count = len(participants)

    if layout == "solo" and effective_active_count > 1:
        raise AppException("UNSUPPORTED_LAYOUT", "Layout does not support this participant count", {}, 400)
    if layout == "grid_2" and effective_active_count > 2:
        raise AppException("UNSUPPORTED_LAYOUT", "Layout does not support this participant count", {}, 400)

    # 5. Host drop handoff
    if not simulate_host_drop:
        active_host = host_player_id
        handoff_occurred = False
        participant_count = len(participants)
        active_participants = list(participants)
        status = "active"
    elif len(participants) >= 2:
        active_participants = [p for p in participants if p != host_player_id]
        active_host = active_participants[0]
        handoff_occurred = True
        participant_count = len(active_participants)
        status = "active"
    else:
        active_participants = []
        active_host = None
        handoff_occurred = False
        participant_count = 0
        status = "terminated"

    # Idempotency check
    request_snapshot = {
        "session_id": session_id,
        "host_player_id": host_player_id,
        "participants": list(participants),
        "layout": layout,
        "simulate_host_drop": simulate_host_drop,
    }
    if session_id in db_state.costream_sessions:
        existing = db_state.costream_sessions[session_id]
        if existing.get("_request") == request_snapshot:
            payload = {k: v for k, v in existing.items() if k != "_request"}
            return JSONResponse(status_code=200, content=payload)

    composite_playback_url = f"http://localhost:8888/costream/{session_id}/index.m3u8"
    chat_room_id = f"chat-{session_id}"

    sig_payload = {
        "active_host": active_host,
        "handoff_occurred": handoff_occurred,
        "layout": layout,
        "participant_count": participant_count,
        "session_id": session_id,
        "status": status,
    }
    signature = sign_day2(session_id, sig_payload)

    response_body = {
        "session_id": session_id,
        "status": status,
        "active_host": active_host,
        "handoff_occurred": handoff_occurred,
        "participant_count": participant_count,
        "active_participants": active_participants,
        "layout": layout,
        "composite_playback_url": composite_playback_url,
        "chat_room_id": chat_room_id,
        "signature": signature,
    }

    db_state.costream_sessions[session_id] = {**response_body, "_request": request_snapshot}
    return JSONResponse(status_code=201, content=response_body)
