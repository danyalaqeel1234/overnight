# NaSCon ’26 Traceability Matrix (Phase I & Phase II)

This document maps every Functional Requirement (FR) and Non-Functional Requirement (NFR) from the specification to its corresponding implementation source file and automated tests.

---

## 1. Functional Requirements (Phase I)

| ID | Requirement Description | Implementation Files | Automated Unit / Integration Tests |
| :--- | :--- | :--- | :--- |
| **FR-1.1** | Multi-Sport Taxonomy & Event-Sourced Scoring (Zero hardcoded sport logic, JSON schema, HMAC signatures, compensating events) | `app/domain/sports.py`<br>`app/domain/events.py`<br>`app/api/audit.py` | `tests/test_scoring.py`<br>`tests/test_sports.py` |
| **FR-1.2** | League & Tournament Setup (Multi-division, promotion/relegation, stages, seasons) | `app/domain/leagues.py`<br>`app/database/models.py` | `tests/test_leagues.py` |
| **FR-1.3** | Match & Fixture Scheduling (Custom Round-robin circle method, Swiss backtracking with Buchholz, Single & Double Elim w/ bracket reset) | `app/domain/fixtures.py`<br>`app/api/audit.py` | `tests/test_fixtures.py` |
| **FR-1.4** | Automated Standings & Tables (Points, 3-way H2H mini-league recursion, NRR, lot drawing, clinched/eliminated math) | `app/domain/standings.py`<br>`app/api/audit.py` | `tests/test_standings.py` |
| **FR-2.1** | Club Profiles & Strict Tenant Isolation | `app/domain/roster.py`<br>`app/core/security.py` | `tests/test_rbac.py` |
| **FR-2.2** | Roster & Player Registry (8-step check order, transfer windows, loan auto-returns, match deferral, immutable audit trail) | `app/domain/roster.py`<br>`app/api/audit.py` | `tests/test_roster.py` |
| **FR-2.3** | Integrated Club Merchandise Store (Pessimistic locking, zero overselling, mock gateway, signed PDF receipts) | `app/domain/store.py`<br>`app/core/pdf.py`<br>`app/api/audit.py` | `tests/test_store.py` |
| **FR-5.1** | 5-Tier Role-Based Access Control (Super Admin, Organizer, Club Mgr, Player, Viewer; 7 probe routes) | `app/core/security.py`<br>`app/api/audit.py` | `tests/test_rbac.py` |

---

## 2. Functional Requirements (Phase II)

| ID | Requirement Description | Implementation Files | Automated Unit / Integration Tests |
| :--- | :--- | :--- | :--- |
| **FR-3.1** | Public Athlete Identity & Concurrency-Safe Social Graph | `app/api/web.py`<br>`app/domain/models.py` | `tests/day2/test_guest_web_player.py` |
| **FR-3.2** | Low-Latency Solo Streaming & Dynamic Overlays (Rotating stream keys, 409 KEY_REVOKED, signed with DAY2_SALT) | `app/domain/streaming.py`<br>`app/api/stream_key.py` | `tests/day2/test_stream_key.py`<br>`tests/day2/test_crypto_vectors.py` |
| **FR-3.3** | Synchronized 4-Way Co-Streaming & Host Handoff (Array order promotion, monotonic sequence, layouts) | `app/domain/costream.py`<br>`app/api/costream.py` | `tests/day2/test_costream.py` |
| **FR-4.1** | Dynamic Cryptographic QR Deep-Linking & Exports (Live route computation, SVG/PNG/PDF, privacy telemetry) | `app/domain/qr_guest.py`<br>`app/api/qr.py` | `tests/day2/test_qr_endpoints.py` |
| **FR-4.2** | Zero-Account Guest Experience (Instant playback, no login wall, guest_anon_tok_*) | `app/web/templates/guest_player.html`<br>`app/api/web.py` | `tests/selenium/test_guest_grid.py`<br>`tests/selenium/test_guest_player.py` |
| **FR-4.3** | Server-Enforced Read-Only Boundary (Pure ASGI middleware, 403 GUEST_WRITE_FORBIDDEN on any write) | `app/core/guest_guard.py`<br>`app/main.py` | `tests/day2/test_guest_guard.py` |
| **FR-4.4** | Progressive Registration & Atomic Cart Merge (Pre-stock idempotency, quantity sum, replay safe) | `app/domain/qr_guest.py`<br>`app/api/guest.py` | `tests/day2/test_cart_merge.py` |
| **FR-5.2** | Notification Bus & DLQ (WebSocket/SSE fan-out, retry <= 3, inspectable DLQ depth) | `app/core/realtime.py`<br>`app/domain/moderation_dlq.py` | `tests/day2/test_moderation_dlq.py` |
| **FR-5.3** | Synchronous Automated Chat Moderation (Leetspeak normalizer, flood drop, muted/kicked separation) | `app/domain/moderation_dlq.py`<br>`app/api/moderation.py` | `tests/day2/test_moderation_dlq.py` |

---

## 3. Non-Functional Requirements (Phase I & Phase II)

| ID | Requirement Description | Acceptance Bar & Target | Implementation / Verification |
| :--- | :--- | :--- | :--- |
| **NFR-1** | Realtime Score Broadcast Latency | Score event via `/audit/v1/events` broadcasts over WS/SSE, p95 < 500 ms | `app/core/realtime.py`<br>`app/api/events.py`<br>`tests/day2/test_realtime.py` |
| **NFR-2** | Load Scalability & Zero-Failure Throughput | 500 guest viewers + 50 chat posters, 15s: 0.00% errors, p95 < 800 ms | `tests/k6_load.js`<br>`tests/reports/k6-summary.json` |
| **NFR-3** | Concurrency Correctness | 20 simultaneous threads buying stock=1 $\to$ exactly 1 201, 19 409s, zero overselling | `app/domain/store.py`<br>`tests/test_store_concurrency.py` |
| **NFR-4** | Offline Tolerance & Synchronization | Mobile caches locally; offline queued actions replay with conflict resolution | `app/domain/offline_sync.py`<br>`mobile/src/services/sync.ts` |
| **NFR-5** | Security & Rate Limiting | 5-role RBAC, alg!=none check, rolling rate-limit on `/api/v1/*` (100 req/10s per IP) | `app/core/security.py`<br>`app/core/rate_limiter.py` |
| **NFR-6** | Observability & Prometheus Metrics | `GET /metrics` text/plain; version=0.0.4 with active WS, streams, bitrate, DLQ, QR scans | `app/domain/observability.py`<br>`app/api/metrics.py` |
| **NFR-7** | Reproducibility & Stack Health | Single command `docker compose up -d --build` healthy within 120s | `docker-compose.yml`<br>`Dockerfile` |
| **NFR-8** | Accessibility Compliance | WCAG 2.1 AA (contrast >= 4.5:1, Tab/Enter nav, touch targets >= 48px, ARIA) | `app/web/templates/guest_player.html`<br>`tests/selenium/test_guest_player.py` |
| **NFR-9** | Privacy-Safe Telemetry & Right to be Forgotten | No IP/full UA/fingerprint in QR; `DELETE /audit/v1/privacy/user/{id}` wipes within 1s | `app/domain/qr_guest.py`<br>`app/api/privacy.py` |
