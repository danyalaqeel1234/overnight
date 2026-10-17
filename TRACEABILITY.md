# NaSCon ’26 Traceability Matrix

This document maps every Functional Requirement (FR) and Non-Functional Requirement (NFR) from the specification to its corresponding implementation source file and automated tests.

---

## 1. Functional Requirements

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

## 2. Non-Functional Requirements

| ID | Requirement Description | Acceptance Bar & Target | Implementation / Verification |
| :--- | :--- | :--- | :--- |
| **NFR-3** | Concurrency Correctness | 20 simultaneous threads buying stock=1 $\to$ exactly 1 201, 19 409s, zero overselling | `app/domain/store.py`<br>`tests/test_store.py` |
| **NFR-4** | Offline Tolerance & Synchronization | Mobile caches locally; offline queued actions replay with conflict resolution | `app/domain/offline_sync.py`<br>`mobile/src/services/sync.ts`<br>`tests/test_offline_sync.py` |
| **NFR-5** | Security & Rate Limiting | 5-role RBAC, alg!=none check, rolling rate-limit on `/api/v1/*` (100 req/10s per IP) | `app/core/security.py`<br>`app/core/rate_limiter.py` |
| **NFR-7** | Reproducibility | One command `DAY1_SALT=... docker compose up -d --build` brings up full backend in $<120$s | `docker-compose.yml`<br>`Dockerfile` |
