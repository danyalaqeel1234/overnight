"""End-to-end in-process contract probe for every Day 2 /audit/v1/* endpoint.

Expected values come from the Day 2 spec examples; signatures use the public
reference salt from Appendix A (never the team salt).
"""
import json, hmac, hashlib, threading

from fastapi.testclient import TestClient

from app.main import app

SALT = b"T01D27ad7ffff12e"


def sig(e, p):
    m = (e + "|" + json.dumps(p, sort_keys=True, separators=(",", ":"), ensure_ascii=False)).encode()
    return hmac.new(SALT, m, hashlib.sha256).hexdigest()


class _SameThreadClient:
    """Drives the ASGI app on the test thread (httpx ASGITransport) so coverage traces handlers."""

    def __init__(self):
        import asyncio, httpx
        self._loop = asyncio.new_event_loop()
        self._lock = threading.Lock()
        self._client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8080")

    def _run(self, method, url, **kw):
        kw.pop("follow_redirects", None)
        with self._lock:
            return self._loop.run_until_complete(self._client.request(method, url, follow_redirects=False, **kw))

    def get(self, url, **kw):
        return self._run("GET", url, **kw)

    def post(self, url, **kw):
        return self._run("POST", url, **kw)

    def delete(self, url, **kw):
        return self._run("DELETE", url, **kw)


def test_day2_contract_asgi_same_thread(monkeypatch):
    monkeypatch.setenv("DAY2_SALT", "T01D27ad7ffff12e")
    c = _SameThreadClient()
    R = []

    def chk(name, cond, info=""):
        R.append((bool(cond), name, info))

    def j(r):
        try:
            return r.json()
        except Exception:
            return {"_raw": r.text[:200]}

    def code(r):
        return j(r).get("error", {}).get("code") if isinstance(j(r), dict) else None













    c.post("/audit/v1/reset", json={})
    r = c.get("/health"); chk("health 200 ok", r.status_code == 200 and j(r) == {"status": "ok"}, j(r))

    # ---- stream key
    r = c.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "player-alpha-1"}); b = j(r)
    chk("stream generate 201 + regex", r.status_code == 201 and str(b.get("stream_key", "")).startswith("sk_live_") and len(b.get("stream_key", "")) == 24, (r.status_code, b))
    r = c.post("/audit/v1/stream/key", json={"action": "rotate", "player_id": "player-alpha-1", "label": "OBS-Main-Desk", "stream_key_override": "sk_live_9f83a1b2c3d4e5f6"}); b = j(r)
    chk("stream rotate 200 override + exact sig/urls", r.status_code == 200 and b.get("stream_key") == "sk_live_9f83a1b2c3d4e5f6"
        and b.get("signature") == "9bd054eb746844b4701c6f158209c315ef2b16f392efd733bdf0715940610289"
        and (b.get("ingest_endpoints") or {}).get("webrtc") == "http://localhost:8889/live/sk_live_9f83a1b2c3d4e5f6/whip"
        and (b.get("ingest_endpoints") or {}).get("rtmp") == "rtmp://localhost:1935/live/sk_live_9f83a1b2c3d4e5f6"
        and b.get("playback_url") == "http://localhost:8888/live/sk_live_9f83a1b2c3d4e5f6/index.m3u8"
        and b.get("label") == "OBS-Main-Desk", (r.status_code, b))
    r = c.post("/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-alpha-1"}); b = j(r)
    chk("stream revoke 200 nulls + sig", r.status_code == 200 and b.get("status") == "revoked" and b.get("ingest_endpoints") is None and b.get("playback_url") is None
        and b.get("signature") == sig(b.get("stream_key", ""), {"action": "revoke", "player_id": "player-alpha-1", "status": "revoked", "stream_key": b.get("stream_key")}), (r.status_code, b))
    r = c.post("/audit/v1/stream/key", json={"action": "revoke", "player_id": "player-beta-1"}); chk("revoke none 404 STREAM_NOT_FOUND", r.status_code == 404 and code(r) == "STREAM_NOT_FOUND", j(r))
    r = c.post("/audit/v1/stream/key", json={"action": "blah", "player_id": "player-alpha-1"}); chk("bad action 400", r.status_code == 400 and code(r) == "VALIDATION_ERROR", j(r))
    r = c.post("/audit/v1/stream/key", json={"action": "generate", "player_id": "nobody"}); chk("unknown player 404", r.status_code == 404 and code(r) == "PLAYER_NOT_FOUND", j(r))

    # ---- costream
    P = ["player-alpha-1", "player-alpha-2", "player-beta-1", "player-beta-2"]
    req = {"session_id": "cs-session-101", "host_player_id": "player-alpha-1", "participants": P, "layout": "grid_4", "simulate_host_drop": True}
    r = c.post("/audit/v1/costream/session", json=req); b = j(r)
    exp = {"session_id": "cs-session-101", "status": "active", "active_host": "player-alpha-2", "handoff_occurred": True, "participant_count": 3,
           "active_participants": P[1:], "layout": "grid_4", "composite_playback_url": "http://localhost:8888/costream/cs-session-101/index.m3u8",
           "chat_room_id": "chat-cs-session-101", "signature": "5211c8c6f8a8e7694c68aa64469ee012eb90b2def8a4d9bf43399f18566aeee4"}
    chk("costream handoff exact 201", r.status_code == 201 and b == exp, (r.status_code, b))
    r = c.post("/audit/v1/costream/session", json=req); chk("costream replay 200", r.status_code == 200 and j(r) == exp, (r.status_code, j(r)))
    r = c.post("/audit/v1/costream/session", json={"session_id": "cs-x", "host_player_id": "player-alpha-1", "participants": ["player-alpha-1"], "simulate_host_drop": True}); b = j(r)
    chk("costream solo drop terminated", r.status_code == 201 and b.get("status") == "terminated" and b.get("active_host") is None and b.get("participant_count") == 0 and b.get("handoff_occurred") is False, (r.status_code, b))
    r = c.post("/audit/v1/costream/session", json={"session_id": "cs-y", "host_player_id": "player-alpha-1", "participants": P + ["player-zzz"]}); chk("5 participants incl unknown -> 404", r.status_code == 404, (r.status_code, j(r)))
    r = c.post("/audit/v1/costream/session", json={"session_id": "cs-y", "host_player_id": "player-alpha-1", "participants": P, "layout": "grid_2"}); chk("grid_2 x4 -> 400 UNSUPPORTED_LAYOUT", r.status_code == 400 and code(r) == "UNSUPPORTED_LAYOUT", j(r))
    r = c.post("/audit/v1/costream/session", json={"session_id": "cs-y", "host_player_id": "player-beta-1", "participants": ["player-alpha-1"]}); chk("host not in participants 400", r.status_code == 400 and code(r) == "VALIDATION_ERROR", j(r))

    # ---- QR
    r = c.get("/audit/v1/qr/match-m1"); b = j(r)
    chk("qr match-m1 exact", r.status_code == 200 and b.get("scan_count") == 1 and b.get("target_route") == "/web/matches/match-m1/live"
        and b.get("signature") == "9c5ce507faf71e175f9faa35b966909c78142735c39811fb0f55dbf4ece9437b" and b.get("entity_type") == "match"
        and b.get("deep_link_uri") == "nascon://entity/match-m1" and (b.get("export_formats") or {}).get("pdf") == "http://localhost:8080/audit/v1/qr/match-m1/export.pdf", b)
    r = c.get("/audit/v1/qr/match-m1?inspect=true"); chk("inspect does not increment", j(r).get("scan_count") == 1, j(r).get("scan_count"))
    for f, ct, mg in [("svg", "image/svg+xml", (b"<svg", b"<?xml")), ("png", "image/png", (b"\x89PNG\r\n\x1a\n",)), ("pdf", "application/pdf", (b"%PDF-",))]:
        r = c.get(f"/audit/v1/qr/match-m1/export.{f}")
        chk(f"export {f}", r.status_code == 200 and r.headers.get("content-type", "").startswith(ct) and r.content.startswith(mg), (r.status_code, r.headers.get("content-type")))
    r = c.get("/q/m1-live", follow_redirects=False); chk("/q/m1-live 302", r.status_code == 302 and r.headers.get("location", "").endswith("/web/matches/match-m1/live"), (r.status_code, r.headers.get("location")))
    r = c.get("/audit/v1/qr/nope-1"); chk("qr unknown 404 QR_NOT_FOUND", r.status_code == 404 and code(r) == "QR_NOT_FOUND", j(r))
    for e in ["player-alpha-1", "club-alpha-1"]:
        r = c.get(f"/audit/v1/qr/{e}?inspect=true"); chk(f"qr {e}", r.status_code == 200, j(r))
    r = c.post("/audit/v1/events", json={"event_id": "ev-end-m1", "match_id": "match-m1", "type": "match_end", "payload": {}})
    b = j(c.get("/audit/v1/qr/match-m1?inspect=true"))
    chk("QR mutation -> vod + fresh sig", b.get("target_route") == "/web/matches/match-m1/vod" and b.get("short_url") == "http://localhost:8080/q/m1-live"
        and b.get("signature") == sig("match-m1", {"entity_id": "match-m1", "short_url": "http://localhost:8080/q/m1-live", "target_route": "/web/matches/match-m1/vod"}), (r.status_code, j(r), b.get("target_route")))
    c.post("/audit/v1/reset", json={})
    for t in ["match_postponed", "status_change"]:
        r = c.post("/audit/v1/events", json={"event_id": "ev-pp-" + t, "match_id": "match-m1", "type": t, "payload": {"status": "postponed"}})
        if r.status_code < 300:
            break
    b = j(c.get("/audit/v1/qr/match-m1?inspect=true")); chk("QR postponed -> notice", b.get("target_route") == "/web/matches/match-m1/notice?state=postponed", (r.status_code, j(r), b.get("target_route")))
    c.post("/audit/v1/reset", json={})

    # ---- guest guard
    H = {"Authorization": "Bearer guest_anon_tok_7721"}
    for path in ["/api/v1/chat", "/audit/v1/checkout", "/audit/v1/events"]:
        r = c.post(path, headers=H, json={}); chk(f"guest 403 {path}", r.status_code == 403 and code(r) == "GUEST_WRITE_FORBIDDEN", (r.status_code, j(r)))
        r = c.post(path, headers=H, content=b"not json"); chk(f"guest 403 {path} (bad body)", r.status_code == 403, r.status_code)

    # ---- cart merge
    cm = {"guest_token": "guest_anon_tok_7721", "registered_user_id": "player-alpha-1", "guest_cart": [{"variant_id": "var-jersey-001-L", "quantity": 1}], "test_write_block": True}
    out = []
    th = [threading.Thread(target=lambda: out.append(c.post("/audit/v1/guest/cart-merge", json=cm))) for _ in range(5)]
    [t.start() for t in th]; [t.join() for t in th]
    b = out[0].json()
    chk("cart-merge exact + 5x concurrent replay", all(o.status_code == 200 and o.json().get("active_cart", {}).get("total_items") == 1 for o in out)
        and b.get("signature") == "152d6fcfffb561ffcd3ec2a3a2c5e5a818efffedeeef6bf610b2c7e46177ad15" and b.get("write_rejection_code") == 403
        and b.get("active_cart") == {"user_id": "player-alpha-1", "currency": "PKR", "total_items": 1, "subtotal_minor": 450000, "items": [{"variant_id": "var-jersey-001-L", "quantity": 1, "unit_price_minor": 450000}]},
        [(o.status_code, o.json().get("active_cart", {}).get("total_items")) for o in out])
    r = c.post("/audit/v1/guest/cart-merge", json={**cm, "registered_user_id": "player-alpha-2"}); chk("merged token diff user 409", r.status_code == 409 and code(r) == "GUEST_TOKEN_ALREADY_MERGED", j(r))
    r = c.post("/audit/v1/guest/cart-merge", json={**cm, "guest_token": "guest_x1", "guest_cart": [{"variant_id": "var-nope", "quantity": 1}]}); chk("variant 404", r.status_code == 404 and code(r) == "VARIANT_NOT_FOUND", j(r))
    r = c.post("/audit/v1/guest/cart-merge", json={**cm, "guest_token": "guest_x2", "guest_cart": [{"variant_id": "var-jersey-001-M", "quantity": 9999}]})
    chk("out of stock 409 + details.variant_id", r.status_code == 409 and code(r) == "OUT_OF_STOCK" and j(r)["error"].get("details", {}).get("variant_id") == "var-jersey-001-M", j(r))
    r = c.post("/audit/v1/guest/cart-merge", json={**cm, "guest_token": "abc"}); chk("bad token prefix 400", r.status_code == 400, j(r))

    # ---- moderation
    mreq = {"chat_room_id": "chat-cs-session-101", "incoming_messages": [
        {"message_id": "msg-1", "sender": "user-guest-1", "text": "Clean sports commentary"},
        {"message_id": "msg-2", "sender": "user-spammer", "text": "Watch this illegal stream b@d_w0rd now!"},
        {"message_id": "msg-3", "sender": "user-flooder", "text": "GOAL! AAAA!!!"}], "check_dlq": True, "simulate_failed_notifications": 0}
    r = c.post("/audit/v1/moderation/test", json=mreq); b = j(r)
    expm = {"chat_room_id": "chat-cs-session-101", "filtered_messages": [
        {"message_id": "msg-1", "sender": "user-guest-1", "text": "Clean sports commentary", "flagged": False, "reason": None},
        {"message_id": "msg-2", "sender": "user-spammer", "text": "Watch this illegal stream *** now!", "flagged": True, "reason": "profanity_leetspeak"}],
        "kicked_users": ["user-spammer"], "muted_users": ["user-flooder"], "dlq_status": {"queue_depth": 0, "undelivered_events": []}}
    s1 = "265f5fb2db106eec3ee58c1c4b205caebc2163fca78c534a9fcfc2dcf88d1db8"
    s2 = sig("chat-cs-session-101", {"chat_room_id": "chat-cs-session-101", "flagged_count": 2, "kicked_users": ["user-spammer"], "queue_depth": 0})
    chk("moderation spec example exact", r.status_code == 200 and {k: v for k, v in b.items() if k != "signature"} == expm and b.get("signature") in (s1, s2),
        (r.status_code, b, "flagged_count=" + ("1" if b.get("signature") == s1 else "2" if b.get("signature") == s2 else "?")))
    outs = []
    th = [threading.Thread(target=lambda: outs.append(c.post("/audit/v1/moderation/test", json={"chat_room_id": "chat-race", "incoming_messages": [{"message_id": "m", "sender": "user-spammer", "text": "b@d_w0rd"}], "check_dlq": True, "simulate_failed_notifications": 1}))) for _ in range(10)]
    [t.start() for t in th]; [t.join() for t in th]
    chk("moderation 10-thread race", all(o.status_code == 200 and o.json().get("kicked_users") == ["user-spammer"] for o in outs), [o.status_code for o in outs])
    r = c.post("/audit/v1/moderation/test", json={"chat_room_id": "chat-race", "incoming_messages": [], "check_dlq": True}); chk("DLQ depth exact 10", j(r).get("dlq_status", {}).get("queue_depth") == 10, j(r))
    for txt, should in [("sc@m", True), ("p.0.r.n", True), ("f*u*c*k", True), ("a$$h0le", True), ("classic assess", False)]:
        r = c.post("/audit/v1/moderation/test", json={"chat_room_id": "chat-t", "incoming_messages": [{"message_id": "x", "sender": "u9", "text": txt}]})
        fm = j(r).get("filtered_messages") or []
        chk(f"leet '{txt}' flagged={should}", bool(fm) and fm[0].get("flagged") == should, (r.status_code, fm))
    r = c.post("/audit/v1/moderation/test", json={"chat_room_id": "chat-k6", "incoming_messages": [{"message_id": "k6-1-1", "sender": "user-1", "text": "Live reaction"}], "check_dlq": False})
    chk("k6 moderation payload 200", r.status_code in (200, 201), (r.status_code, j(r)))

    # ---- metrics / privacy
    r = c.get("/metrics"); t = r.text
    chk("metrics ctype + 5 names", r.headers.get("content-type") == "text/plain; version=0.0.4" and all(n in t for n in ["nascon_active_ws_connections", "nascon_active_streams_total", "nascon_stream_bitrate_kbps", "nascon_dlq_depth", "nascon_qr_scans_total"]), r.headers.get("content-type"))
    r = c.delete("/audit/v1/privacy/user/player-alpha-1"); chk("privacy delete", r.status_code == 200 and j(r) == {"user_id": "player-alpha-1", "status": "anonymized", "pii_retained": False, "tokens_wiped": True}, j(r))

    # ---- web
    c.post("/audit/v1/reset", json={})
    ids = ["guest-video-player", "live-score-banner", "pinned-merch-card", "add-to-guest-cart-btn", "guest-cart-count", "chat-message-list", "chat-input-field", "chat-send-btn", "progressive-auth-modal"]
    r = c.get("/web/matches/match-m1/live"); h = r.text
    miss = [i for i in ids if f'data-testid="{i}"' not in h]; chk("web live has 9 testids", r.status_code == 200 and not miss, (r.status_code, miss))
    chk("score '1 - 0' server-rendered", "1 - 0" in h, "")
    r = c.get("/web/costream/cs-session-101"); miss = [i for i in ids if f'data-testid="{i}"' not in r.text]; chk("web costream has 9 testids", r.status_code == 200 and not miss, (r.status_code, miss))
    for pth in ["/web/matches/match-m1/vod", "/web/matches/match-m1/preview", "/web/matches/match-m1/notice?state=postponed", "/web/players/player-alpha-1", "/web/clubs/club-alpha-1"]:
        r = c.get(pth); chk(f"web route {pth}", r.status_code == 200, r.status_code)

    failed = [(n, str(i)[:300]) for ok, n, i in R if not ok]
    assert not failed, failed
    assert len(R) >= 50
