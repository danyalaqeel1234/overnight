"""
Contract Test Suite: 5-Tier RBAC & 7 Probe Routes Matrix (Section 5.13)
Verifies:
- 5 roles: Super Admin, Organizer, Club Manager, Player, Viewer
- 7 probe routes (P1 - P7) across own, other (same tenant), and foreign tenant targets
- Expected authorization status: 200 (allowed) vs 403 FORBIDDEN (cross-tenant / unauthorized)
- 401 UNAUTHENTICATED on missing token, tampered signature, or alg:none
"""

import hmac
import hashlib
import base64
import json
import time
import pytest
from typing import Dict, Any, Optional

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

class RBACPolicyEngine:
    """
    Reference RBAC Policy Engine matching Section 5.13 exactly.
    Used for probe route evaluation and verification.
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
            "foreign_player_id": "player-beta-1"
        }

    def decode_and_verify_token(self, auth_header: Optional[str]) -> tuple[int, Optional[Dict[str, Any]]]:
        if not auth_header or not auth_header.startswith("Bearer "):
            return 401, None
        
        token = auth_header[7:].strip()
        parts = token.split(".")
        if len(parts) != 3:
            return 401, None
        
        h_b64, p_b64, sig_b64 = parts
        
        try:
            # Decode header
            h_pad = h_b64 + "=" * (-len(h_b64) % 4)
            header = json.loads(base64.urlsafe_b64decode(h_pad).decode())
            
            # alg: none MUST be rejected with 401
            if header.get("alg") != "HS256":
                return 401, None
            
            # Verify signature
            signing_input = f"{h_b64}.{p_b64}"
            expected_sig = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
            expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
            
            if not hmac.compare_digest(sig_b64, expected_sig_b64):
                return 401, None
            
            p_pad = p_b64 + "=" * (-len(p_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(p_pad).decode())
            
            if payload.get("exp", float("inf")) < time.time():
                return 401, None
            
            return 200, payload
        except Exception:
            return 401, None

    def evaluate_probe(self, probe_id: str, target: str, token_payload: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        role = token_payload.get("role")
        tenant = token_payload.get("tenant_id")

        # Super Admin is platform-wide allowed for everything
        if role == "super_admin":
            return 200, {"authorized": True}

        # P1: POST /audit/v1/rbac/tenants (Super Admin only)
        if probe_id == "P1":
            return 403, {"error": {"code": "FORBIDDEN", "message": "Super Admin only", "details": {}}}

        # P2: POST /audit/v1/rbac/leagues/{league_id}/fixtures
        if probe_id == "P2":
            if role == "league_organizer" and target == self.context["own_league_id"]:
                return 200, {"authorized": True}
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P3: POST /audit/v1/rbac/clubs/{club_id}/roster
        # P4: POST /audit/v1/rbac/clubs/{club_id}/products
        if probe_id in ("P3", "P4"):
            if role == "club_manager" and target == self.context["own_club_id"]:
                return 200, {"authorized": True}
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P5: PATCH /audit/v1/rbac/players/{player_id}
        if probe_id == "P5":
            if target == self.context["own_player_id"]:
                if role in ("club_manager", "player"):
                    return 200, {"authorized": True}
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P6: GET /audit/v1/rbac/clubs/{club_id} (Viewer/all allowed within tenant-alpha)
        if probe_id == "P6":
            # Allowed for any tenant-alpha role targeting tenant-alpha clubs
            if target in (self.context["own_club_id"], self.context["other_club_id"]):
                if tenant == "tenant-alpha":
                    return 200, {"authorized": True}
            # Foreign club is always 403 for non-super-admin
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        # P7: GET /audit/v1/rbac/platform/config (Super Admin only)
        if probe_id == "P7":
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

        return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}


class TestRBACMatrixContract:
    @pytest.fixture(autouse=True)
    def setup_policy(self):
        self.engine = RBACPolicyEngine()
        now = time.time()
        
        # 5 Seed Roles matching Section 5.13 / Section 8.3
        self.tokens = {
            "super_admin": create_jwt({"role": "super_admin", "sub": "admin", "exp": now + 3600}),
            "organizer": create_jwt({"role": "league_organizer", "tenant_id": "tenant-alpha", "league_id": "league-alpha-1", "exp": now + 3600}),
            "club_manager": create_jwt({"role": "club_manager", "tenant_id": "tenant-alpha", "club_id": "club-alpha-1", "exp": now + 3600}),
            "player": create_jwt({"role": "player", "tenant_id": "tenant-alpha", "player_id": "player-alpha-1", "club_id": "club-alpha-1", "exp": now + 3600}),
            "viewer": create_jwt({"role": "viewer", "tenant_id": "tenant-alpha", "exp": now + 3600}),
        }

    def execute_probe(self, probe_id: str, target: str, token: Optional[str]) -> tuple[int, Dict[str, Any]]:
        status, payload = self.engine.decode_and_verify_token(token)
        if status != 200:
            return 401, {"error": {"code": "UNAUTHENTICATED", "message": "Token invalid or missing", "details": {}}}
        return self.engine.evaluate_probe(probe_id, target, payload)

    def test_p1_tenants_super_admin_only(self):
        """P1: Allowed for Super Admin (200), 403 for all other 4 roles."""
        for role, token in self.tokens.items():
            status, body = self.execute_probe("P1", "", f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
                assert body["authorized"] is True
            else:
                assert status == 403, f"P1 should be 403 for {role}, got {status}"
                assert body["error"]["code"] == "FORBIDDEN"

    def test_p2_fixtures_matrix(self):
        """
        P2: POST /audit/v1/rbac/leagues/{league_id}/fixtures
        - own league: Allowed for Super Admin & Organizer; Denied (403) for Mgr, Player, Viewer
        - other league: Allowed for Super Admin; Denied (403) for Organizer, Mgr, Player, Viewer
        - foreign league: Allowed for Super Admin; Denied (403) for all others
        """
        ctx = self.engine.context

        # Own league
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P2", ctx["own_league_id"], f"Bearer {token}")
            if role in ("super_admin", "organizer"):
                assert status == 200
            else:
                assert status == 403

        # Other league (same tenant)
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P2", ctx["other_league_id"], f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
            else:
                assert status == 403

        # Foreign league
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P2", ctx["foreign_league_id"], f"Bearer {token}")
            assert status == (200 if role == "super_admin" else 403)

    def test_p3_p4_club_roster_and_products_matrix(self):
        """
        P3/P4: Own club allowed for Super Admin & Club Mgr.
        All other combinations (other club, foreign club, other roles) -> 403.
        """
        ctx = self.engine.context
        for probe in ("P3", "P4"):
            # Own club
            for role, token in self.tokens.items():
                status, _ = self.execute_probe(probe, ctx["own_club_id"], f"Bearer {token}")
                if role in ("super_admin", "club_manager"):
                    assert status == 200
                else:
                    assert status == 403

            # Other club (same tenant)
            for role, token in self.tokens.items():
                status, _ = self.execute_probe(probe, ctx["other_club_id"], f"Bearer {token}")
                assert status == (200 if role == "super_admin" else 403)

            # Foreign club
            for role, token in self.tokens.items():
                status, _ = self.execute_probe(probe, ctx["foreign_club_id"], f"Bearer {token}")
                assert status == (200 if role == "super_admin" else 403)

    def test_p5_player_patch_matrix(self):
        """
        P5: PATCH /audit/v1/rbac/players/{player_id}
        Own player: Super Admin (200), Club Manager (200), Player self (200), Organizer (403), Viewer (403).
        Other player / Foreign player: Super Admin (200), all others (403).
        """
        ctx = self.engine.context
        # Own player
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P5", ctx["own_player_id"], f"Bearer {token}")
            if role in ("super_admin", "club_manager", "player"):
                assert status == 200
            else:
                assert status == 403

        # Other player
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P5", ctx["other_player_id"], f"Bearer {token}")
            assert status == (200 if role == "super_admin" else 403)

        # Foreign player
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P5", ctx["foreign_player_id"], f"Bearer {token}")
            assert status == (200 if role == "super_admin" else 403)

    def test_p6_read_club_profile_tenant_boundary(self):
        """
        P6: GET /audit/v1/rbac/clubs/{club_id}
        Own club & Other club in tenant-alpha: Allowed (200) for ALL 5 tenant-alpha roles!
        Foreign club: Allowed (200) ONLY for Super Admin; 403 for all tenant-alpha roles!
        """
        ctx = self.engine.context
        # Own club in tenant-alpha
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P6", ctx["own_club_id"], f"Bearer {token}")
            assert status == 200, f"P6 should be allowed for {role} on own club"

        # Other club in tenant-alpha
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P6", ctx["other_club_id"], f"Bearer {token}")
            assert status == 200, f"P6 should be allowed for {role} on other tenant-alpha club"

        # Foreign club in tenant-beta: Strict 403 for non-super-admin!
        for role, token in self.tokens.items():
            status, body = self.execute_probe("P6", ctx["foreign_club_id"], f"Bearer {token}")
            if role == "super_admin":
                assert status == 200
            else:
                assert status == 403, f"Foreign club probe must return 403 for {role}, got {status}"
                assert body["error"]["code"] == "FORBIDDEN"

    def test_p7_platform_config_super_admin_only(self):
        """P7: GET /audit/v1/rbac/platform/config allowed only for Super Admin."""
        for role, token in self.tokens.items():
            status, _ = self.execute_probe("P7", "", f"Bearer {token}")
            assert status == (200 if role == "super_admin" else 403)

    def test_security_probes_unauthenticated_and_tampered_tokens(self):
        """
        Section 5.13 Additional Security Probes:
        - Missing Authorization header -> 401 UNAUTHENTICATED
        - Token with alg: none -> 401 UNAUTHENTICATED
        - Tampered signature -> 401 UNAUTHENTICATED
        - Expired token -> 401 UNAUTHENTICATED
        """
        # Missing auth header
        status1, body1 = self.execute_probe("P7", "", None)
        assert status1 == 401
        assert body1["error"]["code"] == "UNAUTHENTICATED"

        # alg: none attempt
        alg_none_token = create_jwt({"role": "super_admin"}, alg="none")
        status2, body2 = self.execute_probe("P7", "", f"Bearer {alg_none_token}")
        assert status2 == 401
        assert body2["error"]["code"] == "UNAUTHENTICATED"

        # Tampered signature
        admin_token = self.tokens["super_admin"]
        tampered_token = admin_token[:-4] + "XXXX"
        status3, body3 = self.execute_probe("P7", "", f"Bearer {tampered_token}")
        assert status3 == 401
        assert body3["error"]["code"] == "UNAUTHENTICATED"

        # Expired token
        expired_token = create_jwt({"role": "super_admin", "exp": time.time() - 100})
        status4, body4 = self.execute_probe("P7", "", f"Bearer {expired_token}")
        assert status4 == 401
        assert body4["error"]["code"] == "UNAUTHENTICATED"
