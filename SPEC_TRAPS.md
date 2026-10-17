# SPEC_TRAPS.md: things that silently fail grader vectors (read before coding any area)

> Source: the NaSCon '26 Part I spec. A vector passes only if EVERY assertion holds (status, error code, every field, signatures). These are the places where "almost right" scores zero.
> **Never put DAY1_SALT in any file.** It is read from the environment only.

## 0. Global (affects every area: build these first, once)
1. **FastAPI returns 422 by default. The spec wants 400.** Override the `RequestValidationError` handler to return 400 `VALIDATION_ERROR` with `details.fields` = list of bad field names. Malformed JSON must also give 400.
2. **Wrong types → 400.** Use Pydantic **strict** mode (`ConfigDict(strict=True)` or `StrictInt`/`StrictStr`/`StrictBool`), so `"5"` is not accepted as an int and `true` is not accepted as 1. **Unknown fields are ignored** (`extra="ignore"`), never rejected.
3. **Every non-2xx response uses the envelope** `{"error":{"code","message","details":{}}}`. This includes 404 for unknown routes, 405, and 500 (catch-all handler: never leak a stack trace). Never return FastAPI's `{"detail":...}`.
4. **Check order:** 400 (schema) → 404 (referenced id missing) → 409/402 (business rule). The first failure wins.
5. **Identifiers:** 1–64 chars matching `^[A-Za-z0-9_.:-]{1,64}$`, case-sensitive, stored and returned verbatim. A `|` is invalid → 400. `sport_id` is stricter: `^[a-z0-9_-]{2,40}$`.
6. **Timestamps** must be exactly `YYYY-MM-DDTHH:MM:SSZ`. Python's `isoformat()` gives `+00:00` and microseconds, which is wrong. Use `strftime("%Y-%m-%dT%H:%M:%SZ")`. Dates are `YYYY-MM-DD`.
7. **Money** is an integer in paisa. Currency is always `"PKR"`.
8. **Idempotency:** the same client id (`event_id`/`order_id`/`request_id`/`action_id`) with an identical body returns **200 with the stored response**, changing nothing. The same id with a different body → 409 `DUPLICATE_*`. Compare request bodies as canonical JSON.
9. **Body > 1 MB → 413 `PAYLOAD_TOO_LARGE`**, using middleware that runs before JSON parsing.
10. **Timing:** every request < 5 s, `/reset` < 10 s, the 20-checkout burst < 10 s.
11. **Startup:** `docker compose up -d --build` must finish within 10 minutes on Ubuntu with Python 3.11, and `/health` must return 200 within **120 s**. `/health` is 200 **only when the DB is reachable AND the baseline is seeded**, so seed automatically on startup. Use a Postgres healthcheck plus `depends_on: condition: service_healthy`, and retry the DB connection in the API. No manual steps, no pre-created volumes.
12. **Salt:** `DAY1_SALT` is read from the environment at startup, UTF-8, **not trimmed, not hex-decoded**. Compose passes `DAY1_SALT: ${DAY1_SALT}`. `.env.example` lists it with no value.
13. **Hard-coded sport logic costs −8.** Never branch on a sport or event name. Branching on `scoring_model` (event/innings/round) is fine. Keep seed sports in a **JSON data file**, not Python code, so a code scan doesn't flag "football" or "goal" in the domain logic.
14. **`/reset`** truncates everything (`TRUNCATE ... RESTART IDENTITY CASCADE`) **and clears in-memory state** (rate-limiter windows, caches, id counters, idempotency stores), then reseeds the exact ids from §5.5. Running it twice must give identical state. The response echoes the seed and stock. Store the seed: it's the default `lots_seed`.

## 1. Signatures (§5.3, Appendix A)
- `sign(salt, id, payload) = hmac_sha256(salt_utf8, (id + "|" + canonical(payload)).utf8).hexdigest()`
- `canonical = json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False)`
- **Sign the payload object exactly as received** (the raw dict from the request), not a Pydantic model dump. A model dump can drop or reorder fields or change types, and the signature won't match.
- Receipts are signed over `receipt.payload` **exactly as returned**.
- Write a unit test that **must** reproduce Test vector 1: salt `demo-salt`, id `evt-1` → `972a8b55…7ec501`.

## 2. Fixtures (`POST /audit/v1/fixtures`): pure computation, store nothing
- These are pure functions: the best module for unit tests and coverage.
- **Round-robin**
  - Circle method. Odd n: add a phantom team; whoever meets it gets the bye.
  - Within each leg, every team has |home − away| ≤ 1: alternate the fixed team's home/away, then rotate.
  - Leg 2 = leg 1 mirrored (home/away swapped), with **global** round numbers (leg 2 continues the count).
  - `match_id` = `RR-L{leg}-R{round}-M{index}`. Byes are listed per round (`[]` when n is even).
- **Withdrawals**
  - `forfeit_remaining`: rounds > `after_round` → `status:"forfeit"`, `awarded_to` = the opponent.
  - `void_all`: every fixture of that team → `"voided"`, `awarded_to:null`. A fixture where **both** teams are withdrawn is voided.
  - `after_round` = 0 means the team never plays. An unknown team, or `after_round` outside `0..round_count` → 400.
  - Fixtures are never removed. Summary counts must add up.
- **Swiss**
  - Round 1 is **exact**: m = ⌊n/2⌋, seed i vs seed i+m, home = the lower seed number. Odd n: the last seed gets the bye.
  - Rounds ≥ 2: minimize the **sum of |score diff|** over rematch-free pairings. **Greedy fails.** Use a memoized DFS: always pair the lowest unpaired team, memoize on the bitmask of remaining teams (n ≤ 64), and prune with branch-and-bound.
  - Bye goes to the lowest-scoring team that hasn't had one, ties → largest index. If the rest can't be paired, try the next candidate. If nothing works → 409 `NO_VALID_PAIRING` with `details.round`.
  - Scoring: W = 1, D = 0.5, bye = 1. Buchholz = sum of **current** scores of opponents actually played (a bye adds 0).
  - Standings show history only, sorted by score desc, Buchholz desc, then seed asc.
  - `history` must contain exactly rounds 1..round−1 → else 400. `total_rounds` is 1..n−1, default ⌈log₂n⌉.
- **Single elimination** (exact)
  - B = next power of 2. Seed order is recursive: order(2k) = for each s in order(k): s, 2k+1−s.
  - R1 match i gets entries 2i−1 and 2i; the lower seed number is home. A seed > n is missing → `bye:true, away:null`, and the bye winner is propagated immediately.
  - The winner of R{r}M{i} goes to R{r+1}M{ceil(i/2)}: `home` slot if i is odd, `away` if even.
  - `results` with an unknown match or a non-participant winner → 400. Optional `TP` third-place match from the semifinal losers.
- **Double elimination**
  - WR1 is identical to single elimination.
  - Counts: LR has 2(k−1) rounds; rounds 2j−1 and 2j have B/2^{j+1} matches each; total LR matches = B−2.
  - Routing: WR1 losers meet in LR1; losers of WR r (r ≥ 2) drop into LR(2r−2).
  - Every non-terminal match has `winner_to`; every WR match has `loser_to`; LR matches have `loser_to:null`. Every slot except WR1 is fed by exactly one source.
  - `GF2.conditional:true`. `required` is null until GF1 has a result, then true only if `bracket_reset` is set and GF1 was won by **GF1.away** (the losers-bracket champion).
  - **Do this last.** It's the most work for the fewest vectors.

## 3. Scoring engine (`/events`, `/score`)
- A match exists if it's a league fixture or had an accepted `match_init`. `match_init` on an existing match → 409 `MATCH_EXISTS`; any other event for a missing match → 404 `MATCH_NOT_FOUND`.
- **State machine:** `match_start` only from upcoming. `score`/`discipline`/`tiebreak_winner`/`match_end` only while in_progress → else 409 (`MATCH_NOT_IN_PROGRESS` or `ILLEGAL_TRANSITION`, per the table).
- `score`: `team_id` must be home or away → 400. `event_type` not in the sport config → 400 `UNKNOWN_EVENT_TYPE`.
- `match_end` with a level score + `draw_allowed:false` + no active `tiebreak_winner` → 409 `TIE_NOT_ALLOWED`.
- **Compensation**
  - Allowed in **any** status, including completed.
  - Can only target score/discipline/tiebreak_winner events of the **same** match. Unknown target → 404 `EVENT_NOT_FOUND`. Already compensated, wrong type, or another match → 409 `INVALID_COMPENSATION`.
  - Both the compensated event and the compensation itself are neutral in the projection.
- **Limits** (compensated events don't count)
  - Innings: legal balls ≥ innings×overs×bpo, or wickets ≥ innings×wickets → 409 `INNINGS_COMPLETE` for that team.
  - Round model: once a team has ≥ (best_of+1)/2 rounds → 409 `SERIES_ALREADY_DECIDED`.
- `sequence` = 1-based position in that match's log (every type counts). `match_version` = log length after the append.
- **Score projection is rebuilt from the log on every read.** No mutable counters.
  - `overs` = `"{balls//bpo}.{balls%bpo}"`.
  - wickets/balls/overs are null for non-innings sports.
  - `fair_play` = sum of active discipline points.
  - Compensating a tiebreak on a level, completed match → `outcome:"undecided"`, which doesn't count as played in standings.
  - The events list includes compensated events with `compensated:true` / `compensated_by`.

## 4. Standings (`GET /standings/{league_id}`)
- Recompute from the logs on every call. "Played" = completed AND outcome ≠ undecided. A win by `tiebreak_winner` counts as a win.
- **resolve(group)**
  - For each criterion in order, compute it for every team in the group.
  - If the values are not all equal: split into sub-groups by value (best first) and call `resolve` on each sub-group of size > 1, **from the first criterion**. Then stop.
  - If they are all equal: move to the next criterion.
  - `draw_lots` always separates teams (distinct SHA values), so the recursion terminates. Only recurse on strictly smaller groups.
- `h2h_points`/`h2h_diff` use **only matches among the teams of the current group**. `overall_diff`/`scored`/`fair_play` use all completed matches.
- **Innings `diff` = NRR**
  - NRR = runs scored ÷ overs faced − runs conceded ÷ overs bowled, rounded to **3 decimals**.
  - Overs = legal balls ÷ bpo as a **decimal**, not the "3.2" display string.
  - All-out (wickets ≥ wickets_per_innings) counts as the full `overs_per_innings`.
  - Guard against division by zero.
- `draw_lots`: ascending `sha256(f"{seed}|{league_id}|{team_id}")`. Unit-test Test vector 2.
- **Qualification** (exact, points only, clinched checked first)
  - max(T) = points(T) + W × remaining(T).
  - `clinched` if fewer than k **other** teams have max(X) ≥ points(T).
  - `eliminated` if at least k others have points(X) > max(T).
- `h2h` is present for **every** ordered pair (zeros if they never met). `resolved_by` = the criterion that placed the team above the next tied team, else null.

## 5. Roster (`/roster/setup`, `/roster/transfer`, `/roster/history`)
- **Exact check order** (first failure wins):
  1. 400 schema/dates (`loan_end_date > effective_date`; `to_squad_id` required unless release)
  2. 404 league/player/squad
  3. 409 `CROSS_TENANT_TRANSFER`
  4. `NOT_IN_SQUAD`
  5. `TRANSFER_WINDOW_CLOSED` (inclusive; release is always allowed)
  6. `PLAYER_ON_LOAN`
  7. `SQUAD_FULL` (dest + 1 ≤ max)
  8. `MIN_POSITION_VIOLATION` (the from squad must keep the required count for the player's position)
- **Effects**
  - Transfer: role becomes substitute.
  - Loan: the player counts toward the **borrower's** squad, `parent_squad_id` = the lender.
  - Release: no squad.
- **In-progress match** → still accepted, with `state:"deferred_until_match_end"` and `blocking_match_id`.
- **Loan auto-return:** a `history?as_of` date after `loan_end_date` appends a `loan_return` entry (`who:"system"`) **exactly once**, never duplicated on repeated calls. `current_squad_id` is computed as of `as_of`.
- Rejected requests write nothing. Replaying the same `request_id` → 200 with the same body.

## 6. Store (`/checkout`, `/inventory`)
- **Never hold a DB lock during the payment call.**
  - **Tx 1 (reserve):** for each item, in **sorted variant_id order** (prevents deadlocks):
    `UPDATE inventory SET stock = stock - :q, reserved = reserved + :q WHERE variant_id = :v AND stock >= :q RETURNING stock`.
    If any update returns no row → roll back the whole tx → 409 `OUT_OF_STOCK` with `details.variant_id`.
  - **Mock gateway.**
  - **Tx 2:**
    - Success → `reserved -= q`.
    - Decline / capture_fail → `stock += q, reserved -= q` → 402 `PAYMENT_DECLINED` / `PAYMENT_CAPTURE_FAILED`.
- After the burst: one 201, nineteen 409, `stock:0`, `reserved:0`. **DB pool size ≥ 20.** Run a single uvicorn worker.
- Discount: `floor(subtotal * 10 / 100)`. Only `WELCOME10`; any other code → 400 `INVALID_DISCOUNT_CODE`. The order of checks is 400 → 404 → discount 400.
- PDF: the text must contain the `order_id` and `PKR {total//100}.{total%100:02d}`, using the **total** (after discount) and no thousands separator. The base64 must decode to bytes starting with `%PDF`.

## 7. RBAC + security
- JWT HS256, decoded with `algorithms=["HS256"]` explicitly, so `alg:none` is rejected. Tampered or expired → 401 `UNAUTHENTICATED`. Tokens are valid for ≥ 1 h.
- **Implement the §5.13 matrix as a data table** (a policy matrix). This is also good viva material.
- Cross-tenant → **403, never 404**. 404 is only for ids that don't exist at all. Probes return `{"authorized":true}` and ignore the body.
- **Rate limit:** **only `/api/v1/*`**, 100 per rolling 10 s per client IP. `/api/v1/ping` → `{"pong":true}`. A 429 carries `RATE_LIMITED` **and a `Retry-After` header**. Don't count rejected requests in the window.
- **Never return a 5xx.** SQL-injection strings in `sport_id` → 400. Strings are always stored as plain data (parameterized queries only).

## 8. Offline sync (`/offline-sync`)
- Sort by `queued_at` ascending (ties keep array order), process one by one against the evolving state, and **return results in request order** with `processed_order`.
- **Statuses and resolutions**
  - `applied/appended`: the action applies and `base_version` == current version.
  - `applied/rebased_append`: `base_version` < current version.
  - `duplicate/skipped_duplicate`: `(device_id, action_id)` was seen before, or the same `event_id` already exists with an identical payload.
  - `rejected/server_wins` + the rule's code: any rule rejects it, including `INVALID_BASE_VERSION` when `base_version` > current, or the matching `*_NOT_FOUND`.
- Version for score_event = the match's event count. Version for roster_transfer = the player's audit-entry count.
- Re-sending the whole request → every action is `duplicate`. The response is always HTTP 200; only a malformed envelope → 400.

## 9. Coverage (10% of each backend area's points, NOT a bonus on top)
- The score per area is `0.9·P·passed/total + 0.1·P·[coverage ≥ 85%]`.
- Put each area in its **own package** (`fixtures`, `scoring`, `standings`, `store`, `roster`, `rbac`) so per-area coverage can be measured.
- `run_tests.sh` must run everywhere: unit tests for the pure logic run without Postgres.
- `COVERAGE.json` must be within 2 percentage points of the real figure, or that area's bonus is voided. Generate it from the real coverage run; never type it by hand.

## 10. Mobile deliverable
- **A real APK is required at `mobile/release/app-release.apk`** (Android 10+). Expo Go alone is NOT enough. Start an EAS cloud build (`eas build -p android --profile preview` with `buildType: "apk"`) **early, by 12:30**, to flush out problems. The cloud queue can be slow.
- The server address must be changeable inside the app (settings screen). Tokens go in secure storage (`expo-secure-store` uses the Keystore).
- The offline queue must persist (expo-sqlite), survive a force-close, use the exact §5.14 action format, and have an always-visible online/offline/syncing indicator. Explain rejected actions in plain language.
- The **5 demo accounts** (§8.3) must exist after every startup and every `/reset`.
- Judges' 3 tasks:
  - (A) find standings, open a match
  - (B) buy an item with the mock payment, view the receipt
  - (C) as Club Manager, do a roster action, then repeat one action in airplane mode and sync
- Polish those three flows first.
