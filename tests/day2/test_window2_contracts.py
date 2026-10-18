"""Window 2 Backend Contracts — comprehensive test suite."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.crypto import sign, sign_day2
from app.domain.models import db_state
from app.domain.streaming import streaming_domain

client = TestClient(app, follow_redirects=False)

DAY2_SALT = "T01D27ad7ffff12e"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", DAY2_SALT)
    db_state.seed_baseline()
    streaming_domain.reset()


# ---------------------------------------------------------------------------
# Appendix A — Test Vector 1
# ---------------------------------------------------------------------------

def test_reference_vector_1():
    entity_id = "sk_live_9f83a1b2c3d4e5f6"
    sig_payload = {
        "action": "rotate",
        "player_id": "player-alpha-1",
        "status": "active",
        "stream_key": "sk_live_9f83a1b2c3d4e5f6",
    }
    computed = sign(DAY2_SALT, entity_id, sig_payload)
    assert computed == "9bd054eb746844b4701c6f158209c315ef2b16f392efd733bdf0715940610289"


# ---------------------------------------------------------------------------
# POST /audit/v1/stream/key
# ---------------------------------------------------------------------------

def test_stream_key_generate_201():
    res = client.post("/audit/v1/stream/key", json={
        "action": "generate", "player_id": "player-alpha-1", "label": "cam1"
    })
    assert res.status_code == 201
    d = res.json()
    assert d["player_id"] == "player-alpha-1"
    assert d["label"] == "cam1"
    assert d["status"] == "active"
    assert d["stream_key"].startswith("sk_live_")
    assert d["ingest_endpoints"]["rtmp"] == f"rtmp://localhost:1935/live/{d['stream_key']}"
    assert d["ingest_endpoints"]["webrtc"] == f"http://localhost:8889/live/{d['stream_key']}/whip"
    assert d["playback_url"] == f"http://localhost:8888/live/{d['stream_key']}/index.m3u8"
    expected_sig = sign_day2(d["stream_key"], {
        "action": "generate", "player_id": "player-alpha-1",
        "status": "active", "stream_key": d["stream_key"],
    })
    assert d["signature"] == expected_sig


def test_stream_key_rotate_200():
    client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "player-alpha-1"})
    res = client.post("/audit/v1/stream/key", json={"action": "rotate", "player_id": "player-alpha-1"})
    assert res.status_code == 200
    d = res.json()
    assert d["status"] == "active"
    assert d["stream_key"].startswith("sk_live_")
    expected_sig = sign_day2(d["stream_key"], {
        "action": "rotate", "player_id": "player-alpha-1",
        "status": "active", "stream_key": d["stream_key"],
    })
    assert d["signature"] == expected_sig


def test_stream_key_revoke_200():
    gen = client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "player-alpha-1"})
    sk = gen.json()["stream_key"]
    res = client.post("/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-alpha-1"})
    assert res.status_code == 200
    d = res.json()
    assert d["status"] == "revoked"
    assert d["ingest_endpoints"] is None
    assert d["playback_url"] is None
    expected_sig = sign_day2(sk, {
        "action": "revoke", "player_id": "player-alpha-1",
        "status": "revoked", "stream_key": sk,
    })
    assert d["signature"] == expected_sig


def test_stream_key_revoke_nonexistent_404():
    res = client.post("/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-alpha-1"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "STREAM_NOT_FOUND"


def test_stream_key_unknown_player_404():
    res = client.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "no-such-player"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_stream_key_invalid_action_400():
    res = client.post("/audit/v1/stream/key", json={"action": "hack", "player_id": "player-alpha-1"})
    assert res.status_code == 400
    assert "action" in res.json()["error"]["details"]["fields"]


# ---------------------------------------------------------------------------
# POST /audit/v1/costream/session
# ---------------------------------------------------------------------------

def test_costream_4way_201():
    res = client.post("/audit/v1/costream/session", json={
        "session_id": "cs-w2-001",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1", "player-beta-2"],
        "layout": "grid_4",
    })
    assert res.status_code == 201
    d = res.json()
    assert d["session_id"] == "cs-w2-001"
    assert d["active_host"] == "player-alpha-1"
    assert d["chat_room_id"] == "chat-cs-w2-001"
    assert d["composite_playback_url"] == "http://localhost:8888/costream/cs-w2-001/index.m3u8"
    assert d["participant_count"] == 4
    expected_sig = sign_day2("cs-w2-001", {
        "active_host": "player-alpha-1",
        "handoff_occurred": False,
        "layout": "grid_4",
        "participant_count": 4,
        "session_id": "cs-w2-001",
        "status": "active",
    })
    assert d["signature"] == expected_sig


def test_costream_host_drop_handoff():
    res = client.post("/audit/v1/costream/session", json={
        "session_id": "cs-w2-drop",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1"],
        "simulate_host_drop": True,
        "layout": "grid_4",
    })
    assert res.status_code == 201
    d = res.json()
    assert d["handoff_occurred"] is True
    assert d["active_host"] == "player-alpha-2"
    assert d["participant_count"] == 2


def test_costream_idempotent_replay_200():
    payload = {
        "session_id": "cs-w2-idem",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2"],
        "layout": "grid_2",
    }
    r1 = client.post("/audit/v1/costream/session", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/audit/v1/costream/session", json=payload)
    assert r2.status_code == 200
    assert r1.json()["signature"] == r2.json()["signature"]


def test_costream_over_capacity_409():
    db_state.players["player-extra"] = {"player_id": "player-extra", "club_id": "club-alpha-1"}
    res = client.post("/audit/v1/costream/session", json={
        "session_id": "cs-over",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1", "player-beta-2", "player-extra"],
    })
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "COSTREAM_SESSION_FULL"


def test_costream_host_not_in_participants_400():
    res = client.post("/audit/v1/costream/session", json={
        "session_id": "cs-bad",
        "host_player_id": "player-beta-1",
        "participants": ["player-alpha-1", "player-alpha-2"],
    })
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_costream_unknown_player_404():
    res = client.post("/audit/v1/costream/session", json={
        "session_id": "cs-unk",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "no-such-player"],
    })
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_costream_solo_layout_4_participants_400():
    res = client.post("/audit/v1/costream/session", json={
        "session_id": "cs-solo-fail",
        "host_player_id": "player-alpha-1",
        "participants": ["player-alpha-1", "player-alpha-2", "player-beta-1", "player-beta-2"],
        "layout": "solo",
    })
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "UNSUPPORTED_LAYOUT"


# ---------------------------------------------------------------------------
# Dynamic QR
# ---------------------------------------------------------------------------

def test_qr_match_in_progress():
    res = client.get("/audit/v1/qr/match-m1")
    assert res.status_code == 200
    d = res.json()
    assert d["entity_status"] == "in_progress"
    assert d["target_route"] == "/web/matches/match-m1/live"
    expected_sig = sign_day2("match-m1", {
        "entity_id": "match-m1",
        "short_url": "http://localhost:8080/q/m1-live",
        "target_route": "/web/matches/match-m1/live",
    })
    assert d["signature"] == expected_sig


def test_qr_match_status_completed_changes_route():
    db_state.matches["match-m1"]["status"] = "completed"
    res = client.get("/audit/v1/qr/match-m1")
    assert res.status_code == 200
    d = res.json()
    assert d["target_route"] == "/web/matches/match-m1/vod"
    assert d["entity_status"] == "completed"
    expected_sig = sign_day2("match-m1", {
        "entity_id": "match-m1",
        "short_url": "http://localhost:8080/q/m1-live",
        "target_route": "/web/matches/match-m1/vod",
    })
    assert d["signature"] == expected_sig


def test_qr_inspect_does_not_increment_scan_count():
    before = db_state.qr_mappings["match-m1"]["scan_count"]
    client.get("/audit/v1/qr/match-m1?inspect=true")
    assert db_state.qr_mappings["match-m1"]["scan_count"] == before


def test_qr_normal_get_increments_scan_count():
    before = db_state.qr_mappings["match-m1"]["scan_count"]
    client.get("/audit/v1/qr/match-m1")
    assert db_state.qr_mappings["match-m1"]["scan_count"] == before + 1


def test_qr_short_code_redirect_302():
    res = client.get("/q/m1-live")
    assert res.status_code == 302
    assert res.headers["location"] == "/web/matches/match-m1/live"


def test_qr_export_svg():
    res = client.get("/audit/v1/qr/match-m1/export.svg")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/svg+xml")
    assert res.content.startswith(b"<svg")


def test_qr_export_png():
    res = client.get("/audit/v1/qr/match-m1/export.png")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/png")
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_qr_export_pdf():
    res = client.get("/audit/v1/qr/match-m1/export.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/pdf")
    assert res.content.startswith(b"%PDF-")
    assert b"match-m1" in res.content


def test_qr_unknown_entity_404():
    res = client.get("/audit/v1/qr/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "QR_NOT_FOUND"
