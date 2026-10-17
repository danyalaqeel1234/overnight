# Team Mutators — 1-Page Code Map for Rapid Live Mutation Defense

> **Purpose:** Zero-fumble reference during the 5-minute live mutation test.

## Directory Responsibilities

| Path | Primary Owner | Tech Stack | Role / Purpose |
| :--- | :--- | :--- | :--- |
| `/backend/app/main.py` | L1 (Danyal) | FastAPI | App factory, CORS, exception handlers, router includes |
| `/backend/app/models/` | L1 | SQLAlchemy | Relational DB schemas & foreign keys |
| `/backend/app/schemas/` | L1 | Pydantic v2 | Input validation (strict mode) & output serializers |
| `/backend/app/api/audit.py` | L1 | FastAPI APIRouter | Route definitions, endpoints, status codes |
| `/backend/app/core/security.py` | L1 | Security / JWT | JWT token generation, 5-tier RBAC dependency |
| `/mobile/src/screens/` | L2 | React Native / Expo | UI views, forms, standings, live scores, store |
| `/mobile/src/services/` | L3 | expo-sqlite & SecureStore | Offline Action Queue, SQLite Cache, Keystore, Replay |
| `/tests/contract/` | L3 | Pytest / HTTPX | 20-thread checkout burst, HMAC vectors, RBAC probes |
| `/docs/` | L3 | Markdown / Mermaid | Architecture, ADRs, Traceability, Viva defense |

## Rapid Mutation Hotspots (5-Minute Defense)
1. **Adding Query Filter:**
   - Route: `app/api/audit.py` -> add parameter to endpoint function
   - Query: `app/domain/` -> add filter condition
   - Test: `tests/contract/` -> add vector with filter param
2. **Changing Status Transition Logic:**
   - Validation: `app/domain/` -> state machine table
   - Test: `tests/contract/` -> assert valid transition & 409 on invalid
3. **Adding Field to Response:**
   - Schema: `app/schemas/`
   - Test: `tests/contract/` -> assert key in `response.json()`
