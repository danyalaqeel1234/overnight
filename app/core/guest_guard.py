import json
from typing import Any, Callable


class GuestWriteGuardMiddleware:
    """
    Pure ASGI middleware enforcing server-side read-only boundary for guest tokens.
    Intercepts any state-mutating HTTP request (POST/PUT/PATCH/DELETE) carrying a
    guest bearer token or guest session cookie and rejects with 403 GUEST_WRITE_FORBIDDEN
    before request body parsing or validation occurs.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] == "http":
            method = scope.get("method", "").upper()
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                path = scope.get("path", "")
                # Exempt allowed guest staging endpoints (cart staging and cart merge)
                if not (path.startswith("/api/v1/guest/cart") or path == "/audit/v1/guest/cart-merge"):
                    headers = dict(scope.get("headers", []))
                    auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="ignore").strip()
                    guest_token = None

                    if auth_header.lower().startswith("bearer "):
                        token_val = auth_header[7:].strip()
                        if token_val.startswith("guest_"):
                            guest_token = token_val
                    elif auth_header.startswith("guest_"):
                        guest_token = auth_header

                    if not guest_token:
                        cookie_header = headers.get(b"cookie", b"").decode("utf-8", errors="ignore")
                        for part in cookie_header.split(";"):
                            part = part.strip()
                            if part.startswith("guest_token=guest_"):
                                guest_token = part.split("=", 1)[1].strip()
                            elif part.startswith("guest_"):
                                guest_token = part

                    if guest_token:
                        error_body = json.dumps({
                            "error": {
                                "code": "GUEST_WRITE_FORBIDDEN",
                                "message": "Anonymous guest tokens cannot perform write mutations.",
                                "details": {"guest_token": guest_token},
                            }
                        }).encode("utf-8")
                        await send({
                            "type": "http.response.start",
                            "status": 403,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"content-length", str(len(error_body)).encode("utf-8")),
                            ],
                        })
                        await send({
                            "type": "http.response.body",
                            "body": error_body,
                        })
                        return

        await self.app(scope, receive, send)
