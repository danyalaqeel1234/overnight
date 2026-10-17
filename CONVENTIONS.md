# Team Mutators — Universal Conventions (NaSCon '26)

> **CRITICAL OVERRIDE RULE:** The official competition problem statement overrides every convention in this file. If the spec demands a specific route, casing, status code, or response shape, adhere strictly to the spec.

---

## 1. Stack & Runtime Versions
* **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Uvicorn (native execution).
* **Database:** PostgreSQL 16 Alpine (Docker in production mode; SQLite fallback for in-process Pytest).
* **Mobile Client:** React Native (Expo SDK 51+), TypeScript, Expo Router, TanStack Query v5, Zustand.
* **QA & Tests:** Pytest, pytest-asyncio, HTTPX `AsyncClient` / Starlette `TestClient`.

---

## 2. Repository Layout & Folder Ownership
Every human and AI agent MUST edit files ONLY inside their assigned folder:
* `/backend`  → **Laptop 1 (Danyal / Backend Lead)**
* `/mobile`   → **Laptop 2 (Mobile Specialist)**
* `/tests`    → **Laptop 3 (QA / Autograder Lead)**
* `/docs`     → **Laptop 3 (Documentation & Viva Lead)**
* `/.github`  → **Laptop 1 (CI/CD Lead)**
* `README.md` → **Shared (Laptop 1 owns; Laptop 3 contributes test/run sections)**
* `TASKS.md`  → **Shared queue (team members update their own task status)**

*Exception:* Laptop 1 Help-Desk lane (Claude Account 2) may edit `/mobile` or `/tests` to resolve escalated blockers, notifying the folder owner who pulls with rebase.

---

## 3. Naming Conventions & URL Patterns
* **Python:** `snake_case` for variables, functions, files, and database columns. `PascalCase` for classes/models.
* **TypeScript / React Native:** `camelCase` for variables and functions. `PascalCase` for components and types.
* **REST Endpoints:** Plural nouns (e.g. `/items`, `/users`). Prefix with `/api/v1/` unless the competition spec dictates explicit paths without prefixes.
* **Database Tables:** Plural lowercase (e.g. `users`, `items`, `audit_logs`).

---

## 4. API Response & Status Code Policy
* **200 OK / 201 Created:** Successful query or creation with JSON payload.
* **401 Unauthorized:** Missing, expired, or invalid JWT Bearer token.
* **404 Not Found (IDOR & Privacy Shield):** Always return `404 Not Found` when a user attempts to access a resource that does not exist OR is owned by another user. Do NOT return `403 Forbidden`, to prevent resource existence enumeration.
* **422 Unprocessable Entity:** Schema validation error automatically handled by Pydantic v2.
* **Unified Error Shape:**
  ```json
  {
    "detail": "Human-readable explanation of error",
    "code": "ERROR_CODE_CONSTANT"
  }
  ```

---

## 5. Security & Multi-Tenancy Architecture
* **Ownership Verification Pattern:**
  Every database query for a protected entity MUST scope to the authenticated user:
  ```python
  item = db.query(Item).filter_by(id=item_id, owner_id=current_user.id).first()
  if not item:
      raise HTTPException(status_code=404, detail="Item not found")
  ```
* **Environment Variables & Secrets:**
  * `.env` is STRICTLY gitignored from Commit #1.
  * Only `.env.example` (with empty or dummy placeholder values) is committed.
  * Backend loads env vars via Pydantic `BaseSettings`.
  * Mobile client has ZERO secrets; accesses config via `EXPO_PUBLIC_*`.
* **Rate Limiting:**
  * SlowAPI rate limiting must be gated behind `RATE_LIMIT_ENABLED` env flag (defaults to `false` during competition to avoid blocking the Cloud Autograder).

---

## 6. Git & Commit Guidelines
* **Trunk-Based:** Commit small units directly to `main` every 20–30 minutes.
* **Pre-Push Protocol:** Always stage your own folder and rebase before pushing:
  ```bash
  git add <your_folder>/
  git commit -m "<type>(<scope>): <short description>"
  git pull --rebase origin main
  git push origin main
  ```
* **Conventional Types:** `feat`, `fix`, `test`, `docs`, `chore`.
* **Freeze Windows:** ZERO commits or pushes between Saturday 2:55 PM and Sunday 10:15 AM.
