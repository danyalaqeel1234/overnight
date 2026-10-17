# Team Mutators — Architecture Decision Records (ADR)
## NaSCon '26 Top-8 Finalist Viva Defense Artifact

---

### ADR-001: Mobile Architecture & Client Framework
* **Status:** Accepted
* **Context:** The competition requires Android-compatible mobile delivery with rapid screen development, offline caching, and responsive touch targets (>= 48 dp).
* **Decision:** Selected React Native with Expo SDK 57, Expo Router, and TypeScript (aligned for physical Pixel 7 compatibility).
* **Alternatives Rejected:**
  1. *Flutter:* Rejected due to longer Gradle build times on campus Wi-Fi and lack of shared TypeScript types with web contracts.
  2. *Native Kotlin/Android:* Rejected due to slower multi-screen scaffolding velocity within the strict 4-hour sprint window.
* **Downside / Trade-offs Accepted:** Accepted reliance on Expo managed workflow and cloud EAS build queues, mitigating by initiating preview builds early, running local Expo development builds, and caching SQLite locally.

---

### ADR-002: Backend Runtime & Framework
* **Status:** Accepted
* **Context:** Need high-throughput asynchronous execution, strict request validation matching Section 5 schema error codes, and auto-generated OpenAPI contracts.
* **Decision:** Selected Python 3.11+ with FastAPI, Pydantic v2 (Strict Mode), and Uvicorn.
* **Alternatives Rejected:**
  1. *Node.js / Express:* Rejected due to lack of native strict typing and boilerplate required for canonical JSON HMAC hashing.
  2. *Django REST Framework:* Rejected due to synchronous blocking overhead and heavy ORM abstractions unsuitable for sub-second bursts.
* **Downside / Trade-offs Accepted:** Accepted custom exception handling overrides for FastAPI's default 422 to return Section 5 compliant 400 `VALIDATION_ERROR` envelopes.

---

### ADR-003: Database Engine & Relational Modeling
* **Status:** Accepted
* **Context:** Multi-tenant relational integrity, foreign key cascades, tenant isolation, and atomic inventory mutations.
* **Decision:** PostgreSQL 16 Alpine for production Docker runtime; SQLite for lightning-fast in-process testing.
* **Alternatives Rejected:**
  1. *MongoDB / NoSQL:* Rejected because document models do not provide ACID guarantees or row-level pessimistic locking for concurrency-safe checkouts.
  2. *MySQL 8:* Rejected due to inferior JSON handling and slower container initialization on low-RAM runner environments.
* **Downside / Trade-offs Accepted:** Accepted dialect differences between SQLite (tests) and Postgres (prod), mitigated by avoiding database-specific types (using standard `String(36)` and generic `JSON`).

---

### ADR-004: Caching Layer & Circuit Breaking
* **Status:** Accepted
* **Context:** Standings recomputation and high-frequency read routes require low latency while guaranteeing zero outage if cache crashes.
* **Decision:** Redis 7 Alpine as read-through cache with graceful DB fallback on connection failure.
* **Alternatives Rejected:**
  1. *Memcached:* Rejected due to lack of structured key patterns and TTL clustering capabilities.
  2. *In-Process Python LRU Cache:* Rejected because multi-worker uvicorn processes would have desynchronized cache states.
* **Downside / Trade-offs Accepted:** Accepted memory consumption overhead in Docker, mitigated by configuring small maxmemory policies with LRU eviction.

---

### ADR-005: Event Broker & Asynchronous Queuing
* **Status:** Accepted
* **Context:** Domain events for order status changes, audit log emission, and offline sync replay ingestion.
* **Decision:** Lightweight internal event dispatcher backed by Redis Pub/Sub / NATS.
* **Alternatives Rejected:**
  1. *Apache Kafka:* Rejected due to massive JVM RAM footprint (exceeding laptop 8GB limit) and unnecessary cluster complexity.
  2. *RabbitMQ:* Rejected for Phase I due to Erlang runtime overhead and slower container boot times.
* **Downside / Trade-offs Accepted:** Accepted at-least-once in-memory delivery semantics, mitigated by strict idempotency keys (`order_id`, `event_id`).

---

### ADR-006: File Storage & Receipt Generation
* **Status:** Accepted
* **Context:** Server-side PDF generation containing order totals and base64 transmission for checkout receipts.
* **Decision:** `fpdf2` lightweight Python library for zero-overhead server-side PDF generation, storing rendered receipts in memory/filesystem.
* **Alternatives Rejected:**
  1. *WeasyPrint / Headless Chromium:* Rejected because rendering engines require 500MB+ dependencies and increase request latency beyond the 5s ceiling.
  2. *ReportLab:* Rejected due to licensing complexities and larger dependency footprint.
* **Downside / Trade-offs Accepted:** Accepted manual coordinate layout in `fpdf2`, mitigated by clean helper templates producing compliant `%PDF` headers.

---

### ADR-007: QA & Testing Strategy
* **Status:** Accepted
* **Context:** 85 points depend on autograder contract adherence, status codes, and multi-threaded concurrency bursts.
* **Decision:** Pytest with HTTPX in-process TestClient and threading.Barrier for 20-thread concurrency tests.
* **Alternatives Rejected:**
  1. *Network-only testing over Wi-Fi:* Rejected due to campus hotspot latency and packet drops causing false test failures.
  2. *Postman / Newman:* Rejected due to lack of programmatic concurrency primitives (barrier synchronization) and coverage instrumentation.
* **Downside / Trade-offs Accepted:** Accepted mock database session resets between tests, gaining 0.1s execution times across 20+ test vectors.

---

### ADR-008: Network Protocol & Multi-Tenant Boundary Security
* **Status:** Accepted
* **Context:** 5-tier RBAC, strict tenant isolation (`tenant-alpha` vs `tenant-beta`), and rolling rate limiting.
* **Decision:** REST over HTTP/1.1 with explicit JWT HS256 validation (enforcing `alg != none`), returning 403 on tenant boundary violation.
* **Alternatives Rejected:**
  1. *GraphQL:* Rejected because autograder asserts exact REST routes, methods, and status codes.
  2. *gRPC:* Rejected due to lack of standard autograder HTTP probe support.
* **Downside / Trade-offs Accepted:** Accepted rigid endpoint mapping across 7 probe routes, mitigated by structured policy table evaluation.
