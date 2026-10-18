from __future__ import annotations
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from app.core.errors import AppException
from app.domain.qr_guest import qr_guest_domain

router = APIRouter()


@router.get("/audit/v1/qr/{entity_id}")
async def get_qr(entity_id: str, request: Request):
    inspect_param = request.query_params.get("inspect", "false").lower()
    inspect = inspect_param in ("true", "1")
    result = qr_guest_domain.get_qr(entity_id, inspect=inspect)
    return JSONResponse(status_code=200, content=result)


@router.get("/audit/v1/qr/{entity_id}/export.svg")
async def export_qr_svg(entity_id: str):
    svg_bytes = qr_guest_domain.export_svg(entity_id)
    return Response(content=svg_bytes, media_type="image/svg+xml")


@router.get("/audit/v1/qr/{entity_id}/export.png")
async def export_qr_png(entity_id: str):
    png_bytes = qr_guest_domain.export_png(entity_id)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/audit/v1/qr/{entity_id}/export.pdf")
async def export_qr_pdf(entity_id: str):
    pdf_bytes = qr_guest_domain.export_pdf(entity_id)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/q/{short_code}")
async def redirect_short_code(short_code: str, request: Request):
    ua = request.headers.get("user-agent", "")
    target_route = qr_guest_domain.resolve_short_code(short_code, user_agent=ua)
    return RedirectResponse(url=target_route, status_code=302)
