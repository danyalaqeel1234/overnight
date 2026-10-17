# NaSCon ’26 App Dev Sprint: Multi-Sport League & Club Operations Platform

Production-style, multi-tenant sports league and club operations platform featuring rule-driven league management, custom fixture scheduling, append-only event-sourced scoring, concurrency-safe merchandise store, and offline-tolerant mobile operations.

---

## 1. Quick Start & Execution

### Prerequisites
- Docker Engine 24+ & Docker Compose v2
- Python 3.11+
- Node.js 20+

### Start the Platform
To bring up the entire platform (API on host port `8080`, database, cache, workers):

```bash
# Provide team cryptographic salt at runtime
DAY1_SALT=T09D1271f28b2611 docker compose up -d --build
```

The readiness probe is accessible at:
```http
GET http://localhost:8080/health
```

### Running Test Suite & Coverage
```bash
chmod +x ./run_tests.sh
./run_tests.sh
```

---

## 2. Seed Demo Accounts (Section 8.3)

All five accounts are seeded automatically on startup and restored after every `POST /audit/v1/reset`:

| Role | Email | Password | Scope / Permissions |
| :--- | :--- | :--- | :--- |
| **Platform Super-Admin** | `admin@nascon.test` | `Nascon@26` | Platform-wide unconstrained administrative access |
| **League Organizer** | `organizer@nascon.test` | `Nascon@26` | Scoped to own league (`league-alpha-1`) |
| **Club Manager** | `manager@nascon.test` | `Nascon@26` | Scoped to own club (`club-alpha-1`) |
| **Player** | `player@nascon.test` | `Nascon@26` | Scoped to own player profile (`player-alpha-1`) |
| **General Viewer** | `viewer@nascon.test` | `Nascon@26` | Read-only access within tenant (`tenant-alpha`) |

---

## 3. Architecture & Traceability

- **API Specification Traps & Safeguards:** See [SPEC_TRAPS.md](SPEC_TRAPS.md)
- **Traceability Matrix:** See [TRACEABILITY.md](TRACEABILITY.md)
- **Unit Test Coverage:** Generated in [COVERAGE.json](COVERAGE.json)
- **Mobile Release Artifact:** Located at `mobile/release/app-release.apk`
