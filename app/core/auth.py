"""Password authentication and scoped authorization for the mobile application."""
import hashlib
import hmac
import secrets
import time
from fastapi import Request
from app.core.errors import AppException
from app.core.security import create_jwt, decode_and_verify_jwt
from app.domain.models import db_state


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"{salt}${digest}"


def profile(user):
    return {k: v for k, v in user.items() if k != "password_hash"}


def login(email, password):
    user = db_state.users.get(email.lower()) if isinstance(email, str) else None
    if not user or not isinstance(password, str):
        raise AppException("UNAUTHENTICATED", "Email or password is incorrect.", {}, 401)
    stored = user["password_hash"]
    if not hmac.compare_digest(password_hash(password, stored.split("$")[0]), stored):
        raise AppException("UNAUTHENTICATED", "Email or password is incorrect.", {}, 401)
    user_info = profile(user)
    return {"token": create_jwt({**user_info, "exp": int(time.time()) + 86400}), "user": user_info}


def authenticate_header(header):
    token = header[7:] if header and header.startswith("Bearer ") else ""
    code, claims, _ = decode_and_verify_jwt(token)
    if code != 200 or not claims or not isinstance(claims.get("exp"), (int, float)):
        raise AppException("UNAUTHENTICATED", "Please sign in again.", {}, 401)
    user = db_state.users.get(claims.get("email"))
    if not user or user["sub"] != claims.get("sub"):
        raise AppException("UNAUTHENTICATED", "Please sign in again.", {}, 401)
    return profile(user)


def current_user(request: Request):
    return authenticate_header(request.headers.get("authorization"))


def authorize(user, role=None, *, tenant=None, league=None, club=None):
    if user["role"] == "super_admin":
        return
    if ((role and user["role"] not in role) or (tenant and user.get("tenant_id") != tenant)
            or (league and user.get("league_id") != league) or (club and user.get("club_id") != club)):
        raise AppException("FORBIDDEN", "Your account cannot perform this action.", {}, 403)
