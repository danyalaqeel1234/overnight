import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.crypto import sign_day2
from app.domain.models import db_state
from app.domain.moderation_dlq import moderation_dlq_domain
from app.domain.observability import observability_domain

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_state(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", "T01D27ad7ffff12e")
    db_state.seed_baseline()
    moderation_dlq_domain.reset()
    observability_domain.reset()


def test_moderation_spec_exact_example():
    payload = {
        "chat_room_id": "chat-cs-session-101",
        "incoming_messages": [
            {
                "message_id": "msg-001",
                "sender": "user-spammer",
                "text": "Watch this illegal stream b@d_w0rd now!",
            }
        ],
        "check_dlq": False,
        "simulate_failed_notifications": 0,
    }
    res = client.post("/audit/v1/moderation/test", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["chat_room_id"] == "chat-cs-session-101"
    assert len(data["filtered_messages"]) == 1
    msg = data["filtered_messages"][0]
    assert msg["message_id"] == "msg-001"
    assert msg["sender"] == "user-spammer"
    assert msg["text"] == "Watch this illegal stream *** now!"
    assert msg["flagged"] is True
    assert msg["reason"] == "profanity_leetspeak"
    assert data["kicked_users"] == ["user-spammer"]
    assert data["muted_users"] == []
    assert data["dlq_status"]["queue_depth"] == 0

    expected_sig = sign_day2(
        "chat-cs-session-101",
        {
            "chat_room_id": "chat-cs-session-101",
            "flagged_count": 1,
            "kicked_users": ["user-spammer"],
            "queue_depth": 0,
        },
    )
    assert data["signature"] == expected_sig


def test_moderation_flood_drop_and_mute():
    payload = {
        "chat_room_id": "chat-cs-session-101",
        "incoming_messages": [
            {
                "message_id": "msg-flood-1",
                "sender": "user-flooder",
                "text": "GOAL! AAAA!!!",
            },
            {
                "message_id": "msg-clean-1",
                "sender": "user-normal",
                "text": "Great game!!",
            },
        ],
        "check_dlq": False,
    }
    res = client.post("/audit/v1/moderation/test", json=payload)
    assert res.status_code == 200
    data = res.json()
    # Flooded message must be DROPPED from filtered_messages
    assert len(data["filtered_messages"]) == 1
    assert data["filtered_messages"][0]["message_id"] == "msg-clean-1"
    assert data["muted_users"] == ["user-flooder"]


def test_moderation_dlq_simulation():
    payload = {
        "chat_room_id": "chat-room-dlq",
        "incoming_messages": [],
        "check_dlq": True,
        "simulate_failed_notifications": 3,
    }
    res = client.post("/audit/v1/moderation/test", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["dlq_status"]["queue_depth"] == 3
    assert len(data["dlq_status"]["undelivered_events"]) == 3
    assert data["dlq_status"]["undelivered_events"][0]["attempts"] == 3


def test_hidden_scenario_3_concurrent_moderation_race():
    payload = {
        "chat_room_id": "chat-cs-session-101",
        "incoming_messages": [
            {
                "message_id": "msg-race",
                "sender": "user-spammer",
                "text": "b@d_w0rd spam!",
            }
        ],
        "check_dlq": False,
        "simulate_failed_notifications": 1,
    }

    def send_req():
        return client.post("/audit/v1/moderation/test", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_req) for _ in range(10)]
        results = [f.result() for f in futures]

    for r in results:
        assert r.status_code == 200
        data = r.json()
        assert data["kicked_users"] == ["user-spammer"]

    # DLQ depth must equal 10
    assert len(moderation_dlq_domain.dlq) == 10


def test_metrics_prometheus_exposition():
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain; version=0.0.4" in res.headers["content-type"]
    body = res.text
    assert "nascon_active_ws_connections" in body
    assert "nascon_active_streams_total" in body
    assert "nascon_stream_bitrate_kbps" in body
    assert "nascon_dlq_depth" in body
    assert "nascon_qr_scans_total" in body
    assert body.endswith("\n")


def test_privacy_user_anonymize():
    res = client.delete("/audit/v1/privacy/user/player-alpha-1")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "player-alpha-1"
    assert data["status"] == "anonymized"
    assert data["pii_retained"] is False
    assert data["tokens_wiped"] is True
