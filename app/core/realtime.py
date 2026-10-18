from __future__ import annotations
import asyncio
from typing import Any
from fastapi import WebSocket
from app.domain.observability import observability_domain


class RealtimeHub:
    def __init__(self) -> None:
        # topic -> set of WebSocket connections
        self.subscribers: dict[str, set[WebSocket]] = {}
        # topic -> set of asyncio.Queue for SSE
        self.sse_queues: dict[str, set[asyncio.Queue]] = {}

    def reset(self) -> None:
        self.subscribers.clear()
        self.sse_queues.clear()

    async def connect_ws(self, topic: str, ws: WebSocket) -> None:
        await ws.accept()
        subs = self.subscribers.setdefault(topic, set())
        subs.add(ws)
        observability_domain.active_ws_connections += 1

    def disconnect_ws(self, topic: str, ws: WebSocket) -> None:
        subs = self.subscribers.get(topic)
        if subs and ws in subs:
            subs.remove(ws)
            observability_domain.active_ws_connections = max(0, observability_domain.active_ws_connections - 1)

    async def broadcast(self, topic: str, message: dict[str, Any]) -> None:
        import json
        text = json.dumps(message)

        # 1. Broadcast to WebSockets
        subs = list(self.subscribers.get(topic, []))
        for ws in subs:
            try:
                await ws.send_text(text)
            except Exception:
                self.disconnect_ws(topic, ws)

        # 2. Broadcast to SSE queues
        queues = list(self.sse_queues.get(topic, []))
        for q in queues:
            try:
                q.put_nowait(text)
            except Exception:
                pass


realtime_hub = RealtimeHub()
