# SPRINT_HANDOVER.md: Master Sprint State & Team Roster

> This file is the single source of truth for the NaSCon '26 Part I Sprint across all sessions, chats, and teammates.

---

## 1. Core Competition Parameters
- **Active Secret Salt:** `DAY1_SALT=T09D1271f28b2611` (Read strictly from environment; never committed into code).
- **GitHub Repository:** `https://github.com/DANYALAQEEL/Mutators.git` (Branch: `main`).
- **Sprint Deadline:** Saturday, Oct 17, 15:00:00 PKT (Final push lock: 15:05:00 PKT).
- **Desk Check Slot:** 15:15 PKT (10-minute live demo on real Android device).

---

## 2. Mandatory Hourly Git Push Windows (-2 pts per missed window)
- [x] **Window 1 (10:45 – 11:45 PKT):** COMPLETED & PUSHED (Commit `f1f1ce4`).
- [x] **Window 2 (11:45 – 12:45 PKT):** COMPLETED & PUSHED (Commit `33f9a7c`) — FastAPI Core, Health, Reset, Crypto, Fixtures (RR/Swiss/Single/Double), Mystery Sports, 70/70 tests passing, Coverage 89.4%.
- [x] **Window 3 (12:45 – 13:45 PKT):** COMPLETED & PUSHED — Standings + H2H Mini-League, Store Concurrency (Pessimistic Locking + PDF receipts), 8-rule Roster Transfers & Loan Returns, Leagues & Event Sourcing (177/177 tests passing, all areas >= 88.5% coverage).
- [x] **Window 4 (13:45 – 14:45 PKT):** COMPLETED & PUSHED — 5-Tier RBAC & 7 Probes, Rolling Rate Limiter on /api/v1/* (100 req/10s), Offline Sync Router, Dockerfile & docker-compose.yml on Port 8080 (214/214 tests passing, all areas >= 88.5%).
- [x] **Final Lock (14:45 – 15:00 PKT):** Test suite pass (215/215), `COVERAGE.json` >= 85% across all 6 areas, clean working tree, final push before 15:05 (Commit `f2ec6b5`).

---

## 3. Team Member Division of Labor (Zero Overlap)

### Laptop 1: Danyal (Lead & Master Orchestrator with Antigravity / Claude Code / Codex)
- **Ownership:** `app/core/`, `app/domain/`, `app/api/audit.py`, git checkpoints.
- **Scope:**
  - Override FastAPI 422 to 400 `VALIDATION_ERROR` with `details.fields`.
  - Canonical JSON + HMAC-SHA256 signature generator (`sign(salt, id, payload)`).
  - Dynamic mystery sports engine (`POST /audit/v1/sports` - zero hardcoded sports).
  - Pure fixture generation (`POST /audit/v1/fixtures` - RR circle method, Swiss backtracking matching, Single/Double elim).
  - Standings engine (`GET /standings/{league_id}` - 3-way recursive H2H mini-league, decimal NRR, deterministic lot drawing).
  - Concurrency store (`POST /audit/v1/checkout` - row-level pessimistic locks, mock gateway rollback, signed `fpdf2` PDF receipts).
  - Roster system (`POST /roster/transfer` - 8-rule chain, in-progress match deferral, query-time loan returns).
  - 5-Tier RBAC & 7 probe routes (`POST /audit/v1/rbac-matrix`, `/audit/v1/rbac/*`).

### Laptop 2: Teammate 1 (Mobile Lead & UI/HCI Master)
- **Ownership:** `mobile/src/screens/**`, `mobile/src/components/**`, `mobile/release/app-release.apk`.
- **Scope (Targets 10 Points):**
  - Trigger EAS cloud APK build immediately (`eas build -p android --profile preview`).
  - Implement the 3 primary judge desk-check journeys:
    1. Standings $\to$ Tap Match $\to$ Live score detail with pinned product.
    2. Store $\to$ Select variant $\to$ Mock checkout (`tok_success`) $\to$ View PDF receipt.
    3. Roster management (Club Manager) $\to$ Transfer/loan/release forms.
  - HCI Standards: $\ge 48$dp touch targets, plain-language error banners, configurable server address in Settings.

### Laptop 3: Teammate 2 (Mobile Persistence, Offline Sync & QA Lead)
- **Ownership:** `mobile/src/services/**`, `app/api/offline_sync.py`, `tests/**`.
- **Scope (Targets 4 Points + 3.6 Coverage Bonus):**
  - Local SQLite cache for fixtures, standings, club profile (`expo-sqlite`).
  - Persistent SQLite Offline Action Queue (survives force-close & restart in Airplane Mode).
  - Reconnect & auto-sync replay to `POST /audit/v1/offline-sync`.
  - Contract & Concurrency Testing:
    * 20-thread checkout burst test on 1 stock item.
    * HMAC signature and lot drawing test vectors.
    * RBAC 7 probe routes matrix (403 for cross-tenant).
  - Ensure `./run_tests.sh` updates `COVERAGE.json` so all 6 areas are $\ge 85\%$.

---

## 4. Key References & Trap Guides
- **Specifications & Rules:** [SPEC_TRAPS.md](SPEC_TRAPS.md)
- **Requirement Mapping:** [TRACEABILITY.md](TRACEABILITY.md)
- **Demo Accounts:** [README.md](README.md)
