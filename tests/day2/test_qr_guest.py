import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.crypto import sign_day2
from app.domain.models import db_state
from app.domain.qr_guest import qr_guest_domain
from app.domain.scoring import add_event

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_state(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", "T01D27ad7ffff12e")
    monkeypatch.setenv("DAY1_SALT", "T09D1271f28b2611")
    db_state.seed_baseline()
    qr_guest_domain.reset()


def test_get_qr_and_scan_count_inspect():
    # Calling with inspect=true does not increment scan count
    res1 = client.get("/audit/v1/qr/match-m1?inspect=true")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["entity_id"] == "match-m1"
    assert data1["entity_type"] == "match"
    assert data1["entity_status"] == "in_progress"
    assert data1["short_url"] == "http://localhost:8080/q/m1-live"
    assert data1["target_route"] == "/web/matches/match-m1/live"
    assert data1["deep_link_uri"] == "nascon://entity/match-m1"
    assert data1["scan_count"] == 0

    # Normal GET increments scan count
    res2 = client.get("/audit/v1/qr/match-m1")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["scan_count"] == 1

    # Signature verification
    expected_sig = sign_day2(
        "match-m1",
        {
            "entity_id": "match-m1",
            "short_url": "http://localhost:8080/q/m1-live",
            "target_route": "/web/matches/match-m1/live",
        },
    )
    assert data2["signature"] == expected_sig


def test_qr_302_redirect_and_telemetry():
    res = client.get("/q/m1-live", follow_redirects=False, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"})
    assert res.status_code == 302
    assert res.headers["location"] == "/web/matches/match-m1/live"
    assert qr_guest_domain.telemetry["device_family"]["mobile"] >= 1


def test_hidden_scenario_2_qr_mutation_after_print():
    # Initial live route
    res1 = client.get("/audit/v1/qr/match-m1?inspect=true")
    data1 = res1.json()
    assert data1["target_route"] == "/web/matches/match-m1/live"
    sig1 = data1["signature"]

    # Match ends via event
    ev_payload = {
        "event_id": "ev-match-end-m1",
        "match_id": "match-m1",
        "type": "match_end",
        "payload": {},
    }
    status_code, _ = add_event(ev_payload)
    assert status_code == 201

    # Route should mutate to /vod, same short_url, fresh signature S2 != S1
    res2 = client.get("/audit/v1/qr/match-m1?inspect=true")
    data2 = res2.json()
    assert data2["short_url"] == data1["short_url"]
    assert data2["target_route"] == "/web/matches/match-m1/vod"
    assert data2["signature"] != sig1

    expected_sig2 = sign_day2(
        "match-m1",
        {
            "entity_id": "match-m1",
            "short_url": data2["short_url"],
            "target_route": "/web/matches/match-m1/vod",
        },
    )
    assert data2["signature"] == expected_sig2


def test_qr_exports():
    # SVG
    res_svg = client.get("/audit/v1/qr/match-m1/export.svg")
    assert res_svg.status_code == 200
    assert "image/svg+xml" in res_svg.headers["content-type"]
    assert res_svg.content.startswith(b"<?xml") or res_svg.content.startswith(b"<svg")

    # PNG
    res_png = client.get("/audit/v1/qr/match-m1/export.png")
    assert res_png.status_code == 200
    assert "image/png" in res_png.headers["content-type"]
    assert res_png.content.startswith(b"\x89PNG\r\n\x1a\n")

    # PDF
    res_pdf = client.get("/audit/v1/qr/match-m1/export.pdf")
    assert res_pdf.status_code == 200
    assert "application/pdf" in res_pdf.headers["content-type"]
    assert res_pdf.content.startswith(b"%PDF-")


def test_guest_cart_merge_happy_path():
    payload = {
        "guest_token": "guest_anon_tok_7721",
        "registered_user_id": "player-alpha-1",
        "guest_cart": [
            {"variant_id": "var-jersey-001-L", "quantity": 1}
        ],
        "test_write_block": True,
    }
    res = client.post("/audit/v1/guest/cart-merge", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["cart_merged"] is True
    assert data["write_block_verified"] is True
    assert data["write_rejection_code"] == 403
    assert data["active_cart"]["total_items"] == 1
    assert data["active_cart"]["subtotal_minor"] == 450000

    expected_sig = sign_day2(
        "guest_anon_tok_7721",
        {
            "cart_merged": True,
            "guest_token": "guest_anon_tok_7721",
            "registered_user_id": "player-alpha-1",
            "total_items": 1,
            "write_rejection_code": 403,
        },
    )
    assert data["signature"] == expected_sig


def test_hidden_scenario_4_cart_merge_replay_idempotent():
    payload = {
        "guest_token": "guest_anon_tok_7721",
        "registered_user_id": "player-alpha-1",
        "guest_cart": [
            {"variant_id": "var-jersey-001-L", "quantity": 1}
        ],
    }
    res1 = client.post("/audit/v1/guest/cart-merge", json=payload)
    assert res1.status_code == 200

    # Replay identical merge -> returns 200 and same total_items (1, NOT 2)
    res2 = client.post("/audit/v1/guest/cart-merge", json=payload)
    assert res2.status_code == 200
    assert res2.json()["active_cart"]["total_items"] == 1

    # Different user with already merged token -> 409
    payload_diff_user = dict(payload)
    payload_diff_user["registered_user_id"] = "player-alpha-2"
    res_err1 = client.post("/audit/v1/guest/cart-merge", json=payload_diff_user)
    assert res_err1.status_code == 409
    assert res_err1.json()["error"]["code"] == "GUEST_TOKEN_ALREADY_MERGED"


def test_direct_guest_write_block_probes():
    headers = {"Authorization": "Bearer guest_anon_tok_7721"}

    # 1. POST /api/v1/chat -> 403
    res_chat = client.post("/api/v1/chat", json={"message": "hello"}, headers=headers)
    assert res_chat.status_code == 403
    assert res_chat.json()["error"]["code"] == "GUEST_WRITE_FORBIDDEN"

    # 2. POST /audit/v1/checkout -> 403
    res_chk = client.post("/audit/v1/checkout", json={"items": []}, headers=headers)
    assert res_chk.status_code == 403
    assert res_chk.json()["error"]["code"] == "GUEST_WRITE_FORBIDDEN"

    # 3. POST /audit/v1/events -> 403
    res_ev = client.post("/audit/v1/events", json={"type": "score"}, headers=headers)
    assert res_ev.status_code == 403
    assert res_ev.json()["error"]["code"] == "GUEST_WRITE_FORBIDDEN"
