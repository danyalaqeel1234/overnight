# Team Mutators — 1-Page Code Map for Rapid Live Mutation Defense

> **Purpose:** Zero-fumble navigation during the 5-minute live mutation defense and Top-8 Viva.

## Master System Code Map

### 1. Backend Service Layer (`app/`)
| File Path | Lead Owner | Responsibility / Mutation Target |
| :--- | :--- | :--- |
| `app/main.py` | L1 | FastAPI factory, exception handler registration, router includes |
| `app/core/errors.py` | L1 | Global 400 `VALIDATION_ERROR` override, envelope handler, 1MB limit |
| `app/core/crypto.py` | L1 | Canonical JSON serializer + HMAC-SHA256 signature generator |
| `app/domain/models.py` | L1 | In-memory `DBState`, baseline seed data, product/stock maps |
| `app/domain/fixtures.py`| L1 | Pure round-robin (circle method), Swiss (backtracking DFS), single/double elim |
| `app/domain/sports.py` | L1 | Config-driven scoring models (`event`, `innings`, `round`), event taxonomy |
| `app/api/health.py` | L1 | `GET /health` readiness probe (checks DB readiness & seeded state) |
| `app/api/reset.py` | L1 | `POST /audit/v1/reset` state wiper, cache clearer, baseline re-seeder |
| `app/api/sports.py` | L1 | `POST /audit/v1/sports` dynamic mystery sport registration |
| `app/api/fixtures.py` | L1 | `POST /audit/v1/fixtures` bracket & round scheduling generator |
| `app/api/offline_sync.py`| L3 | `POST /audit/v1/offline-sync` replay processor & conflict resolution |

### 2. Mobile Client Layer (`mobile/`)
| File Path | Lead Owner | Responsibility / Screen Purpose |
| :--- | :--- | :--- |
| `mobile/App.tsx` | L2 | Root navigation shell, tab bars, role switcher, sync status header |
| `mobile/src/screens/StandingsScreen.tsx` | L2 | Tournament tables, division selector, qualification indicators |
| `mobile/src/screens/MatchDetailScreen.tsx`| L2 | Live score display, event timeline, pinned merchandise card |
| `mobile/src/screens/StoreScreen.tsx` | L2 | Catalogue grid, product cards, category filters |
| `mobile/src/screens/ProductDetailModal.tsx` | L2 | Size/variant selector, cart addition, stock badge |
| `mobile/src/screens/ReceiptModal.tsx` | L2 | Order summary, payment status, base64 PDF receipt preview |
| `mobile/src/screens/RosterScreen.tsx` | L2 | Club roster management, player transfer/loan/release modals |
| `mobile/src/screens/SettingsScreen.tsx` | L2 | Backend server URL configuration, active role toggle, sync queue view |
| `mobile/src/services/secureStore.ts` | L3 | JWT auth token storage in Android Keystore (`expo-secure-store`) |
| `mobile/src/services/database.ts` | L3 | Persistent SQLite database manager (`expo-sqlite`) |
| `mobile/src/services/cache.ts` | L3 | Local SQLite cache for Fixtures, Standings, and Club Profiles |
| `mobile/src/services/offlineQueue.ts` | L3 | Persistent SQLite Offline Action Queue (Airplane Mode queueing) |
| `mobile/src/services/sync.ts` | L3 | One-tap sync replay to `/audit/v1/offline-sync` + plain-language errors |
| `mobile/src/services/deskCheck.ts` | L3 | Automated 5-step judge desk-check sequence orchestrator |
| `mobile/src/store/` | L2 | Zustand stores: `cartStore.ts`, `configStore.ts`, `rosterStore.ts` |

### 3. Test Suites (`tests/`)
| File Path | Lead Owner | Test Coverage / Probes Verified |
| :--- | :--- | :--- |
| `tests/test_standings.py` | L3 | 3-way H2H mini-league recursion, decimal NRR, Test Vector 2 lot drawing, clinched math |
| `tests/test_store_concurrency.py`| L3 | 20-thread checkout burst on 1 stock, gateway decline rollback, `WELCOME10` discount |
| `tests/test_roster_rules.py` | L3 | 8-step check order, deferred match transfer, query-time loan return |
| `tests/contract/test_crypto_hmac.py`| L3 | Test Vectors 1 & 2, canonical JSON sorting and UTF-8 encoding |
| `tests/contract/test_rbac_matrix.py` | L3 | 7 probe routes (`P1`-`P7`), 5 roles, tenant isolation (403), auth tampering (401) |
| `tests/contract/test_offline_sync.py`| L3 | Offline sync replay: `appended`, `rebased_append`, `skipped_duplicate`, `server_wins` |
| `tests/test_fixtures.py` | L1 | Round-robin circle method, Swiss pairings, single & double elimination |
| `tests/test_sports.py` | L1 | Event-sourced scoring, compensation rollbacks, innings/series limits |

---

## Rapid Mutation Hotspots (5-Minute Live Defense Guide)

### Mutation 1: Add a Search / Query Filter
1. **Backend Route:** Add query parameter in endpoint function in `app/api/*.py`.
2. **Domain Logic:** Add `.filter(...)` or list comprehension in `app/domain/*.py`.
3. **Mobile Screen:** Add `TextInput` search state filter in `mobile/src/screens/*.tsx`.
4. **Pytest Verification:** Add test assertion with query param in `tests/test_*.py`.

### Mutation 2: Change Status Transition or Validation Rule
1. **Validation Rule:** Update schema validator or router check in `app/domain/*.py`.
2. **Error Code:** Verify matching code from `Appendix B` in `SPEC_TRAPS.md`.
3. **Pytest Verification:** Run `pytest tests/test_<module>.py -k test_<rule>` (< 1s execution).

### Mutation 3: Change Component Card Layout on Mobile
1. **Target Screen:** `mobile/src/screens/*.tsx` (Standings, MatchDetail, or Store).
2. **Styles:** Update `StyleSheet.create({ ... })` keeping min 48dp touch target size.
3. **Preview:** Instant hot reload on physical Android device connected via USB/Hotspot.
