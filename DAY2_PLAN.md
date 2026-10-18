# NaSCon '26 App Dev — Day 2 (Part II) Master Plan & Task Board
**Team:** Mutators | **Target:** 100% Vector & Probe Pass, 0% Phase I Regression, Win

---

## 1. Push Windows & Status Tracker (Oct 18 PKT)
- [x] **Window 1 (10:15 – 11:30 PKT):**
  - [x] Checkpoint 1.1 (11:13 PKT - Commit `3824707`): Skeleton layout, `.env` ignore, dockerignore, `DAY2_PLAN.md`, `docs/VIVA_DAY2.md`.
  - [x] Checkpoint 1.2 (11:28 PKT - Commit `1e0f8cf`): `DAY2_SALT` dynamic loading, Day 2 streaming keys (`/audit/v1/stream/key`), co-streaming sessions (`/audit/v1/costream/session`), server-side guest write-block guard (403 `GUEST_WRITE_FORBIDDEN`), mobile `nascon://` deep linking, 229/229 tests green.
- [x] **Window 2 (11:30 – 12:45 PKT):**
  - [x] Checkpoint 2.1 (12:33 PKT - Commit `d16a9ea`): Dynamic QR router, WebSocket and SSE realtime pub/sub hub, score broadcast integration.
  - [x] Checkpoint 2.2 (12:54 PKT - Commit `016f39e`): Guest Web Player with all 9 mandatory `data-testid` elements, WCAG 2.1 AA accessibility, progressive auth modal on 403, and Selenium Grid 4 test suite (`tests/selenium/`).
- [x] **Window 3 (12:45 – 13:45 PKT): Ahead of Schedule!**
  - [x] Checkpoint 3.1 (13:15 PKT): Appium 2 deep link test suite (`tests/appium/`), verified reports (`tests/reports/` JUnit XML & k6 summary), CI workflow with salt fallbacks (`.github/workflows/autograde.yml`), `COVERAGE_DAY2.json` (all 5 modules $\ge 85\%$), full `TRACEABILITY.md` expansion.
  - [x] Checkpoint 3.2: Complete Viva defense guide (`docs/VIVA_DAY2.md`) with 4 hidden complexity scenario defenses ready for team review by 13:20 PKT.
- [ ] **Window 4 Final Verification Window (13:45 – 14:00 PKT; grace lock 14:05:00):**
  - Standing by for team Viva rehearsal, zero risky code edits, clean lock at 13:55 PKT.

---

## 2. Division of Labor & Deliverables Completed
- **Backend & Core API (8080):** All 6 Day 2 endpoints implemented with exact HMAC-SHA256 signatures, character-for-character parity, zero hardcoded salts.
- **Guest Read-Only Boundary:** Pure ASGI middleware blocking state-mutating requests (`guest_anon_tok_*`) with 403 `GUEST_WRITE_FORBIDDEN`.
- **Realtime Pub/Sub Engine:** Sub-500ms score broadcast via WebSocket & SSE connected to `/audit/v1/events`.
- **Guest Web Player:** WCAG 2.1 AA dark theme player exposing all 9 `data-testid` attributes on `/web/matches/{id}/live` and `/web/costream/{id}`.
- **QA & Automation:** Selenium Grid 4 suite (`tests/selenium/test_guest_grid.py`), Appium 2 suite (`tests/appium/test_mobile_deeplink.py`), k6 load test script (`tests/k6_load.js`).
- **Reports & Artifacts:** `tests/reports/selenium-report.xml`, `tests/reports/appium-report.xml`, `tests/reports/k6-summary.json`, `COVERAGE_DAY2.json`.
- **Viva Defense:** `docs/VIVA_DAY2.md` covering all 4 hidden complexity scenarios.
