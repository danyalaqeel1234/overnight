"""Roster management domain logic."""
from __future__ import annotations
import datetime
from app.core.errors import AppException
from app.domain.models import db_state


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _audit_id() -> str:
    n = sum(1 for _ in db_state.roster_audit)
    return f"au-{n + 1:04d}"


def setup_roster(data: dict) -> dict:
    league_data = data["league"]
    lid = league_data["league_id"]
    squads = data.get("squads", [])
    players = data.get("players", [])
    matches_in_progress = data.get("matches_in_progress", [])

    # Clear existing roster state for this league
    old_squads = {sq_id for sq_id, sq in db_state.roster_squads.items()
                  if sq.get("league_id") == lid}
    for sq_id in old_squads:
        del db_state.roster_squads[sq_id]
    old_players = {pid for pid, pl in db_state.roster_players.items()
                   if pl.get("league_id") == lid}
    for pid in old_players:
        del db_state.roster_players[pid]

    # Store league config
    db_state.roster_leagues[lid] = {
        "league_id": lid,
        "tenant_id": league_data["tenant_id"],
        "sport_id": league_data.get("sport_id"),
        "transfer_window": league_data.get("transfer_window"),
        "max_squad_size": league_data.get("max_squad_size"),
        "required_positions": league_data.get("required_positions", {}),
        "matches_in_progress": matches_in_progress,
    }

    # If max_squad_size / required_positions omitted, use from sport config
    sport_id = league_data.get("sport_id")
    if sport_id and sport_id in db_state.sports:
        sport = db_state.sports[sport_id]
        roster_cfg = sport.get("roster", {})
        if db_state.roster_leagues[lid]["max_squad_size"] is None:
            db_state.roster_leagues[lid]["max_squad_size"] = roster_cfg.get("max_squad_size", 25)
        if not db_state.roster_leagues[lid]["required_positions"]:
            db_state.roster_leagues[lid]["required_positions"] = roster_cfg.get("required_positions", {})

    # Register squads
    squad_counts: dict[str, int] = {}
    for sq in squads:
        sq_id = sq["squad_id"]
        db_state.roster_squads[sq_id] = {
            "squad_id": sq_id,
            "club_id": sq.get("club_id"),
            "tenant_id": sq.get("tenant_id"),
            "name": sq.get("name"),
            "league_id": lid,
        }
        squad_counts[sq_id] = 0

    # Register players
    for pl in players:
        pid = pl["player_id"]
        sq_id = pl["squad_id"]
        db_state.roster_players[pid] = {
            "player_id": pid,
            "name": pl.get("name"),
            "position": pl.get("position"),
            "squad_id": sq_id,
            "parent_squad_id": None,
            "role": pl.get("role", "starter"),
            "league_id": lid,
            "registration_type": "initial",
            "loan_end_date": None,
        }
        if sq_id in squad_counts:
            squad_counts[sq_id] += 1

    # Ensure all squads present (even empty ones)
    for sq in squads:
        if sq["squad_id"] not in squad_counts:
            squad_counts[sq["squad_id"]] = 0

    return {
        "league_id": lid,
        "status": "configured",
        "squad_counts": squad_counts,
    }


def _count_squad(sq_id: str, lid: str) -> int:
    return sum(1 for p in db_state.roster_players.values()
               if p.get("league_id") == lid and p.get("squad_id") == sq_id)


def _count_position(sq_id: str, lid: str, position: str) -> int:
    return sum(1 for p in db_state.roster_players.values()
               if p.get("league_id") == lid and p.get("squad_id") == sq_id and p.get("position") == position)


def transfer_player(data: dict) -> tuple[int, dict]:
    from app.core.crypto import canonical
    request_id = data.get("request_id")
    body_canonical = canonical(data)

    # Idempotency
    if request_id in db_state.idempotency_transfers:
        stored = db_state.idempotency_transfers[request_id]
        if stored["canonical"] == body_canonical:
            return 200, stored["response"]
        raise AppException("DUPLICATE_REQUEST_ID", "Request ID already used with different body.", {}, 409)

    # Check 1: schema/dates validation
    ttype = data.get("type")
    effective_date = data.get("effective_date")
    loan_end_date = data.get("loan_end_date")
    to_squad_id = data.get("to_squad_id")
    from_squad_id = data.get("from_squad_id")
    lid = data.get("league_id")
    player_id = data.get("player_id")

    if ttype not in ("transfer", "loan", "release"):
        raise AppException("VALIDATION_ERROR", "Invalid type.", {"fields": ["type"]}, 400)
    if ttype != "release" and to_squad_id is None:
        raise AppException("VALIDATION_ERROR", "to_squad_id required unless release.", {"fields": ["to_squad_id"]}, 400)
    if ttype == "loan":
        if not loan_end_date:
            raise AppException("VALIDATION_ERROR", "loan_end_date required for loan.", {"fields": ["loan_end_date"]}, 400)
        if loan_end_date <= effective_date:
            raise AppException("VALIDATION_ERROR", "loan_end_date must be after effective_date.", {"fields": ["loan_end_date"]}, 400)

    # Check 2: 404s
    if lid not in db_state.roster_leagues:
        raise AppException("LEAGUE_NOT_FOUND", f"League '{lid}' not found.", {}, 404)
    if player_id not in db_state.roster_players:
        raise AppException("PLAYER_NOT_FOUND", f"Player '{player_id}' not found.", {}, 404)
    if from_squad_id not in db_state.roster_squads:
        raise AppException("SQUAD_NOT_FOUND", f"Squad '{from_squad_id}' not found.", {}, 404)
    if to_squad_id is not None and to_squad_id not in db_state.roster_squads:
        raise AppException("SQUAD_NOT_FOUND", f"Squad '{to_squad_id}' not found.", {}, 404)

    league_cfg = db_state.roster_leagues[lid]
    league_tenant = league_cfg["tenant_id"]
    from_sq = db_state.roster_squads[from_squad_id]
    to_sq = db_state.roster_squads.get(to_squad_id) if to_squad_id else None

    # Check 3: cross-tenant
    if to_sq and to_sq["tenant_id"] != league_tenant:
        raise AppException("CROSS_TENANT_TRANSFER", "Transfer between different tenants.", {}, 409)
    if from_sq["tenant_id"] != league_tenant:
        raise AppException("CROSS_TENANT_TRANSFER", "Transfer between different tenants.", {}, 409)

    # Check 4: player's squad == from_squad_id
    player = db_state.roster_players[player_id]
    if player.get("squad_id") != from_squad_id:
        raise AppException("NOT_IN_SQUAD", f"Player is not in squad '{from_squad_id}'.", {}, 409)

    # Check 5: transfer window
    if ttype in ("transfer", "loan"):
        tw = league_cfg.get("transfer_window")
        if tw:
            window_open = tw["open"]
            window_close = tw["close"]
            if not (window_open <= effective_date <= window_close):
                raise AppException("TRANSFER_WINDOW_CLOSED", "Transfer window is closed.", {}, 409)

    # Check 6: player on loan
    if player.get("registration_type") == "loan" and player.get("loan_end_date"):
        raise AppException("PLAYER_ON_LOAN", "Player is currently on loan.", {}, 409)

    # Check 7: squad full
    if ttype in ("transfer", "loan") and to_squad_id:
        max_size = league_cfg.get("max_squad_size", 25)
        current_count = _count_squad(to_squad_id, lid)
        if current_count + 1 > max_size:
            raise AppException("SQUAD_FULL", f"Squad '{to_squad_id}' is full.", {}, 409)

    # Check 8: min position violation
    position = player.get("position")
    required_pos = league_cfg.get("required_positions", {})
    if position and position in required_pos:
        required_count = required_pos[position]
        current_in_from = _count_position(from_squad_id, lid, position)
        if current_in_from - 1 < required_count:
            raise AppException("MIN_POSITION_VIOLATION", f"From squad would drop below required {position} count.", {}, 409)

    # In-progress match check
    matches_in_progress = league_cfg.get("matches_in_progress", [])
    blocking_match_id = None
    for m in matches_in_progress:
        if from_squad_id in (m.get("home_squad_id"), m.get("away_squad_id")):
            blocking_match_id = m["match_id"]
            break

    state = "deferred_until_match_end" if blocking_match_id else "active"

    # Apply effects
    old_squad_id = player["squad_id"]
    old_role = player.get("role", "substitute")

    if ttype == "transfer":
        player["squad_id"] = to_squad_id
        player["parent_squad_id"] = None
        player["role"] = "substitute"
        player["registration_type"] = "transfer"
        player["loan_end_date"] = None
        reg = {
            "player_id": player_id, "league_id": lid,
            "squad_id": to_squad_id, "parent_squad_id": None,
            "registration_type": "transfer", "start_date": effective_date,
            "loan_end_date": None, "role": "substitute",
        }
    elif ttype == "loan":
        player["squad_id"] = to_squad_id
        player["parent_squad_id"] = from_squad_id
        player["role"] = "substitute"
        player["registration_type"] = "loan"
        player["loan_end_date"] = loan_end_date
        reg = {
            "player_id": player_id, "league_id": lid,
            "squad_id": to_squad_id, "parent_squad_id": from_squad_id,
            "registration_type": "loan", "start_date": effective_date,
            "loan_end_date": loan_end_date, "role": "substitute",
        }
    else:  # release
        player["squad_id"] = None
        player["parent_squad_id"] = None
        player["registration_type"] = "release"
        player["loan_end_date"] = None
        reg = None

    # Audit entry
    audit_id = _audit_id()
    audit_entry = {
        "audit_id": audit_id,
        "action": ttype,
        "player_id": player_id,
        "league_id": lid,
        "from_squad_id": from_squad_id,
        "to_squad_id": to_squad_id,
        "effective_date": effective_date,
        "state": state,
        "who": data.get("requested_by"),
        "when": _now(),
        "why": data.get("reason"),
    }
    db_state.roster_audit.append(audit_entry)

    response = {
        "request_id": request_id,
        "status": "accepted",
        "state": state,
        "blocking_match_id": blocking_match_id,
        "registration": reg,
        "audit_entry": audit_entry,
    }
    db_state.idempotency_transfers[request_id] = {"canonical": body_canonical, "response": response}
    return 201, response


def get_history(player_id: str, as_of: str | None = None) -> dict:
    if player_id not in db_state.roster_players:
        raise AppException("PLAYER_NOT_FOUND", f"Player '{player_id}' not found.", {}, 404)

    if not as_of:
        as_of = _today()

    player = db_state.roster_players[player_id]
    lid = player.get("league_id")

    # Get audit entries for this player in order
    history = [e for e in db_state.roster_audit if e.get("player_id") == player_id]
    history.sort(key=lambda e: (e.get("when", ""), e.get("audit_id", "")))

    # Check for loan auto-return
    current_loan_end = None
    if player.get("registration_type") == "loan" and player.get("loan_end_date"):
        current_loan_end = player["loan_end_date"]

    # Auto-return if as_of > loan_end_date and loan not yet returned
    auto_return_done = any(e.get("action") == "loan_return" for e in history)
    if current_loan_end and as_of > current_loan_end and not auto_return_done:
        # Append loan_return audit entry
        parent_sq = player.get("parent_squad_id")
        audit_id = _audit_id()
        loan_return_entry = {
            "audit_id": audit_id,
            "action": "loan_return",
            "player_id": player_id,
            "league_id": lid,
            "from_squad_id": player.get("squad_id"),
            "to_squad_id": parent_sq,
            "effective_date": current_loan_end,
            "state": "active",
            "who": "system",
            "when": _now(),
            "why": "Loan period ended",
        }
        db_state.roster_audit.append(loan_return_entry)
        history.append(loan_return_entry)
        # Update player state
        player["squad_id"] = parent_sq
        player["parent_squad_id"] = None
        player["registration_type"] = "transfer"
        player["role"] = "substitute"
        player["loan_end_date"] = None

    # Compute current squad as of as_of date
    current_squad = None
    parent_squad = None
    for entry in history:
        eff = entry.get("effective_date", "")
        action = entry.get("action")
        if eff <= as_of or action == "loan_return":
            if action == "transfer":
                current_squad = entry.get("to_squad_id")
                parent_squad = None
            elif action == "loan":
                current_squad = entry.get("to_squad_id")
                parent_squad = entry.get("from_squad_id")
            elif action == "release":
                current_squad = None
                parent_squad = None
            elif action == "loan_return":
                if entry.get("effective_date", "") <= as_of:
                    current_squad = entry.get("to_squad_id")
                    parent_squad = None

    return {
        "player_id": player_id,
        "as_of": as_of,
        "league_id": lid,
        "current_squad_id": current_squad,
        "parent_squad_id": parent_squad,
        "history": history,
    }
