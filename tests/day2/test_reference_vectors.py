import os
import pytest
from app.core.crypto import sign, canonical


@pytest.fixture(autouse=True)
def set_day2_salt(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", "T01D27ad7ffff12e")


def test_reference_vectors():
    salt = "T01D27ad7ffff12e"

    # Vector 1: stream/key (4-key payload)
    v1_payload = {
        "action": "rotate",
        "player_id": "player-alpha-1",
        "status": "active",
        "stream_key": "sk_live_9f83a1b2c3d4e5f6",
    }
    s1 = sign(salt, "sk_live_9f83a1b2c3d4e5f6", v1_payload)
    assert s1 == "9bd054eb746844b4701c6f158209c315ef2b16f392efd733bdf0715940610289"

    # Vector 2: legacy 2-key stream
    v2_payload = {"action": "rotate", "player_id": "player-alpha-1"}
    s2 = sign(salt, "sk_live_101", v2_payload)
    assert s2 == "830b24eb2c795c02c54c17516b0e96870f5b65d98d28c2f0a15619ec3e076188"

    # Vector 3: QR match-m1 live
    v3_payload = {
        "entity_id": "match-m1",
        "short_url": "http://localhost:8080/q/m1-live",
        "target_route": "/web/matches/match-m1/live",
    }
    s3 = sign(salt, "match-m1", v3_payload)
    assert s3 == "9c5ce507faf71e175f9faa35b966909c78142735c39811fb0f55dbf4ece9437b"

    # Vector 4: Costream handoff example
    v4_payload = {
        "active_host": "player-alpha-2",
        "handoff_occurred": True,
        "layout": "grid_4",
        "participant_count": 3,
        "session_id": "cs-session-101",
        "status": "active",
    }
    s4 = sign(salt, "cs-session-101", v4_payload)
    assert s4 == "5211c8c6f8a8e7694c68aa64469ee012eb90b2def8a4d9bf43399f18566aeee4"

    # Vector 5: Cart-merge example
    v5_payload = {
        "cart_merged": True,
        "guest_token": "guest_anon_tok_7721",
        "registered_user_id": "player-alpha-1",
        "total_items": 1,
        "write_rejection_code": 403,
    }
    s5 = sign(salt, "guest_anon_tok_7721", v5_payload)
    assert s5 == "152d6fcfffb561ffcd3ec2a3a2c5e5a818efffedeeef6bf610b2c7e46177ad15"

    # Vector 6: Moderation example
    v6_payload = {
        "chat_room_id": "chat-cs-session-101",
        "flagged_count": 1,
        "kicked_users": ["user-spammer"],
        "queue_depth": 0,
    }
    s6 = sign(salt, "chat-cs-session-101", v6_payload)
    assert s6 == "265f5fb2db106eec3ee58c1c4b205caebc2163fca78c534a9fcfc2dcf88d1db8"
