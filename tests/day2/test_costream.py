import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.crypto import sign_day2
from app.domain.models import db_state
from app.domain.costream import costream_domain

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_state(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", "T01D27ad7ffff12e")
    db_state.seed_baseline()
    costream_domain.reset()


def test_create_costream_session_success():
    payload = {
        "session_id": "cs-session-101",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1"],
        "layout": "grid_4",
    }
    res = client.post("/audit/v1/costream/session", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["session_id"] == "cs-session-101"
    assert data["status"] == "active"
    assert data["active_host"] == "player-alpha-1"
    assert data["handoff_occurred"] is False
    assert data["participant_count"] == 3
    assert data["active_participants"] == ["player-alpha-1", "player-alpha-2", "player-beta-1"]
    assert data["composite_playback_url"] == "http://localhost:8888/costream/cs-session-101/index.m3u8"
    assert data["chat_room_id"] == "chat-cs-session-101"

    expected_sig = sign_day2(
        "cs-session-101",
        {
            "active_host": "player-alpha-1",
            "handoff_occurred": False,
            "layout": "grid_4",
            "participant_count": 3,
            "session_id": "cs-session-101",
            "status": "active",
        },
    )
    assert data["signature"] == expected_sig


def test_costream_host_drop_handoff():
    # Hidden Scenario 1: host drop promotes remaining[0]
    payload = {
        "session_id": "cs-session-101",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1", "player-beta-2"],
        "simulate_host_drop": True,
        "layout": "grid_4",
    }
    res = client.post("/audit/v1/costream/session", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "active"
    assert data["active_host"] == "player-alpha-2"
    assert data["handoff_occurred"] is True
    assert data["participant_count"] == 3
    assert data["active_participants"] == ["player-alpha-2", "player-beta-1", "player-beta-2"]
    assert data["composite_playback_url"] == "http://localhost:8888/costream/cs-session-101/index.m3u8"
    assert data["chat_room_id"] == "chat-cs-session-101"


def test_costream_host_drop_single_participant_terminates():
    payload = {
        "session_id": "cs-session-single",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1"],
        "simulate_host_drop": True,
        "layout": "solo",
    }
    res = client.post("/audit/v1/costream/session", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "terminated"
    assert data["active_host"] is None
    assert data["handoff_occurred"] is False
    assert data["participant_count"] == 0
    assert data["active_participants"] == []


def test_costream_check_order_unknown_player_before_full():
    # 5 participants with an unknown player -> must return 404 PLAYER_NOT_FOUND, NOT 409
    payload = {
        "session_id": "cs-session-5",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1", "player-beta-2", "player-unknown"],
    }
    res = client.post("/audit/v1/costream/session", json=payload)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_costream_5_participants_all_exist_returns_409():
    # 5 participants where all exist -> 409 COSTREAM_SESSION_FULL
    # Temporarily add player-alpha-3
    db_state.players["player-alpha-3"] = {"player_id": "player-alpha-3", "club_id": "club-alpha-1"}
    payload = {
        "session_id": "cs-session-5-real",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-alpha-3", "player-beta-1", "player-beta-2"],
    }
    res = client.post("/audit/v1/costream/session", json=payload)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "COSTREAM_SESSION_FULL"


def test_costream_unsupported_layout():
    # solo with 2 participants
    payload = {
        "session_id": "cs-solo-fail",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2"],
        "layout": "solo",
    }
    res = client.post("/audit/v1/costream/session", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "UNSUPPORTED_LAYOUT"

    # grid_2 with 3 participants without drop -> 400
    payload2 = {
        "session_id": "cs-grid2-fail",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1"],
        "layout": "grid_2",
    }
    res2 = client.post("/audit/v1/costream/session", json=payload2)
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "UNSUPPORTED_LAYOUT"

    # grid_2 with 3 participants WITH host drop -> effective count 2 -> 201 OK
    payload3 = {
        "session_id": "cs-grid2-ok",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1"],
        "layout": "grid_2",
        "simulate_host_drop": True,
    }
    res3 = client.post("/audit/v1/costream/session", json=payload3)
    assert res3.status_code == 201
    assert res3.json()["participant_count"] == 2


def test_costream_guest_token_forbidden():
    headers = {"Authorization": "Bearer guest_anon_tok_7721"}
    payload = {
        "session_id": "cs-guest",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2"],
    }
    res = client.post("/audit/v1/costream/session", json=payload, headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "GUEST_WRITE_FORBIDDEN"
