"""
Window 4 Test Suite: 5-Tier RBAC & 7 Probe Routes Matrix & Rate Limiting (Section 5.13 & SPEC_TRAPS.md Rule 7)

Verifies:
1. POST /audit/v1/rbac-matrix: returns JWT tokens for 5 seed roles + context IDs.
2. 7 Probe Routes (P1 through P7) authorization matrix across all 5 roles:
   - P1: POST /audit/v1/rbac/tenants (Super Admin only -> 200; all others -> 403)
   - P2: POST /audit/v1/rbac/leagues/{league_id}/fixtures (Super Admin & Organizer on own league -> 200; others -> 403)
   - P3: POST /audit/v1/rbac/clubs/{club_id}/roster (Super Admin & Club Manager on own club -> 200; others -> 403)
   - P4: POST /audit/v1/rbac/clubs/{club_id}/products (Super Admin & Club Manager on own club -> 200; others -> 403)
   - P5: PATCH /audit/v1/rbac/players/{player_id} (Super Admin, Manager of own club, Player self -> 200; others -> 403)
   - P6: GET /audit/v1/rbac/clubs/{club_id} (All tenant-alpha roles on tenant-alpha clubs -> 200; Foreign club strictly 403)
   - P7: GET /audit/v1/rbac/platform/config (Super Admin only -> 200; all others -> 403)
3. Strict 403 FORBIDDEN (never 404) for foreign tenant/club access.
4. Security probe validation:
   - Missing Authorization header -> 401 UNAUTHENTICATED
   - alg: none token -> 401 UNAUTHENTICATED
   - Tampered signature -> 401 UNAUTHENTICATED
   - Expired token -> 401 UNAUTHENTICATED
5. Rate Limiting on /api/v1/*:
   - 100 requests per rolling 10 seconds per IP
   - 101st request returns 429 RATE_LIMITED with Retry-After header
   - Independent IP tracking and rolling window reset
   - Scope limited to /api/v1/* (not /audit/v1/*)
"""

import hmac
import hashlib
import base64
import json
import time
from collections import defaultdict, deque
from typing import Dict, Any, Optional, Tuple, List
import pytest
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

SECRET_KEY = "nascon-26-rbac-secret-key"


def create_jwt(payload: Dict[str, Any], secret: str = SECRET_KEY, alg: str = "HS256") -> str:
    """Helper to generate JWT tokens matching HS256 specification."""
    header = {"typ": "JWT", "alg": alg}
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signing_input = f"{h_b64}.{p_b64}"

    if alg == "none":
        sig_b64 = ""
    else:
        sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")

    return f"{signing_input}.{sig_b64}"


def decode_and_verify_jwt(token: str, secret: str = SECRET_KEY) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
    """
    Decodes and strictly verifies JWT.
    Returns: (status_code, payload, error_code)
    """
    if not token:
        return 401, None, "UNAUTHENTICATED"

    parts = token.split(".")
    if len(parts) != 3:
        return 401, None, "UNAUTHENTICATED"

    h_b64, p_b64, sig_b64 = parts

    try:
        # Decode header
        h_pad = h_b64 + "=" * (-len(h_b64) % 4)
        header = json.loads(base64.urlsafe_b64decode(h_pad).decode())

        # Strict requirement: alg: none MUST be rejected with 401
        if header.get("alg") != "HS256":
            return 401, None, "UNAUTHENTICATED"

        # Verify signature
        signing_input = f"{h_b64}.{p_b64}"
        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")

        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return 401, None, "UNAUTHENTICATED"

        p_pad = p_b64 + "=" * (-len(p_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(p_pad).decode())

        # Check expiration if present
        if "exp" in payload and payload["exp"] < time.time():
            return 401, None, "UNAUTHENTICATED"

        return 200, payload, None
    except Exception:
        return 401, None, "UNAUTHENTICATED"


class RollingRateLimiter:
    """
    Rolling window rate limiter enforcing Section 5.13 & SPEC_TRAPS.md Rule 7:
    - 100 requests per rolling 10 seconds per IP.
    - Only applies to /api/v1/* routes.
    - 101st request returns 429 RATE_LIMITED with Retry-After header.
    - Rejected requests do NOT count into the window.
    """

    def __init__(self, limit: int = 100, window_seconds: float = 10.0):
        self.limit = limit
        self.window_seconds = window_seconds
        # ip -> deque of timestamps
        self.requests: Dict[str, deque] = defaultdict(deque)

    def is_allowed(self, ip: str, now: Optional[float] = None) -> Tuple[bool, int]:
        """
        Check if request from ip is allowed.
        Returns: (allowed, retry_after_seconds)
        """
        t = time.time() if now is None else now
        cutoff = t - self.window_seconds
        window = self.requests[ip]

        # Purge timestamps outside the rolling window
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) < self.limit:
            # Request admitted; record timestamp
            window.append(t)
            return True, 0
        else:
            # Rate limited; calculate Retry-After based on oldest timestamp in window
            oldest = window[0]
            retry_after = max(1, int(oldest + self.window_seconds - t + 0.999))
            # SPEC_TRAPS.md Rule 7: Don't count rejected requests in the window
            return False, retry_after

    def reset(self):
        self.requests.clear()


class RBACPolicyEngine:
    """
    Authoritative Section 5.13 RBAC Policy Engine.
    Evaluates 7 probe routes against tokens, context, and tenant boundaries.
    """

    def __init__(self):
        self.context = {
            "tenant_id": "tenant-alpha",
            "foreign_tenant_id": "tenant-beta",
            "own_league_id": "league-alpha-1",
            "other_league_id": "league-alpha-2",
            "foreign_league_id": "league-beta-1",
            "own_club_id": "club-alpha-1",
            "other_club_id": "club-alpha-2",
            "foreign_club_id": "club-beta-1",
            "own_player_id": "player-alpha-1",
            "other_player_id": "player-alpha-2",
            "foreign_player_id": "player-beta-1",
        }
        # Player to club mapping
        self.player_club_map = {
            "player-alpha-1": "club-alpha-1",
            "player-alpha-2": "club-alpha-2",
            "player-beta-1": "club-beta-1",
        }
        # League to tenant mapping
        self.league_tenant_map = {
            "league-alpha-1": "tenant-alpha",
            "league-alpha-2": "tenant-alpha",
            "league-beta-1": "tenant-beta",
        }
        # Club to tenant mapping
        self.club_tenant_map = {
            "club-alpha-1": "tenant-alpha",
            "club-alpha-2": "tenant-alpha",
            "club-beta-1": "tenant-beta",
        }

    def generate_seed_tokens(self) -> Dict[str, str]:
        now = time.time()
        return {
            "super_admin": create_jwt({"role": "super_admin", "sub": "admin-1", "exp": now + 7200}),
            "league_organizer": create_jwt({
                "role": "league_organizer",
                "tenant_id": "tenant-alpha",
                "league_id": "league-alpha-1",
                "sub": "org-1",
                "exp": now + 7200,
            }),
            "club_manager": create_jwt({
                "role": "club_manager",
                "tenant_id": "tenant-alpha",
                "club_id": "club-alpha-1",
                "sub": "mgr-1",
                "exp": now + 7200,
            }),
            "player": create_jwt({
                "role": "player",
                "tenant_id": "tenant-alpha",
                "player_id": "player-alpha-1",
                "club_id": "club-alpha-1",
                "sub": "ply-1",
                "exp": now + 7200,
            }),
            "viewer": create_jwt({
                "role": "viewer",
                "tenant_id": "tenant-alpha",
                "sub": "view-1",
                "exp": now + 7200,
            }),
        }

    def evaluate_probe(
        self,
        probe_id: str,
        target_id: str,
        token: Optional[str],
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Evaluates authorization probe.
        Returns: (status_code, body)
        """
        if not token or not token.startswith("Bearer "):
            return 401, {"error": {"code": "UNAUTHENTICATED", "message": "Missing or malformed Authorization header", "details": {}}}

        raw_token = token[7:].strip()
        status, payload, err_code = decode_and_verify_jwt(raw_token)
        if status != 200 or not payload:
            return 401, {"error": {"code": err_code or "UNAUTHENTICATED", "message": "Invalid token", "details": {}}}

        role = payload.get("role")
        user_tenant = payload.get("tenant_id")

        # Super Admin is platform-wide allowed for every probe
        if role == "super_admin":
            return 200, {"authorized": True}

        # P1: POST /audit/v1/rbac/tenants (Super Admin only)
        if probe_id == "P1":
            return 403, {"error": {"code": "FORBIDDEN", "message": "Super Admin access required", "details": {}}}

        # P2: POST /audit/v1/rbac/leagues/{league_id}/fixtures
        if probe_id == "P2":
            league_tenant = self.league_tenant_map.get(target_id)
            # Rule: Cross-tenant access is always 403 (strictly not 404)
            if league_tenant and league_tenant != user_tenant:
                return 403, {"error": {"code": "FORBIDDEN", "message": "Cross-tenant access prohibited", "details": {}}}
            if role == "league_organizer" and target_id == payload.get("league_id"):
                return 200, {"authorized": True}
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P3: POST /audit/v1/rbac/clubs/{club_id}/roster
        # P4: POST /audit/v1/rbac/clubs/{club_id}/products
        if probe_id in ("P3", "P4"):
            club_tenant = self.club_tenant_map.get(target_id)
            # Rule: Cross-tenant access is always 403 (strictly not 404)
            if club_tenant and club_tenant != user_tenant:
                return 403, {"error": {"code": "FORBIDDEN", "message": "Cross-tenant access prohibited", "details": {}}}
            if role == "club_manager" and target_id == payload.get("club_id"):
                return 200, {"authorized": True}
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P5: PATCH /audit/v1/rbac/players/{player_id}
        if probe_id == "P5":
            player_club = self.player_club_map.get(target_id)
            club_tenant = self.club_tenant_map.get(player_club) if player_club else None
            # Rule: Cross-tenant access is always 403 (strictly not 404)
            if club_tenant and club_tenant != user_tenant:
                return 403, {"error": {"code": "FORBIDDEN", "message": "Cross-tenant access prohibited", "details": {}}}

            if role == "club_manager":
                # Own club's players allowed
                if player_club == payload.get("club_id"):
                    return 200, {"authorized": True}
            elif role == "player":
                # Self only
                if target_id == payload.get("player_id"):
                    return 200, {"authorized": True}
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P6: GET /audit/v1/rbac/clubs/{club_id}
        if probe_id == "P6":
            club_tenant = self.club_tenant_map.get(target_id)
            # Rule: Foreign club is strictly 403 FORBIDDEN (never 404)
            if club_tenant != user_tenant:
                return 403, {"error": {"code": "FORBIDDEN", "message": "Foreign club access prohibited", "details": {}}}
            # All roles within tenant-alpha are allowed to view tenant-alpha clubs
            if user_tenant == "tenant-alpha" and club_tenant == "tenant-alpha":
                return 200, {"authorized": True}
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P7: GET /audit/v1/rbac/platform/config
        if probe_id == "P7":
            return 403, {"error": {"code": "FORBIDDEN", "message": "Super Admin access required", "details": {}}}

        return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}


# --- FASTAPI TEST HARNESS FOR HTTP INTEGRATION ---

def create_rbac_test_app() -> FastAPI:
    """Builds a FastAPI app with RBAC and Rate Limiting for full TestClient verification."""
    test_app = FastAPI(title="RBAC Test Harness")
    engine = RBACPolicyEngine()
    limiter = RollingRateLimiter(limit=100, window_seconds=10.0)

    @test_app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # Only rate limit /api/v1/* routes
        if request.url.path.startswith("/api/v1/"):
            client_ip = request.client.host if request.client else "127.0.0.1"
            # Support X-Forwarded-For if supplied in headers
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()

            allowed, retry_after = limiter.is_allowed(client_ip)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "RATE_LIMITED", "message": "Rate limit exceeded", "details": {}}},
                    headers={"Retry-After": str(retry_after)},
                )
        return await call_next(request)

    @test_app.post("/audit/v1/rbac-matrix")
    async def rbac_matrix():
        return {
            "tokens": engine.generate_seed_tokens(),
            "context": engine.context,
        }

    @test_app.get("/api/v1/ping")
    async def api_ping():
        return {"pong": True}

    @test_app.post("/audit/v1/rbac/tenants")
    async def probe_p1(request: Request):
        auth = request.headers.get("authorization")
        status, body = engine.evaluate_probe("P1", "", auth)
        return JSONResponse(status_code=status, content=body)

    @test_app.post("/audit/v1/rbac/leagues/{league_id}/fixtures")
    async def probe_p2(league_id: str, request: Request):
        auth = request.headers.get("authorization")
        status, body = engine.evaluate_probe("P2", league_id, auth)
        return JSONResponse(status_code=status, content=body)

    @test_app.post("/audit/v1/rbac/clubs/{club_id}/roster")
    async def probe_p3(club_id: str, request: Request):
        auth = request.headers.get("authorization")
        status, body = engine.evaluate_probe("P3", club_id, auth)
        return JSONResponse(status_code=status, content=body)

    @test_app.post("/audit/v1/rbac/clubs/{club_id}/products")
    async def probe_p4(club_id: str, request: Request):
        auth = request.headers.get("authorization")
        status, body = engine.evaluate_probe("P4", club_id, auth)
        return JSONResponse(status_code=status, content=body)

    @test_app.patch("/audit/v1/rbac/players/{player_id}")
    async def probe_p5(player_id: str, request: Request):
        auth = request.headers.get("authorization")
        status, body = engine.evaluate_probe("P5", player_id, auth)
        return JSONResponse(status_code=status, content=body)

    @test_app.get("/audit/v1/rbac/clubs/{club_id}")
    async def probe_p6(club_id: str, request: Request):
        auth = request.headers.get("authorization")
        status, body = engine.evaluate_probe("P6", club_id, auth)
        return JSONResponse(status_code=status, content=body)

    @test_app.get("/audit/v1/rbac/platform/config")
    async def probe_p7(request: Request):
        auth = request.headers.get("authorization")
        status, body = engine.evaluate_probe("P7", "", auth)
        return JSONResponse(status_code=status, content=body)

    return test_app


# ==============================================================================
# PYTEST TEST SUITES
# ==============================================================================

class TestRBACProbeMatrix:
    """Comprehensive test matrix covering Section 5.13 P1 through P7."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = RBACPolicyEngine()
        self.tokens = self.engine.generate_seed_tokens()
        self.ctx = self.engine.context

    def test_rbac_matrix_generation_schema(self):
        """Verify POST /audit/v1/rbac-matrix schema and token generation."""
        tokens = self.tokens
        assert "super_admin" in tokens
        assert "league_organizer" in tokens
        assert "club_manager" in tokens
        assert "player" in tokens
        assert "viewer" in tokens

        # Verify context keys
        for key in (
            "tenant_id", "foreign_tenant_id",
            "own_league_id", "other_league_id", "foreign_league_id",
            "own_club_id", "other_club_id", "foreign_club_id",
            "own_player_id", "other_player_id", "foreign_player_id"
        ):
            assert key in self.ctx

    def test_p1_tenants_super_admin_only(self):
        """
        P1: POST /audit/v1/rbac/tenants
        Expected: Super Admin -> 200; All others -> 403 FORBIDDEN.
        """
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P1", "", f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
                assert body == {"authorized": True}
            else:
                assert status == 403, f"P1 should be 403 for {role}, got {status}"
                assert body["error"]["code"] == "FORBIDDEN"

    def test_p2_fixtures_league_matrix(self):
        """
        P2: POST /audit/v1/rbac/leagues/{league_id}/fixtures
        - own league: Super Admin (200), League Organizer (200); others (403)
        - other league (same tenant): Super Admin (200); others (403)
        - foreign league: Super Admin (200); others (403)
        """
        # Own league (league-alpha-1)
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P2", self.ctx["own_league_id"], f"Bearer {token}")
            if role in ("super_admin", "league_organizer"):
                assert status == 200, f"P2 own league failed for {role}"
                assert body["authorized"] is True
            else:
                assert status == 403
                assert body["error"]["code"] == "FORBIDDEN"

        # Other league in same tenant (league-alpha-2)
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P2", self.ctx["other_league_id"], f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
            else:
                assert status == 403
                assert body["error"]["code"] == "FORBIDDEN"

        # Foreign league (league-beta-1)
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P2", self.ctx["foreign_league_id"], f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
            else:
                assert status == 403
                assert body["error"]["code"] == "FORBIDDEN"

    def test_p3_p4_club_roster_and_products_matrix(self):
        """
        P3: POST /audit/v1/rbac/clubs/{club_id}/roster
        P4: POST /audit/v1/rbac/clubs/{club_id}/products
        - own club: Super Admin (200), Club Manager (200); others (403)
        - other club / foreign club: Super Admin (200); others (403)
        """
        for probe in ("P3", "P4"):
            # Own club (club-alpha-1)
            for role, token in self.tokens.items():
                status, body = self.engine.evaluate_probe(probe, self.ctx["own_club_id"], f"Bearer {token}")
                if role in ("super_admin", "club_manager"):
                    assert status == 200, f"{probe} own club failed for {role}"
                    assert body["authorized"] is True
                else:
                    assert status == 403
                    assert body["error"]["code"] == "FORBIDDEN"

            # Other club (club-alpha-2)
            for role, token in self.tokens.items():
                status, body = self.engine.evaluate_probe(probe, self.ctx["other_club_id"], f"Bearer {token}")
                if role == "super_admin":
                    assert status == 200
                else:
                    assert status == 403
                    assert body["error"]["code"] == "FORBIDDEN"

            # Foreign club (club-beta-1)
            for role, token in self.tokens.items():
                status, body = self.engine.evaluate_probe(probe, self.ctx["foreign_club_id"], f"Bearer {token}")
                if role == "super_admin":
                    assert status == 200
                else:
                    assert status == 403
                    assert body["error"]["code"] == "FORBIDDEN"

    def test_p5_player_patch_matrix(self):
        """
        P5: PATCH /audit/v1/rbac/players/{player_id}
        - own player (player-alpha-1): Super Admin (200), Club Manager (200), Player self (200); Organizer/Viewer (403)
        - other player (player-alpha-2): Super Admin (200); Club Manager (403), Player (403), others (403)
        - foreign player (player-beta-1): Super Admin (200); all others (403)
        """
        # Own player (player-alpha-1 in club-alpha-1)
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P5", self.ctx["own_player_id"], f"Bearer {token}")
            if role in ("super_admin", "club_manager", "player"):
                assert status == 200, f"P5 own player failed for {role}"
                assert body["authorized"] is True
            else:
                assert status == 403
                assert body["error"]["code"] == "FORBIDDEN"

        # Other player (player-alpha-2 in club-alpha-2)
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P5", self.ctx["other_player_id"], f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
            else:
                assert status == 403
                assert body["error"]["code"] == "FORBIDDEN"

        # Foreign player (player-beta-1 in club-beta-1)
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P5", self.ctx["foreign_player_id"], f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
            else:
                assert status == 403
                assert body["error"]["code"] == "FORBIDDEN"

    def test_p6_clubs_get_read_matrix_and_tenant_boundary(self):
        """
        P6: GET /audit/v1/rbac/clubs/{club_id}
        - own club & other club in tenant-alpha: All 5 tenant-alpha roles allowed (200)!
        - foreign club in tenant-beta: Super Admin (200); all tenant-alpha roles strictly 403 FORBIDDEN!
        """
        # Own club in tenant-alpha
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P6", self.ctx["own_club_id"], f"Bearer {token}")
            assert status == 200, f"P6 own club should be 200 for {role}, got {status}"
            assert body["authorized"] is True

        # Other club in tenant-alpha
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P6", self.ctx["other_club_id"], f"Bearer {token}")
            assert status == 200, f"P6 other tenant-alpha club should be 200 for {role}, got {status}"
            assert body["authorized"] is True

        # Foreign club in tenant-beta: Strict 403 for non-super-admin
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P6", self.ctx["foreign_club_id"], f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
                assert body["authorized"] is True
            else:
                assert status == 403, f"Foreign club probe must return 403 for {role}, got {status}"
                assert body["error"]["code"] == "FORBIDDEN"

    def test_p7_platform_config_super_admin_only(self):
        """
        P7: GET /audit/v1/rbac/platform/config
        Expected: Super Admin -> 200; All other roles -> 403 FORBIDDEN.
        """
        for role, token in self.tokens.items():
            status, body = self.engine.evaluate_probe("P7", "", f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
                assert body["authorized"] is True
            else:
                assert status == 403
                assert body["error"]["code"] == "FORBIDDEN"


class TestForeignTenantForbiddenNot404:
    """
    SPEC_TRAPS.md Rule 7 & Section 5.13:
    'Cross-tenant access by a non-super-admin is always 403 (not 404).
    404 is reserved for ids that do not exist at all.'
    """

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = RBACPolicyEngine()
        self.tokens = self.engine.generate_seed_tokens()
        self.ctx = self.engine.context

    def test_foreign_club_is_strictly_403_not_404(self):
        """Assert GET /audit/v1/rbac/clubs/{foreign_club} returns 403, NEVER 404."""
        for role in ("league_organizer", "club_manager", "player", "viewer"):
            token = self.tokens[role]
            status, body = self.engine.evaluate_probe("P6", self.ctx["foreign_club_id"], f"Bearer {token}")
            assert status == 403, f"Expected 403 for foreign club under role {role}, got {status}"
            assert status != 404, f"TRAP: Foreign club returned 404 instead of 403 for role {role}!"
            assert body["error"]["code"] == "FORBIDDEN"

    def test_foreign_league_is_strictly_403_not_404(self):
        """Assert POST /audit/v1/rbac/leagues/{foreign_league}/fixtures returns 403, NEVER 404."""
        for role in ("league_organizer", "club_manager", "player", "viewer"):
            token = self.tokens[role]
            status, body = self.engine.evaluate_probe("P2", self.ctx["foreign_league_id"], f"Bearer {token}")
            assert status == 403
            assert status != 404
            assert body["error"]["code"] == "FORBIDDEN"

    def test_foreign_player_is_strictly_403_not_404(self):
        """Assert PATCH /audit/v1/rbac/players/{foreign_player} returns 403, NEVER 404."""
        for role in ("league_organizer", "club_manager", "player", "viewer"):
            token = self.tokens[role]
            status, body = self.engine.evaluate_probe("P5", self.ctx["foreign_player_id"], f"Bearer {token}")
            assert status == 403
            assert status != 404
            assert body["error"]["code"] == "FORBIDDEN"

    def test_foreign_club_products_is_strictly_403_not_404(self):
        """Assert POST /audit/v1/rbac/clubs/{foreign_club}/products returns 403, NEVER 404."""
        for role in ("league_organizer", "club_manager", "player", "viewer"):
            token = self.tokens[role]
            status, body = self.engine.evaluate_probe("P4", self.ctx["foreign_club_id"], f"Bearer {token}")
            assert status == 403
            assert status != 404
            assert body["error"]["code"] == "FORBIDDEN"


class TestSecurityProbesAndTokenValidation:
    """Security probes: missing tokens, alg:none, tampered signatures, expired tokens."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = RBACPolicyEngine()
        self.tokens = self.engine.generate_seed_tokens()

    def test_missing_authorization_header_returns_401(self):
        """Missing Authorization header -> 401 UNAUTHENTICATED."""
        status, body = self.engine.evaluate_probe("P7", "", None)
        assert status == 401
        assert body["error"]["code"] == "UNAUTHENTICATED"

        status_empty, body_empty = self.engine.evaluate_probe("P7", "", "")
        assert status_empty == 401
        assert body_empty["error"]["code"] == "UNAUTHENTICATED"

    def test_missing_bearer_prefix_returns_401(self):
        """Header without 'Bearer ' prefix -> 401 UNAUTHENTICATED."""
        token = self.tokens["super_admin"]
        status, body = self.engine.evaluate_probe("P7", "", token)
        assert status == 401
        assert body["error"]["code"] == "UNAUTHENTICATED"

    def test_alg_none_token_rejected_with_401(self):
        """SPEC REQUIREMENT: Token with alg: none MUST be rejected with 401."""
        alg_none_token = create_jwt({"role": "super_admin", "sub": "admin"}, alg="none")
        status, body = self.engine.evaluate_probe("P7", "", f"Bearer {alg_none_token}")
        assert status == 401
        assert body["error"]["code"] == "UNAUTHENTICATED"

    def test_tampered_signature_rejected_with_401(self):
        """Token with altered signature -> 401 UNAUTHENTICATED."""
        valid_token = self.tokens["super_admin"]
        parts = valid_token.split(".")
        # Corrupt the signature bytes
        tampered_sig = parts[2][:-4] + "AAAA"
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
        status, body = self.engine.evaluate_probe("P7", "", f"Bearer {tampered_token}")
        assert status == 401
        assert body["error"]["code"] == "UNAUTHENTICATED"

    def test_tampered_payload_rejected_with_401(self):
        """Token with payload altered after signing -> 401 UNAUTHENTICATED."""
        valid_token = self.tokens["viewer"]
        parts = valid_token.split(".")
        # Escalate role in payload
        forged_payload = {"role": "super_admin", "sub": "attacker"}
        forged_b64 = base64.urlsafe_b64encode(json.dumps(forged_payload).encode()).decode().rstrip("=")
        forged_token = f"{parts[0]}.{forged_b64}.{parts[2]}"
        status, body = self.engine.evaluate_probe("P7", "", f"Bearer {forged_token}")
        assert status == 401
        assert body["error"]["code"] == "UNAUTHENTICATED"

    def test_expired_token_rejected_with_401(self):
        """Token past expiration -> 401 UNAUTHENTICATED."""
        expired_token = create_jwt({"role": "super_admin", "exp": time.time() - 30})
        status, body = self.engine.evaluate_probe("P7", "", f"Bearer {expired_token}")
        assert status == 401
        assert body["error"]["code"] == "UNAUTHENTICATED"

    def test_malformed_token_string_rejected_with_401(self):
        """Malformed garbage string -> 401 UNAUTHENTICATED."""
        status, body = self.engine.evaluate_probe("P7", "", "Bearer not.a.valid.jwt.string")
        assert status == 401
        assert body["error"]["code"] == "UNAUTHENTICATED"


class TestRateLimiting:
    """
    Rate Limiting: 100 requests per rolling 10 seconds per IP on /api/v1/*.
    Assert 101st request returns 429 RATE_LIMITED with Retry-After header.
    """

    @pytest.fixture(autouse=True)
    def setup_limiter(self):
        self.limiter = RollingRateLimiter(limit=100, window_seconds=10.0)

    def test_100_requests_allowed_101st_rate_limited(self):
        """
        Send 100 requests within window: all allowed.
        101st request must be denied with Retry-After > 0.
        """
        ip = "192.168.1.100"
        base_time = 1000.0

        for i in range(100):
            allowed, retry_after = self.limiter.is_allowed(ip, now=base_time + (i * 0.05))
            assert allowed is True, f"Request {i+1} should be allowed"
            assert retry_after == 0

        # 101st request
        allowed_101, retry_after_101 = self.limiter.is_allowed(ip, now=base_time + 5.0)
        assert allowed_101 is False, "101st request must be rejected"
        assert retry_after_101 > 0, "Retry-After must be > 0"
        assert retry_after_101 <= 10, "Retry-After should not exceed window length"

    def test_rejected_requests_not_counted_in_window(self):
        """
        SPEC_TRAPS.md Rule 7: 'Don't count rejected requests in the window.'
        Sending multiple rejected requests does not push out the timestamp queue.
        """
        ip = "192.168.1.100"
        base_time = 1000.0

        # Fill window
        for i in range(100):
            self.limiter.is_allowed(ip, now=base_time)

        # Fire 20 rejected requests at base_time + 2.0
        for _ in range(20):
            allowed, _ = self.limiter.is_allowed(ip, now=base_time + 2.0)
            assert allowed is False

        # Queue length must strictly remain 100
        assert len(self.limiter.requests[ip]) == 100

        # At base_time + 10.01, the original 100 entries expire
        allowed_after_expiry, _ = self.limiter.is_allowed(ip, now=base_time + 10.01)
        assert allowed_after_expiry is True, "Request after rolling window expiry must succeed"

    def test_per_client_ip_isolation(self):
        """Client A reaching rate limit must not affect Client B."""
        ip_a = "10.0.0.1"
        ip_b = "10.0.0.2"
        now = 2000.0

        # Exhaust ip_a
        for _ in range(100):
            self.limiter.is_allowed(ip_a, now=now)

        assert self.limiter.is_allowed(ip_a, now=now)[0] is False

        # ip_b should still have full quota
        for _ in range(100):
            assert self.limiter.is_allowed(ip_b, now=now)[0] is True
        assert self.limiter.is_allowed(ip_b, now=now)[0] is False

    def test_rolling_window_continuous_sliding(self):
        """Test continuous sliding window behavior."""
        ip = "172.16.0.5"
        start = 5000.0

        # 50 requests at t=0
        for _ in range(50):
            assert self.limiter.is_allowed(ip, now=start)[0] is True

        # 50 requests at t=5
        for _ in range(50):
            assert self.limiter.is_allowed(ip, now=start + 5.0)[0] is True

        # At t=6, limit is reached (100 total in [start, start+10])
        assert self.limiter.is_allowed(ip, now=start + 6.0)[0] is False

        # At t=10.1, the first 50 have expired, leaving 50 in window -> allowed!
        assert self.limiter.is_allowed(ip, now=start + 10.1)[0] is True


class TestRBACFastAPILiveEndpoints:
    """End-to-end HTTP integration tests using FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def setup_app_client(self):
        self.app = create_rbac_test_app()
        self.client = TestClient(self.app)
        matrix_res = self.client.post("/audit/v1/rbac-matrix")
        assert matrix_res.status_code == 200
        data = matrix_res.json()
        self.tokens = data["tokens"]
        self.ctx = data["context"]

    def test_http_p1_tenants(self):
        """Test P1 over HTTP wire."""
        # Super admin allowed
        res = self.client.post(
            "/audit/v1/rbac/tenants",
            headers={"Authorization": f"Bearer {self.tokens['super_admin']}"},
            json={},
        )
        assert res.status_code == 200
        assert res.json() == {"authorized": True}

        # Viewer denied
        res_view = self.client.post(
            "/audit/v1/rbac/tenants",
            headers={"Authorization": f"Bearer {self.tokens['viewer']}"},
            json={},
        )
        assert res_view.status_code == 403
        assert res_view.json()["error"]["code"] == "FORBIDDEN"

    def test_http_p6_foreign_club_strict_403(self):
        """Test P6 foreign club over HTTP wire returns 403 strictly."""
        foreign_club = self.ctx["foreign_club_id"]
        res = self.client.get(
            f"/audit/v1/rbac/clubs/{foreign_club}",
            headers={"Authorization": f"Bearer {self.tokens['club_manager']}"},
        )
        assert res.status_code == 403
        assert res.status_code != 404
        assert res.json()["error"]["code"] == "FORBIDDEN"

    def test_http_rate_limit_101st_request(self):
        """
        Hit GET /api/v1/ping 100 times: all 200 OK.
        101st request returns 429 RATE_LIMITED with Retry-After header.
        """
        ip_header = {"X-Forwarded-For": "203.0.113.195"}

        for i in range(100):
            res = self.client.get("/api/v1/ping", headers=ip_header)
            assert res.status_code == 200
            assert res.json() == {"pong": True}

        # 101st request
        res_101 = self.client.get("/api/v1/ping", headers=ip_header)
        assert res_101.status_code == 429
        assert res_101.json()["error"]["code"] == "RATE_LIMITED"
        assert "Retry-After" in res_101.headers
        retry_val = int(res_101.headers["Retry-After"])
        assert retry_val >= 1

    def test_http_rate_limit_scope_only_api_v1(self):
        """
        Verify /audit/v1/* routes are NOT blocked by /api/v1/* rate limiter.
        """
        ip_header = {"X-Forwarded-For": "203.0.113.199"}

        # Exhaust /api/v1/ping
        for _ in range(100):
            self.client.get("/api/v1/ping", headers=ip_header)

        assert self.client.get("/api/v1/ping", headers=ip_header).status_code == 429

        # /audit/v1/rbac/platform/config should NOT be 429
        audit_res = self.client.get(
            "/audit/v1/rbac/platform/config",
            headers={
                "Authorization": f"Bearer {self.tokens['super_admin']}",
                "X-Forwarded-For": "203.0.113.199",
            },
        )
        assert audit_res.status_code == 200
