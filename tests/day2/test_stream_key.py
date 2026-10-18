import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.crypto import sign_day2
from app.domain.models import db_state
from app.domain.streaming import streaming_domain

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_state(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", "T01D27ad7ffff12e")
    db_state.seed_baseline()
    streaming_domain.reset()


def test_generate_stream_key():
    payload = {
        "action": "generate",
        "player_id": "player-alpha-1",
        "label": "main_rig",
    }
    res = client.post("/audit/v1/stream/key", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["player_id"] == "player-alpha-1"
    assert data["label"] == "main_rig"
    assert data["status"] == "active"
    assert data["stream_key"].startswith("sk_live_")
    assert "rtmp" in data["ingest_endpoints"]
    assert "webrtc" in data["ingest_endpoints"]
    assert data["playback_url"] == f"http://localhost:8888/live/{data['stream_key']}/index.m3u8"

    expected_sig = sign_day2(
        data["stream_key"],
        {
            "action": "generate",
            "player_id": "player-alpha-1",
            "status": "active",
            "stream_key": data["stream_key"],
        },
    )
    assert data["signature"] == expected_sig


def test_stream_key_override_verbatim():
    payload = {
        "action": "generate",
        "player_id": "player-alpha-1",
        "stream_key_override": "sk_live_custom123456",
    }
    res = client.post("/audit/v1/stream/key", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["stream_key"] == "sk_live_custom123456"


def test_rotate_stream_key():
    # First generate
    res1 = client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "player-alpha-1"})
    key1 = res1.json()["stream_key"]

    # Rotate
    res2 = client.post("/audit/v1/stream/key", json={"action": "rotate", "player_id": "player-alpha-1"})
    assert res2.status_code == 200
    data2 = res2.json()
    key2 = data2["stream_key"]
    assert key2 != key1
    assert data2["status"] == "active"

    # Old key publish should be rejected with 409
    res_pub1 = client.post("/audit/v1/stream/publish", json={"stream_key": key1})
    assert res_pub1.status_code == 409
    assert res_pub1.json()["error"]["code"] == "KEY_REVOKED"

    # New key publish should be allowed
    res_pub2 = client.post("/audit/v1/stream/publish", json={"stream_key": key2})
    assert res_pub2.status_code == 200


def test_revoke_stream_key():
    res1 = client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "player-alpha-1"})
    key1 = res1.json()["stream_key"]

    res_rev = client.post("/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-alpha-1"})
    assert res_rev.status_code == 200
    data = res_rev.json()
    assert data["status"] == "revoked"
    assert data["ingest_endpoints"] is None
    assert data["playback_url"] is None

    # Revoke again -> 404 STREAM_NOT_FOUND
    res_rev2 = client.post("/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-alpha-1"})
    assert res_rev2.status_code == 404
    assert res_rev2.json()["error"]["code"] == "STREAM_NOT_FOUND"


def test_validation_errors():
    # Invalid action
    res = client.post("/audit/v1/stream/key", json={"action": "invalid_action", "player_id": "player-alpha-1"})
    assert res.status_code == 400
    assert "action" in res.json()["error"]["details"]["fields"]

    # Unknown player
    res = client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "player-nonexistent"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_guest_write_forbidden_stream_key():
    headers = {"Authorization": "Bearer guest_anon_tok_7721"}
    res = client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "player-alpha-1"}, headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "GUEST_WRITE_FORBIDDEN"
