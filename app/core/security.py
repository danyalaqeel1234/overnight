import base64
import hashlib
import hmac
import json
import time
from typing import Any

SECRET_KEY = "nascon-26-rbac-secret-key"

context = {
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

_player_club_map = {
    "player-alpha-1": "club-alpha-1",
    "player-alpha-2": "club-alpha-2",
    "player-beta-1": "club-beta-1",
    "player-beta-2": "club-beta-1",
}

_league_tenant_map = {
    "league-alpha-1": "tenant-alpha",
    "league-alpha-2": "tenant-alpha",
    "league-beta-1": "tenant-beta",
}

_club_tenant_map = {
    "club-alpha-1": "tenant-alpha",
    "club-alpha-2": "tenant-alpha",
    "club-beta-1": "tenant-beta",
}


def create_jwt(payload: dict, secret: str = SECRET_KEY, alg: str = "HS256") -> str:
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


def decode_and_verify_jwt(token: str, secret: str = SECRET_KEY) -> tuple[int, dict | None, str | None]:
    if not token:
        return 401, None, "UNAUTHENTICATED"
    parts = token.split(".")
    if len(parts) != 3:
        return 401, None, "UNAUTHENTICATED"
    h_b64, p_b64, sig_b64 = parts
    try:
        h_pad = h_b64 + "=" * (-len(h_b64) % 4)
        header = json.loads(base64.urlsafe_b64decode(h_pad).decode())
        if header.get("alg") != "HS256":
            return 401, None, "UNAUTHENTICATED"
        signing_input = f"{h_b64}.{p_b64}"
        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return 401, None, "UNAUTHENTICATED"
        p_pad = p_b64 + "=" * (-len(p_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(p_pad).decode())
        if "exp" in payload and payload["exp"] < time.time():
            return 401, None, "UNAUTHENTICATED"
        return 200, payload, None
    except Exception:
        return 401, None, "UNAUTHENTICATED"


def generate_seed_tokens() -> dict:
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
            "sub": "player-1",
            "exp": now + 7200,
        }),
        "viewer": create_jwt({
            "role": "viewer",
            "tenant_id": "tenant-alpha",
            "sub": "view-1",
            "exp": now + 7200,
        }),
    }


def evaluate_probe(probe_id: str, target_id: str, auth_header: str | None) -> tuple[int, dict]:
    if not auth_header or not auth_header.startswith("Bearer "):
        return 401, {"error": {"code": "UNAUTHENTICATED", "message": "Unauthenticated", "details": {}}}

    raw_token = auth_header[7:].strip()
    status, payload, err_code = decode_and_verify_jwt(raw_token)
    if status != 200 or not payload:
        return 401, {"error": {"code": "UNAUTHENTICATED", "message": "Unauthenticated", "details": {}}}

    role = payload.get("role")
    user_tenant = payload.get("tenant_id")

    if role == "super_admin":
        return 200, {"authorized": True}

    if probe_id == "P1":
        return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

    if probe_id == "P2":
        league_tenant = _league_tenant_map.get(target_id)
        if league_tenant is None:
            return 404, {"error": {"code": "LEAGUE_NOT_FOUND", "message": "League not found", "details": {}}}
        if league_tenant != user_tenant:
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}
        if role == "league_organizer" and target_id == payload.get("league_id"):
            return 200, {"authorized": True}
        return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

    if probe_id in ("P3", "P4"):
        club_tenant = _club_tenant_map.get(target_id)
        if club_tenant is None:
            return 404, {"error": {"code": "CLUB_NOT_FOUND", "message": "Club not found", "details": {}}}
        if club_tenant != user_tenant:
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}
        if role == "club_manager" and target_id == payload.get("club_id"):
            return 200, {"authorized": True}
        return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

    if probe_id == "P5":
        player_club = _player_club_map.get(target_id)
        if player_club is None:
            return 404, {"error": {"code": "PLAYER_NOT_FOUND", "message": "Player not found", "details": {}}}
        club_tenant = _club_tenant_map.get(player_club)
        if club_tenant != user_tenant:
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}
        if role == "club_manager" and player_club == payload.get("club_id"):
            return 200, {"authorized": True}
        if role == "player" and target_id == payload.get("player_id"):
            return 200, {"authorized": True}
        return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

    if probe_id == "P6":
        club_tenant = _club_tenant_map.get(target_id)
        if club_tenant is None:
            return 404, {"error": {"code": "CLUB_NOT_FOUND", "message": "Club not found", "details": {}}}
        if club_tenant != user_tenant:
            return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}
        return 200, {"authorized": True}

    if probe_id == "P7":
        return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}

    return 403, {"error": {"code": "FORBIDDEN", "message": "Forbidden", "details": {}}}
