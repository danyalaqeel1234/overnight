from __future__ import annotations
import pathlib
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()

_TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "web" / "templates"


def _render_guest_player(match_id: str = "", session_id: str = "") -> str:
    tmpl = (_TEMPLATE_DIR / "guest_player.html").read_text(encoding="utf-8")
    tmpl = tmpl.replace("{{ match_id }}", match_id)
    tmpl = tmpl.replace("{{ session_id }}", session_id)
    return tmpl


@router.get("/web/matches/{match_id}/live", response_class=HTMLResponse)
async def match_live(match_id: str):
    return HTMLResponse(_render_guest_player(match_id=match_id))


@router.get("/web/matches/{match_id}/preview", response_class=HTMLResponse)
async def match_preview(match_id: str):
    return HTMLResponse(_render_guest_player(match_id=match_id))


@router.get("/web/matches/{match_id}/vod", response_class=HTMLResponse)
async def match_vod(match_id: str):
    return HTMLResponse(_render_guest_player(match_id=match_id))


@router.get("/web/matches/{match_id}/notice", response_class=HTMLResponse)
async def match_notice(match_id: str, state: str = ""):
    html = _render_guest_player(match_id=match_id)
    # Inject a notice banner after <h1>
    notice = (
        f'<div role="alert" style="background:#7f1d1d;color:#fecaca;padding:12px 24px;'
        f'text-align:center;font-weight:600;">Match status: {state}</div>'
    )
    html = html.replace("<h1>NaSCon '26 Live</h1>", f"<h1>NaSCon '26 Live</h1>{notice}")
    return HTMLResponse(html)


@router.get("/web/costream/{session_id}", response_class=HTMLResponse)
async def costream_view(session_id: str):
    # Costream also uses the guest player template; match_id derived from session context
    return HTMLResponse(_render_guest_player(session_id=session_id))


@router.get("/web/players/{player_id}", response_class=HTMLResponse)
async def player_profile(player_id: str):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><title>Athlete Profile</title>
<style>body{{background:#0b0f19;color:#f8fafc;font-family:system-ui,sans-serif;padding:2rem}}</style>
</head>
<body>
  <h1>Athlete Profile: {player_id}</h1>
  <section aria-label="Career records">
    <h2>Career Records</h2>
    <p>Stats loading…</p>
  </section>
  <section aria-label="Fixtures">
    <h2>Fixtures</h2>
    <p>Upcoming fixtures loading…</p>
  </section>
</body>
</html>"""
    return HTMLResponse(html)


@router.get("/web/clubs/{club_id}", response_class=HTMLResponse)
async def club_view(club_id: str):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><title>Club</title>
<style>body{{background:#0b0f19;color:#f8fafc;font-family:system-ui,sans-serif;padding:2rem}}</style>
</head>
<body>
  <h1>Club: {club_id}</h1>
  <section aria-label="Club information">
    <p>Club details loading…</p>
  </section>
</body>
</html>"""
    return HTMLResponse(html)
