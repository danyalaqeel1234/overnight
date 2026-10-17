# Top-8 Viva Defense — 10 Toughest Questions & High-Impact Answers

### Q1: Why did you choose FastAPI over Node.js/Express or Django?
FastAPI provides asynchronous concurrency and automatic Pydantic v2 validation out-of-the-box, ensuring zero-overhead input checking against the autograder's schema requirements. It also natively outputs OpenAPI schemas matching our test contracts without third-party boilerplate.

### Q2: How do you strictly prevent Insecure Direct Object Reference (IDOR) and tenant leakage?
Every single database query enforces tenant boundaries at the SQL level via `filter_by(id=entity_id, tenant_id=current_user.tenant_id)`. For cross-tenant requests by authenticated users, we enforce a strict `403 FORBIDDEN` response on probe routes, and `404 NOT FOUND` on entities that do not exist, completely blocking enumeration attacks.

### Q3: Why run Pytest in-process against SQLite instead of hitting the live Docker container?
In-process testing with Starlette/HTTPX and SQLite eliminates network round-trip overhead and Docker port contention, executing test suites in under two seconds. This allows us to re-run full test regressions continuously on every local change without Wi-Fi or container lag.

### Q4: How do you handle 20 concurrent threads attempting to buy the last merchandise unit?
We implement two-phase row-level pessimistic locking in PostgreSQL: `UPDATE inventory SET stock = stock - :q, reserved = reserved + :q WHERE variant_id = :v AND stock >= :q RETURNING stock`. Only the single thread securing the row proceeds to the mock gateway; the other 19 fail immediately with `409 OUT_OF_STOCK`, ensuring zero overselling and stock returning to 0.

### Q5: What happens if the mock payment gateway fails during checkout?
Our payment handler executes an atomic rollback: `stock += q, reserved -= q` upon receiving `tok_declined` or `tok_capture_fail`. It returns HTTP `402 PAYMENT_DECLINED` / `PAYMENT_CAPTURE_FAILED` and immediately releases the reserved inventory for other buyers.

### Q6: How does the mobile client guarantee offline action durability during an app crash or force-close?
Actions performed in Airplane Mode are immediately written to an `expo-sqlite` persistent database on disk with status `pending`. Because they are committed to disk before UI feedback, force-closing or killing the process leaves the SQLite rows completely intact, ready for one-tap replay on reconnect.

### Q7: Why do you return 400 instead of 422 for malformed payloads?
The competition specification strictly mandates that schema/type validation errors return HTTP 400 `VALIDATION_ERROR` with a `details.fields` array. We explicitly override FastAPI's default `RequestValidationError` handler to conform 100% to this requirement.

### Q8: How is HMAC signature integrity preserved across mobile and backend?
We enforce canonical JSON serialization—sorting dictionary keys recursively by Unicode code point, omitting all whitespace (`separators=(',', ':')`), and unescaping UTF-8 characters. The message `id + "|" + canonical_payload` is signed with HMAC-SHA256 using the unhexed, untrimmed `DAY1_SALT`.

### Q9: How are tie-breaks in the tournament standings resolved?
We implement a recursive `resolve(group)` algorithm: first checking head-to-head points and differentials among the tied group only, falling back to overall differential and runs/goals scored, and finally resolving any unbreakable tie using deterministic SHA-256 lot drawing based on the competition seed.

### Q10: How are secrets managed across the development and autograding environments?
No secret or production credential is ever committed to source control; `.env` is gitignored from commit zero. All configurations are injected through environment variables validated via Pydantic `BaseSettings`, with safe defaults falling back for in-process test runs.
