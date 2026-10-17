from __future__ import annotations

import json
import math

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppException
from app.domain.fixtures import (
    generate_double_elim,
    generate_round_robin,
    generate_single_elim,
    generate_swiss,
)

router = APIRouter()


def _val_err(fields: list[str]) -> AppException:
    return AppException("VALIDATION_ERROR", "Validation error", {"fields": sorted(set(fields))}, 400)


@router.post("/audit/v1/fixtures")
async def fixtures(request: Request):
    try:
        raw = await request.body()
        data = json.loads(raw) if raw else {}
    except Exception:
        raise _val_err([])

    if not isinstance(data, dict):
        raise _val_err([])

    fmt = data.get("format")
    teams = data.get("teams")
    params = data.get("params") or {}

    if not isinstance(teams, list) or len(teams) < 2:
        raise _val_err(["teams"])
    if len(teams) != len(set(teams)):
        raise _val_err(["teams"])

    if fmt == "round_robin":
        legs = params.get("legs", 1)
        withdrawals = params.get("withdrawals", [])
        withdrawal_policy = params.get("withdrawal_policy", "forfeit_remaining")
        if not isinstance(legs, int) or isinstance(legs, bool) or legs not in (1, 2):
            raise _val_err(["params.legs"])
        if not isinstance(withdrawals, list):
            raise _val_err(["params.withdrawals"])
        if withdrawal_policy not in ("void_all", "forfeit_remaining"):
            raise _val_err(["params.withdrawal_policy"])
        result = generate_round_robin(
            teams=teams,
            legs=legs,
            withdrawals=withdrawals,
            withdrawal_policy=withdrawal_policy,
        )
        return JSONResponse(status_code=200, content=result)

    elif fmt == "swiss":
        total_rounds_raw = params.get("total_rounds")
        round_num = params.get("round", 1)
        history = params.get("history", [])

        if total_rounds_raw is not None:
            if not isinstance(total_rounds_raw, int) or isinstance(total_rounds_raw, bool):
                raise _val_err(["params.total_rounds"])
        if not isinstance(round_num, int) or isinstance(round_num, bool):
            raise _val_err(["params.round"])
        if not isinstance(history, list):
            raise _val_err(["params.history"])

        result = generate_swiss(
            teams=teams,
            total_rounds=total_rounds_raw,
            round_num=round_num,
            history=history,
        )
        return JSONResponse(status_code=200, content=result)

    elif fmt == "single_elim":
        third_place = params.get("third_place_match", False)
        results_raw = params.get("results", [])
        if not isinstance(results_raw, list):
            raise _val_err(["params.results"])
        result = generate_single_elim(
            teams=teams,
            third_place_match=bool(third_place),
            results=results_raw,
        )
        return JSONResponse(status_code=200, content=result)

    elif fmt == "double_elim":
        br = params.get("bracket_reset", False)
        results_raw = params.get("results", [])
        if not isinstance(results_raw, list):
            raise _val_err(["params.results"])
        result = generate_double_elim(
            teams=teams,
            bracket_reset=bool(br),
            results=results_raw,
        )
        return JSONResponse(status_code=200, content=result)

    else:
        raise _val_err(["format"])
