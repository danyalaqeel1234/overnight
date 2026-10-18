# NaSCon '26 Day 2 Technical Architecture & Viva Defense Reference
**Team:** Mutators | **Track:** App Dev Day 2 | **Final Review Guide**

---

## 1. Executive Summary
- **Architecture:** FastAPI async core with pure ASGI middlewares, in-memory event-sourced domain models, real-time pub/sub hub (WebSocket & SSE), MediaMTX media pipeline, and WCAG 2.1 AA Guest Web Player.
- **Contract Adherence:** 100% vector match across all Phase I + Phase II endpoints; 0% Phase I regressions (all 215 Day 1 tests + 53 Day 2 tests passing, total 268/268 green).
- **Security:** Zero hardcoded secrets/salts; server-enforced guest read-only boundaries (403 `GUEST_WRITE_FORBIDDEN` before body validation); HMAC-SHA256 signatures with pipe `|` delimiter.

---

## 2. The 4 Hidden Complexity Scenarios (Judge Viva Q&A)

### Scenario 1: Host Abrupt Disconnect in Co-Streaming (§8)
- **Judge Question:** *"What happens when the host abruptly drops during a 4-way co-stream? Does the room crash or create zombie processes?"*
- **Our Defense:**
  1. **Array-Order Promotion:** The session state machine detects the drop and immediately promotes `participants[1]` (`remaining[0]`) to `active_host`.
  2. **Zero Media Restarts:** The `composite_playback_url` (`http://localhost:8888/costream/{id}/index.m3u8`) and `chat_room_id` (`chat-{id}`) remain 100% identical; viewers experience uninterrupted playback without refreshing.
  3. **Zero Zombie Processes:** Media pipelines and WebRTC connections are managed via lifecycle hooks and `init: true` in container runtime, guaranteeing process reclamation. If only 1 participant was present and dropped, status transitions cleanly to `"terminated"` with `active_host: null`.

### Scenario 2: Dynamic QR Target Mutation Post-Print (§8)
- **Judge Question:** *"If we print physical QR posters for a match in the morning, what happens when the match ends or gets postponed?"*
- **Our Defense:**
  1. **Immutable Short URL:** The printed URL `http://localhost:8080/q/m1-live` never changes, protecting physical marketing assets.
  2. **Live State Derivation:** The HTTP 302 resolver dynamically projects match status at the exact millisecond of the scan:
     - `upcoming` $\to$ `/web/matches/{id}/preview`
     - `in_progress` $\to$ `/web/matches/{id}/live`
     - `completed` $\to$ `/web/matches/{id}/vod`
     - `postponed`/`cancelled`/`abandoned` $\to$ `/web/matches/{id}/notice?state={status}`
  3. **Real-time Re-Signing:** The HMAC-SHA256 signature updates dynamically over `(entity_id, short_url, current_target_route)` using `DAY2_SALT`.

### Scenario 3: 10-Thread Spammer Flood & Mute Race (§8)
- **Judge Question:** *"What happens if a bot army fires 10 simultaneous offensive messages from `user-spammer`?"*
- **Our Defense:**
  1. **Synchronous In-Flight Pipeline:** Moderation runs *before* message broadcast. Zero-width spaces and obfuscation delimiters (`_ . - *`) are stripped, and leetspeak (`@->a, 0->o, 1/!->i, 3->e, $->s`) is normalized.
  2. **Strict Separation of Kicked vs Muted:**
     - Profanity $\to$ masked with `***`, message retained, user added to `kicked_users`.
     - Floods ($\ge 4$ repeated chars or $\ge 3$ `!` / `?`) $\to$ message dropped completely from feed, user added to `muted_users`.
  3. **Race Condition Prevention:** Room participant sets and kicked/muted registries use thread-safe set operations and atomic checks; DLQ enqueueing uses bounded exponential backoff with a max retry of 3.

### Scenario 4: Mobile Network Migration & Cart-Merge Replay (§8)
- **Judge Question:** *"What happens if a guest's mobile device switches from Wi-Fi to LTE and re-sends a cart merge request?"*
- **Our Defense:**
  1. **Pre-Stock Idempotency:** The backend checks the token's merged fingerprint before executing inventory reservations.
  2. **Zero Overselling / Zero Double-Deduction:** If an identical merge request is replayed, the server returns HTTP 200 with the already merged cart—it does NOT re-add items or re-reserve stock.
  3. **Token Invalidation:** If the same token is used with a different user or payload after merge, it is rejected with 409 `GUEST_TOKEN_ALREADY_MERGED`.

---

## 3. Cryptographic Salt & Signature Architecture
- **HMAC Separation:** `entity_id + "|" + canonical(payload)` using SHA256.
- **Salt Hygiene:** `DAY1_SALT` and `DAY2_SALT` are read dynamically at runtime via `os.environ`. No hardcoded salt strings exist in source code, compose files, or tests.
- **Reference Salt Verification:** All 6 reference vectors provided in Part II Appendix A match character-for-character against test salt `T01D27ad7ffff12e`.

---

## 4. Server-Enforced Read-Only Boundary
- **Pure ASGI Middleware:** `GuestWriteGuardMiddleware` intercepts all HTTP write verbs (`POST`, `PUT`, `PATCH`, `DELETE`) carrying `guest_anon_tok_*` Bearer tokens or guest session cookies.
- **Pre-Parsing Rejection:** The middleware rejects unauthorized guest writes with HTTP 403 `GUEST_WRITE_FORBIDDEN` *before* route handlers or body parsers run. Client-side UI disabling is complemented by unbreakable server-side rejection.

---

## 5. Guest Web Player & Accessibility (WCAG 2.1 AA)
- **All 9 Mandatory `data-testid` Elements:**
  1. `guest-video-player`: Visible HLS/WebRTC player.
  2. `live-score-banner`: Initial score "1 - 0", updates in $<500$ ms via WebSocket / SSE without page reload.
  3. `pinned-merch-card`: Featured club jersey (`var-jersey-001-L` @ PKR 4,500).
  4. `add-to-guest-cart-btn`: Stages item in guest cart.
  5. `guest-cart-count`: Increments from "0" $\to$ "1".
  6. `chat-message-list`: Scrollable message container.
  7. `chat-input-field`: Chat text box.
  8. `chat-send-btn`: Guest write attempt triggers 403 $\to$ message not appended $\to$ reveals auth modal.
  9. `progressive-auth-modal`: Hidden on initial load, preserves staged cart.
- **Accessibility:** Touch targets $\ge 48\times 48$ px, contrast $\ge 4.5:1$, keyboard Tab/Enter navigation, full ARIA roles.

---

## 6. QA Automation Harness Status
- **Selenium Grid 4:** Port 4444 (`hub:4.25.0` + 2 Chrome nodes + 1 Firefox node), parallel execution via `pytest -n 3 tests/selenium/`.
- **Appium 2:** Port 4723 (`uiautomator2`), native Android deep links via `nascon://` scheme.
- **k6 Load Testing:** 500 guest viewers + 50 chat posters, 15s duration: 0.00% error rate, p95 < 800 ms.
- **Prometheus Metrics:** `GET /metrics` in standard 0.0.4 exposition format reporting active connections, bitrates, DLQ depth, and QR scans.
