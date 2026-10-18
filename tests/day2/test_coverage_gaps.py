"""
Edge-case contract tests for the streaming and qr_guest module groups:
stream key validation, media auth hook, cart-merge schema validation,
guest cart staging, guest guard header/cookie forms, and the web player routes.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import generate_seed_tokens
from app.domain.models import db_state
from app.domain.qr_guest import qr_guest_domain
from app.domain.streaming import streaming_domain

client = TestClient(app)

TESTIDS = [
    "guest-video-player",
    "live-score-banner",
    "pinned-merch-card",
    "add-to-guest-cart-btn",
    "guest-cart-count",
    "chat-message-list",
    "chat-input-field",
    "chat-send-btn",
    "progressive-auth-modal",
]


@pytest.fixture(autouse=True)
def setup_state(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", "T01D27ad7ffff12e")
    db_state.seed_baseline()
    streaming_domain.reset()
    qr_guest_domain.reset()


def _fields(res):
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    return body["error"]["details"]["fields"]


# ---------------------------------------------------------------- stream/key


def test_stream_key_empty_body_400():
    res = client.post("/audit/v1/stream/key", content=b"")
    assert res.status_code == 400
    assert _fields(res) == []


def test_stream_key_invalid_json_400():
    res = client.post(
        "/audit/v1/stream/key", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert _fields(res) == []


def test_stream_key_json_array_400():
    res = client.post("/audit/v1/stream/key", json=["generate"])
    assert res.status_code == 400
    assert _fields(res) == []


def test_stream_key_missing_player_id_400():
    res = client.post("/audit/v1/stream/key", json={"action": "generate"})
    assert res.status_code == 400
    assert "player_id" in _fields(res)


def test_stream_key_label_too_long_400():
    res = client.post(
        "/audit/v1/stream/key",
        json={"action": "generate", "player_id": "player-alpha-1", "label": "x" * 65},
    )
    assert res.status_code == 400
    assert _fields(res) == ["label"]


def test_stream_key_null_label_defaults():
    res = client.post(
        "/audit/v1/stream/key",
        json={"action": "generate", "player_id": "player-alpha-1", "label": None},
    )
    assert res.status_code == 201
    assert res.json()["label"] == "default"


def test_stream_key_non_string_override_400():
    res = client.post(
        "/audit/v1/stream/key",
        json={"action": "generate", "player_id": "player-alpha-1", "stream_key_override": 101},
    )
    assert res.status_code == 400
    assert _fields(res) == ["stream_key_override"]


def test_active_keys_index_tracks_generate():
    client.post(
        "/audit/v1/stream/key",
        json={
            "action": "generate",
            "player_id": "player-alpha-1",
            "stream_key_override": "sk_live_idx",
        },
    )
    assert streaming_domain.player_active_keys.get("player-alpha-1") == "sk_live_idx"


# ---------------------------------------------------------- media auth hook


def _generate(key: str) -> None:
    res = client.post(
        "/audit/v1/stream/key",
        json={"action": "generate", "player_id": "player-alpha-1", "stream_key_override": key},
    )
    assert res.status_code == 201


def test_media_auth_active_key_allows_publish():
    _generate("sk_live_media_ok")
    res = client.post(
        "/internal/media/auth", json={"action": "publish", "path": "live/sk_live_media_ok"}
    )
    assert res.status_code == 200


def test_media_auth_revoked_key_409():
    _generate("sk_live_media_rev")
    res = client.post(
        "/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-alpha-1"}
    )
    assert res.status_code == 200
    res = client.post(
        "/internal/media/auth", json={"action": "publish", "path": "live/sk_live_media_rev"}
    )
    assert res.status_code == 409
    assert res.json()["error"] == "KEY_REVOKED"


def test_media_auth_unknown_key_404():
    res = client.post(
        "/internal/media/auth", json={"action": "publish", "path": "live/sk_live_unknown"}
    )
    assert res.status_code == 404
    assert res.json()["error"] == "STREAM_NOT_FOUND"


def test_media_auth_read_and_other_paths_allowed():
    res = client.post("/internal/media/auth", json={"action": "read", "path": "live/anything"})
    assert res.status_code == 200
    res = client.post("/internal/media/auth", json={"action": "publish", "path": "costream/cs-1"})
    assert res.status_code == 200
    res = client.post("/internal/media/auth", content=b"")
    assert res.status_code == 200


def test_publish_check_active_key_200():
    _generate("sk_live_pub_ok")
    res = client.post("/audit/v1/stream/publish", json={"stream_key": "sk_live_pub_ok"})
    assert res.status_code == 200
    assert res.json()["status"] == "allowed"


# ------------------------------------------------------- guest/cart-merge


def _merge(body):
    return client.post("/audit/v1/guest/cart-merge", json=body)


def _valid_merge(**overrides):
    body = {
        "guest_token": "guest_anon_tok_7721",
        "registered_user_id": "player-alpha-1",
        "guest_cart": [{"variant_id": "var-jersey-001-L", "quantity": 1}],
    }
    body.update(overrides)
    return body


def test_cart_merge_empty_body_400():
    res = client.post("/audit/v1/guest/cart-merge", content=b"")
    assert res.status_code == 400
    assert _fields(res) == []


def test_cart_merge_invalid_json_400():
    res = client.post(
        "/audit/v1/guest/cart-merge",
        content=b"{bad",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400
    assert _fields(res) == []


def test_cart_merge_json_array_400():
    res = client.post("/audit/v1/guest/cart-merge", json=[1, 2])
    assert res.status_code == 400
    assert _fields(res) == []


def test_cart_merge_bad_guest_token_400():
    res = _merge(_valid_merge(guest_token="abc"))
    assert res.status_code == 400
    assert _fields(res) == ["guest_token"]


def test_cart_merge_missing_user_400():
    body = _valid_merge()
    del body["registered_user_id"]
    res = _merge(body)
    assert res.status_code == 400
    assert _fields(res) == ["registered_user_id"]


def test_cart_merge_eleven_items_400():
    items = [{"variant_id": "var-jersey-001-L", "quantity": 1}] * 11
    res = _merge(_valid_merge(guest_cart=items))
    assert res.status_code == 400
    assert _fields(res) == ["guest_cart"]


def test_cart_merge_item_not_object_400():
    res = _merge(_valid_merge(guest_cart=["var-jersey-001-L"]))
    assert res.status_code == 400
    assert _fields(res) == ["guest_cart"]


def test_cart_merge_missing_variant_400():
    res = _merge(_valid_merge(guest_cart=[{"quantity": 1}]))
    assert res.status_code == 400
    assert _fields(res) == ["guest_cart"]


@pytest.mark.parametrize("qty", [0, "1", True, -2])
def test_cart_merge_bad_quantity_400(qty):
    res = _merge(_valid_merge(guest_cart=[{"variant_id": "var-jersey-001-L", "quantity": qty}]))
    assert res.status_code == 400
    assert _fields(res) == ["guest_cart"]


def test_cart_merge_non_bool_write_block_400():
    res = _merge(_valid_merge(test_write_block="true"))
    assert res.status_code == 400
    assert _fields(res) == ["test_write_block"]


# ------------------------------------------------- guest staging and guard


def test_guest_cart_staging_allowed_for_guest_bearer():
    res = client.post(
        "/api/v1/guest/cart",
        json={
            "guest_token": "guest_anon_tok_7721",
            "items": [{"variant_id": "var-jersey-001-L", "quantity": 1}],
        },
        headers={"Authorization": "Bearer guest_anon_tok_7721"},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "staged", "items_count": 1}
    assert qr_guest_domain.guest_carts["guest_anon_tok_7721"][0]["quantity"] == 1


def test_member_chat_post_201():
    token = generate_seed_tokens()["super_admin"]
    res = client.post(
        "/api/v1/chat",
        json={"chat_room_id": "chat-cs-session-101", "text": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201


def _assert_guest_forbidden(res, token):
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "GUEST_WRITE_FORBIDDEN"
    assert err["details"]["guest_token"] == token


def test_guard_raw_guest_authorization_header_403():
    res = client.post(
        "/api/v1/chat", json={"text": "hi"}, headers={"Authorization": "guest_raw_tok_1"}
    )
    _assert_guest_forbidden(res, "guest_raw_tok_1")


def test_guard_guest_token_cookie_403():
    res = client.post(
        "/audit/v1/checkout", json={}, headers={"Cookie": "guest_token=guest_cookie_tok_9"}
    )
    _assert_guest_forbidden(res, "guest_cookie_tok_9")


def test_guard_bare_guest_cookie_403():
    res = client.post("/audit/v1/events", json={}, headers={"Cookie": "guest_bare_tok_3"})
    _assert_guest_forbidden(res, "guest_bare_tok_3")


# ---------------------------------------------------------- web player routes


@pytest.mark.parametrize("path", ["/web/matches/match-m1/live", "/web/costream/cs-session-101"])
def test_player_pages_have_all_nine_testids(path):
    res = client.get(path)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    for testid in TESTIDS:
        assert f'data-testid="{testid}"' in res.text, testid


@pytest.mark.parametrize("suffix", ["preview", "vod"])
def test_match_preview_and_vod_render(suffix):
    res = client.get(f"/web/matches/match-m1/{suffix}")
    assert res.status_code == 200
    assert "match-m1" in res.text


def test_match_notice_shows_state():
    res = client.get("/web/matches/match-m1/notice?state=postponed")
    assert res.status_code == 200
    assert "Match status: postponed" in res.text
    assert 'role="alert"' in res.text


def test_player_and_club_pages_render():
    res = client.get("/web/players/player-alpha-1")
    assert res.status_code == 200
    assert "Athlete Profile: player-alpha-1" in res.text
    res = client.get("/web/clubs/club-alpha-1")
    assert res.status_code == 200
    assert "Club: club-alpha-1" in res.text
