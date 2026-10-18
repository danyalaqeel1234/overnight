from __future__ import annotations
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from app.core.realtime import realtime_hub

router = APIRouter()


@router.websocket("/ws/matches/{match_id}")
async def ws_match_scores(websocket: WebSocket, match_id: str):
    topic = f"match:{match_id}"
    await realtime_hub.connect_ws(topic, websocket)
    try:
        while True:
            # Keep socket alive and accept incoming pings
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        realtime_hub.disconnect_ws(topic, websocket)


@router.websocket("/ws/chat/{room_id}")
async def ws_chat_room(websocket: WebSocket, room_id: str):
    topic = f"chat:{room_id}"
    await realtime_hub.connect_ws(topic, websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        realtime_hub.disconnect_ws(topic, websocket)


@router.websocket("/ws/costream/{session_id}")
async def ws_costream(websocket: WebSocket, session_id: str):
    topic = f"costream:{session_id}"
    await realtime_hub.connect_ws(topic, websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        realtime_hub.disconnect_ws(topic, websocket)


@router.get("/api/v1/matches/{match_id}/stream")
async def sse_match_stream(match_id: str):
    topic = f"match:{match_id}"
    queue: asyncio.Queue = asyncio.Queue()
    subs = realtime_hub.sse_queues.setdefault(topic, set())
    subs.add(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        finally:
            if queue in subs:
                subs.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
