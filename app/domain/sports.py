"""Sports domain logic: validation and creation."""
from __future__ import annotations

import re
from typing import Any

from app.core.errors import AppException

_SPORT_ID_RE = re.compile(r"^[a-z0-9_-]{2,40}$")
_EVENT_KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")

_VALID_OVERTIME_POLICIES = {"none", "extra_time", "shootout", "golden_score", "super_over"}
_VALID_TIE_BREAK_ITEMS = {"h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"}
_DEFAULT_TIE_BREAK = ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"]


def _bad(fields: list[str]) -> AppException:
    return AppException(
        code="VALIDATION_ERROR",
        message="Validation error",
        details={"fields": sorted(set(fields))},
        status_code=400,
    )


def validate_and_normalise(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw sport creation dict and return normalised config."""
    errors: list[str] = []

    # sport_id
    sport_id = data.get("sport_id", "")
    if not isinstance(sport_id, str) or not _SPORT_ID_RE.match(sport_id):
        errors.append("sport_id")

    # name
    name = data.get("name", "")
    if not isinstance(name, str) or not (1 <= len(name) <= 80):
        errors.append("name")

    # scoring_model
    scoring_model = data.get("scoring_model")
    if scoring_model not in ("event", "innings", "round"):
        errors.append("scoring_model")

    # periods
    periods = data.get("periods")
    if not isinstance(periods, dict):
        errors.append("periods")
    else:
        if scoring_model == "event":
            if not isinstance(periods.get("count"), int) or isinstance(periods.get("count"), bool) or periods["count"] < 1:
                errors.append("periods.count")
            if not isinstance(periods.get("duration_minutes"), int) or isinstance(periods.get("duration_minutes"), bool) or periods["duration_minutes"] < 1:
                errors.append("periods.duration_minutes")
        elif scoring_model == "innings":
            for field in ("innings_per_team", "overs_per_innings", "balls_per_over", "wickets_per_innings"):
                v = periods.get(field)
                if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                    errors.append(f"periods.{field}")
        elif scoring_model == "round":
            bo = periods.get("best_of")
            if not isinstance(bo, int) or isinstance(bo, bool) or bo < 1 or bo % 2 == 0:
                errors.append("periods.best_of")

    # scoring_events
    scoring_events = data.get("scoring_events")
    if not isinstance(scoring_events, dict) or len(scoring_events) < 1:
        errors.append("scoring_events")
    else:
        for k, v in scoring_events.items():
            if not _EVENT_KEY_RE.match(str(k)):
                errors.append(f"scoring_events.{k}")
                continue
            if not isinstance(v, dict):
                errors.append(f"scoring_events.{k}")
                continue
            if scoring_model == "event":
                pts = v.get("points")
                if not isinstance(pts, int) or isinstance(pts, bool) or pts < 1:
                    errors.append(f"scoring_events.{k}.points")
            elif scoring_model == "innings":
                runs = v.get("runs")
                lb = v.get("legal_ball")
                wk = v.get("wicket")
                if not isinstance(runs, int) or isinstance(runs, bool) or runs < 0:
                    errors.append(f"scoring_events.{k}.runs")
                if not isinstance(lb, bool):
                    errors.append(f"scoring_events.{k}.legal_ball")
                if not isinstance(wk, bool):
                    errors.append(f"scoring_events.{k}.wicket")
            elif scoring_model == "round":
                rds = v.get("rounds")
                if not isinstance(rds, int) or isinstance(rds, bool) or rds < 1:
                    errors.append(f"scoring_events.{k}.rounds")

    # draw_allowed
    if not isinstance(data.get("draw_allowed"), bool):
        errors.append("draw_allowed")

    # overtime
    overtime = data.get("overtime")
    if not isinstance(overtime, dict):
        errors.append("overtime")
    else:
        policy = overtime.get("policy")
        if policy not in _VALID_OVERTIME_POLICIES:
            errors.append("overtime.policy")
        dm = overtime.get("duration_minutes")
        if dm is not None:
            if not isinstance(dm, int) or isinstance(dm, bool) or dm < 0:
                errors.append("overtime.duration_minutes")

    # tie_break_order (optional)
    tbo_raw = data.get("tie_break_order")
    if tbo_raw is not None:
        if not isinstance(tbo_raw, list):
            errors.append("tie_break_order")
        else:
            seen = set()
            for item in tbo_raw:
                if item not in _VALID_TIE_BREAK_ITEMS:
                    errors.append("tie_break_order")
                    break
                if item in seen:
                    errors.append("tie_break_order")
                    break
                seen.add(item)

    # roster
    roster = data.get("roster")
    if not isinstance(roster, dict):
        errors.append("roster")
    else:
        mn = roster.get("min_squad_size")
        mx = roster.get("max_squad_size")
        if not isinstance(mn, int) or isinstance(mn, bool) or mn < 1:
            errors.append("roster.min_squad_size")
        if not isinstance(mx, int) or isinstance(mx, bool) or mx < 1:
            errors.append("roster.max_squad_size")
        if isinstance(mn, int) and isinstance(mx, int) and not isinstance(mn, bool) and not isinstance(mx, bool) and mn > mx:
            errors.append("roster.min_squad_size")
        rp = roster.get("required_positions")
        if rp is not None and not isinstance(rp, dict):
            errors.append("roster.required_positions")

    if errors:
        raise _bad(errors)

    # Normalise tie_break_order: remove draw_lots if present, then append
    if tbo_raw is None:
        tbo = list(_DEFAULT_TIE_BREAK)
    else:
        tbo = [x for x in tbo_raw if x != "draw_lots"]
        tbo.append("draw_lots")

    config = {
        "sport_id": sport_id,
        "name": name,
        "scoring_model": scoring_model,
        "periods": periods,
        "scoring_events": scoring_events,
        "draw_allowed": data["draw_allowed"],
        "overtime": overtime,
        "tie_break_order": tbo,
        "roster": {
            "min_squad_size": roster["min_squad_size"],
            "max_squad_size": roster["max_squad_size"],
            "required_positions": roster.get("required_positions") or {},
        },
    }
    return config
