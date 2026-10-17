from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.security import context, evaluate_probe, generate_seed_tokens

router = APIRouter()


@router.post("/audit/v1/rbac-matrix")
async def rbac_matrix():
    return {"tokens": generate_seed_tokens(), "context": context}


@router.post("/audit/v1/rbac/tenants")
async def probe_p1(request: Request):
    auth = request.headers.get("authorization")
    status, body = evaluate_probe("P1", "", auth)
    return JSONResponse(status_code=status, content=body)


@router.post("/audit/v1/rbac/leagues/{league_id}/fixtures")
async def probe_p2(league_id: str, request: Request):
    auth = request.headers.get("authorization")
    status, body = evaluate_probe("P2", league_id, auth)
    return JSONResponse(status_code=status, content=body)


@router.post("/audit/v1/rbac/clubs/{club_id}/roster")
async def probe_p3(club_id: str, request: Request):
    auth = request.headers.get("authorization")
    status, body = evaluate_probe("P3", club_id, auth)
    return JSONResponse(status_code=status, content=body)


@router.post("/audit/v1/rbac/clubs/{club_id}/products")
async def probe_p4(club_id: str, request: Request):
    auth = request.headers.get("authorization")
    status, body = evaluate_probe("P4", club_id, auth)
    return JSONResponse(status_code=status, content=body)


@router.patch("/audit/v1/rbac/players/{player_id}")
async def probe_p5(player_id: str, request: Request):
    auth = request.headers.get("authorization")
    status, body = evaluate_probe("P5", player_id, auth)
    return JSONResponse(status_code=status, content=body)


@router.get("/audit/v1/rbac/clubs/{club_id}")
async def probe_p6(club_id: str, request: Request):
    auth = request.headers.get("authorization")
    status, body = evaluate_probe("P6", club_id, auth)
    return JSONResponse(status_code=status, content=body)


@router.get("/audit/v1/rbac/platform/config")
async def probe_p7(request: Request):
    auth = request.headers.get("authorization")
    status, body = evaluate_probe("P7", "", auth)
    return JSONResponse(status_code=status, content=body)
