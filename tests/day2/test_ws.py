import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.realtime import realtime_hub

client = TestClient(app)


def test_ws_match_connection():
    with client.websocket_connect("/ws/matches/match-m1") as ws:
        assert realtime_hub.subscribers.get("match:match-m1") is not None
        assert len(realtime_hub.subscribers["match:match-m1"]) >= 1


def test_ws_chat_connection():
    with client.websocket_connect("/ws/chat/chat-room-1") as ws:
        assert realtime_hub.subscribers.get("chat:chat-room-1") is not None
        assert len(realtime_hub.subscribers["chat:chat-room-1"]) >= 1


def test_ws_costream_connection():
    with client.websocket_connect("/ws/costream/cs-session-101") as ws:
        assert realtime_hub.subscribers.get("costream:cs-session-101") is not None
        assert len(realtime_hub.subscribers["costream:cs-session-101"]) >= 1
