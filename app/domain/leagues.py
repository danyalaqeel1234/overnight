"""League registration domain logic."""
from __future__ import annotations
from app.core.errors import AppException
from app.domain.models import db_state


def create_league(data: dict) -> dict:
    league_id = data["league_id"]
    sport_id = data["sport_id"]
    teams = data["teams"]
    fixtures = data["fixtures"]
    points = data.get("points") or {"win": 3, "draw": 1, "loss": 0}
    qualification = data["qualification"]
    lots_seed = data.get("lots_seed")
    if lots_seed is None:
        lots_seed = db_state.current_seed

    # Validations
    if sport_id not in db_state.sports:
        raise AppException("SPORT_NOT_FOUND", f"Sport '{sport_id}' not found.", {}, 404)

    sport = db_state.sports[sport_id]
    tie_break_order = data.get("tie_break_order") or sport.get("tie_break_order", [
        "h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"
    ])

    teams_set = set(teams)
    if len(teams_set) != len(teams):
        raise AppException("VALIDATION_ERROR", "Teams must be unique.", {"fields": ["teams"]}, 400)

    if league_id in db_state.leagues:
        raise AppException("LEAGUE_EXISTS", f"League '{league_id}' already exists.", {}, 409)

    # Check match_id uniqueness
    for fix in fixtures:
        if fix["match_id"] in db_state.matches:
            raise AppException("MATCH_EXISTS", f"Match '{fix['match_id']}' already exists.", {}, 409)
        h, a = fix["home"], fix["away"]
        if h not in teams_set or a not in teams_set:
            raise AppException("VALIDATION_ERROR", "Fixture teams must be in league teams.", {"fields": ["fixtures"]}, 400)
        if h == a:
            raise AppException("VALIDATION_ERROR", "Home and away teams must differ.", {"fields": ["fixtures"]}, 400)

    # Check fixture match_id uniqueness within the request
    seen_match_ids = set()
    for fix in fixtures:
        if fix["match_id"] in seen_match_ids:
            raise AppException("MATCH_EXISTS", f"Duplicate match_id '{fix['match_id']}' in fixtures.", {}, 409)
        seen_match_ids.add(fix["match_id"])

    # Create league
    db_state.leagues[league_id] = {
        "league_id": league_id,
        "sport_id": sport_id,
        "teams": list(teams),
        "fixtures": [dict(f) for f in fixtures],
        "points": points,
        "tie_break_order": tie_break_order,
        "qualification": qualification,
        "lots_seed": lots_seed,
    }

    # Auto-register fixtures as match streams (status upcoming)
    for fix in fixtures:
        mid = fix["match_id"]
        db_state.matches[mid] = {
            "match_id": mid,
            "sport_id": sport_id,
            "home_team_id": fix["home"],
            "away_team_id": fix["away"],
            "league_id": league_id,
        }
        db_state.events[mid] = []

    return {
        "league_id": league_id,
        "status": "created",
        "team_count": len(teams),
        "fixture_count": len(fixtures),
    }
