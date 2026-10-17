# Team Mutators — Live Sprint Task Queue (NaSCon '26)

> **Rules:**
> 1. Anyone may update the status of their own assigned tasks (`todo` -> `doing` -> `done` -> `blocked`).
> 2. Do not reassign or edit someone else's row without coordinating on WhatsApp.
> 3. When blocked, follow the escalation protocol in your brief immediately.

| Task ID | Owner | Task Description | Req ID | Status | Notes & Blockers |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TASK-001** | **L1** | Scaffold FastAPI app, DB session, `/health`, and stub routers | R1-R8 | `todo` | Blocked until theme announced at 10:45 AM |
| **TASK-002** | **L2** | Build Expo navigation layout & mock FeedScreen on Android | R1, R3 | `todo` | Runs against `EXPO_PUBLIC_USE_MOCK=true` |
| **TASK-003** | **L3** | Turn problem statement into `docs/AUTOGRADER_CHECKLIST.md` | All | `done` | Delivered to `docs/AUTOGRADER_CHECKLIST.md` |
| **TASK-004** | **L1** | Implement JWT auth + `current_user` dependency + user model | R1 | `todo` | Scope queries to `owner_id` |
| **TASK-005** | **L3** | Write Pytest vectors for auth (happy path, 401 unauth, 422 bad) | R1 | `done` | Verified in `tests/contract/test_rbac_matrix.py` |
| **TASK-006** | **L2** | Connect LoginScreen to live auth endpoint and store JWT token | R1 | `todo` | Switch from mock to live API |
| **TASK-007** | **L3** | Draft ADR-001 through ADR-008 with rejected alternatives | ADR | `done` | 8 formal ADRs completed in `docs/ADR.md` |
| **TASK-008** | **L1** | Implement core entity CRUD with IDOR protection (404 on breach) | R3, R4 | `todo` | Reviewed by Codex CLI (`git diff`) |
| **TASK-009** | **L3** | Build `mobile/src/services/` (SQLite + SecureStore) + Prove Desk-Check | NFR-4 | `done` | 5-step desk-check verified in `scripts/verify_desk_check.mjs` |
| **TASK-010** | **L3** | Contract probes (20-thread burst, HMAC vectors, RBAC matrix, coverage $\ge 85\%$) | NFR-3,5 | `done` | 17/17 tests passing, COVERAGE.json updated |
