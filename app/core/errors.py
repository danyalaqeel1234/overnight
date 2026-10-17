from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details if details is not None else {}
        self.status_code = status_code


def _err(code: str, message: str, details: dict, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return _err(exc.code, exc.message, exc.details, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields: set[str] = set()
        for error in exc.errors():
            loc = error.get("loc", ())
            # Skip the "body" prefix added by FastAPI
            parts = [str(p) for p in loc if p != "body"]
            if parts:
                fields.add(".".join(parts))
        sorted_fields = sorted(fields)
        return _err(
            "VALIDATION_ERROR",
            "Validation error",
            {"fields": sorted_fields},
            400,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if exc.status_code == 404:
            return _err("NOT_FOUND", exc.detail or "Not found", {}, 404)
        if exc.status_code == 405:
            return _err("METHOD_NOT_ALLOWED", exc.detail or "Method not allowed", {}, 405)
        return _err(
            "HTTP_ERROR",
            str(exc.detail) if exc.detail else "HTTP error",
            {},
            exc.status_code,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return _err("INTERNAL_SERVER_ERROR", "An internal error occurred", {}, 500)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    _MAX = 1_048_576

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None and int(cl) > self._MAX:
            return _err(
                "PAYLOAD_TOO_LARGE", "Payload exceeds 1 MB limit", {}, 413
            )
        body = await request.body()
        if len(body) > self._MAX:
            return _err(
                "PAYLOAD_TOO_LARGE", "Payload exceeds 1 MB limit", {}, 413
            )
        return await call_next(request)
