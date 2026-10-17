"""Event-sourced scoring engine."""
from __future__ import annotations
import datetime
from app.core.config import DAY1_SALT
from app.core.crypto import sign, canonical
from app.core.errors import AppException
from app.domain.models import db_state


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def project_match(match_id: str) -> dict | None:
    """Rebuild full match state from event log. Returns None if match not found."""
    match = db_state.matches.get(match_id)
    if not match:
        return None
    sport = db_state.sports[match["sport_id"]]
    model = sport["scoring_model"]
    bpo = sport["periods"].get("balls_per_over", 6) if model == "innings" else None
    events = db_state.events.get(match_id, [])

    # Pre-pass: build compensated map (event_id -> compensating_event_id)
    compensated: dict[str, str] = {}
    for ev in events:
        if ev["type"] == "compensation":
            target = ev["payload"]["compensates"]
            compensated[target] = ev["event_id"]

    home_id = match["home_team_id"]
    away_id = match["away_team_id"]
    status = "upcoming"
    home_score = away_score = 0
    home_wickets = away_wickets = 0
    home_balls = away_balls = 0
    home_fair = away_fair = 0
    tiebreak_winner = None  # active tiebreak winner team_id

    for ev in events:
        if ev["event_id"] in compensated:
            continue  # skip compensated events
        t = ev["type"]
        p = ev["payload"]
        if t == "match_start":
            status = "in_progress"
        elif t == "match_end":
            status = "completed"
        elif t == "score":
            tid = p["team_id"]
            etype = p["event_type"]
            ecfg = sport["scoring_events"][etype]
            if model == "event":
                pts = ecfg["points"]
                if tid == home_id:
                    home_score += pts
                else:
                    away_score += pts
            elif model == "innings":
                runs = ecfg.get("runs", 0)
                legal = ecfg.get("legal_ball", False)
                wicket = ecfg.get("wicket", False)
                if tid == home_id:
                    home_score += runs
                    if legal:
                        home_balls += 1
                    if wicket:
                        home_wickets += 1
                else:
                    away_score += runs
                    if legal:
                        away_balls += 1
                    if wicket:
                        away_wickets += 1
            elif model == "round":
                rounds = ecfg.get("rounds", 1)
                if tid == home_id:
                    home_score += rounds
                else:
                    away_score += rounds
        elif t == "discipline":
            tid = p["team_id"]
            if tid == home_id:
                home_fair += p["points"]
            else:
                away_fair += p["points"]
        elif t == "tiebreak_winner":
            tiebreak_winner = p["team_id"]

    # Determine outcome
    outcome = "pending"
    winner_id = None
    if status == "completed":
        if home_score > away_score:
            outcome = "home_win"
            winner_id = home_id
        elif away_score > home_score:
            outcome = "away_win"
            winner_id = away_id
        else:
            if tiebreak_winner:
                outcome = "home_win" if tiebreak_winner == home_id else "away_win"
                winner_id = tiebreak_winner
            elif sport.get("draw_allowed", True):
                outcome = "draw"
            else:
                outcome = "undecided"

    events_out = []
    for ev in events:
        events_out.append({
            "sequence": ev["sequence"],
            "event_id": ev["event_id"],
            "type": ev["type"],
            "payload": ev["payload"],
            "signature": ev["signature"],
            "compensated": ev["event_id"] in compensated,
            "compensated_by": compensated.get(ev["event_id"]),
        })

    home_data = {
        "team_id": home_id, "score": home_score,
        "wickets": home_wickets if model == "innings" else None,
        "balls": home_balls if model == "innings" else None,
        "overs": f"{home_balls // bpo}.{home_balls % bpo}" if model == "innings" else None,
        "fair_play": home_fair,
    }
    away_data = {
        "team_id": away_id, "score": away_score,
        "wickets": away_wickets if model == "innings" else None,
        "balls": away_balls if model == "innings" else None,
        "overs": f"{away_balls // bpo}.{away_balls % bpo}" if model == "innings" else None,
        "fair_play": away_fair,
    }

    return {
        "match_id": match_id,
        "sport_id": match["sport_id"],
        "league_id": match.get("league_id"),
        "status": status,
        "outcome": outcome,
        "winner_team_id": winner_id,
        "tiebreak_winner_team_id": tiebreak_winner,
        "home": home_data,
        "away": away_data,
        "version": len(events),
        "events": events_out,
    }


def add_event(data: dict) -> tuple[int, dict]:
    """Validate and append event. Returns (status_code, response_dict)."""
    event_id = data.get("event_id")
    match_id = data.get("match_id")
    etype = data.get("type")
    payload = data.get("payload", {})
    body_canonical = canonical(data)

    # Idempotency check
    if event_id in db_state.idempotency_events:
        stored = db_state.idempotency_events[event_id]
        if stored["canonical"] == body_canonical:
            return 200, stored["response"]
        raise AppException("DUPLICATE_EVENT_ID", "Event ID already used with different payload.", {}, 409)

    # Check if match exists
    match_exists = match_id in db_state.matches

    if etype == "match_init":
        if match_exists:
            raise AppException("MATCH_EXISTS", f"Match '{match_id}' already exists.", {}, 409)
        sport_id = payload.get("sport_id")
        if not sport_id or sport_id not in db_state.sports:
            raise AppException("SPORT_NOT_FOUND", f"Sport not found.", {}, 404)
        home = payload.get("home_team_id")
        away = payload.get("away_team_id")
        league_id = payload.get("league_id")
        # Create match
        db_state.matches[match_id] = {
            "match_id": match_id, "sport_id": sport_id,
            "home_team_id": home, "away_team_id": away,
            "league_id": league_id,
        }
        db_state.events[match_id] = []
    else:
        if not match_exists:
            raise AppException("MATCH_NOT_FOUND", f"Match '{match_id}' not found.", {}, 404)

    match = db_state.matches[match_id]
    sport = db_state.sports[match["sport_id"]]
    events = db_state.events[match_id]
    state = project_match(match_id)
    status = state["status"]

    if etype == "match_start":
        if status != "upcoming":
            raise AppException("ILLEGAL_TRANSITION", f"Cannot start match in status '{status}'.", {}, 409)
    elif etype == "match_end":
        if status != "in_progress":
            raise AppException("ILLEGAL_TRANSITION", f"Cannot end match in status '{status}'.", {}, 409)
        # Check TIE_NOT_ALLOWED
        home_score = state["home"]["score"]
        away_score = state["away"]["score"]
        if home_score == away_score and not sport.get("draw_allowed", True) and not state["tiebreak_winner_team_id"]:
            raise AppException("TIE_NOT_ALLOWED", "Draw not allowed and no tiebreak winner.", {}, 409)
    elif etype == "score":
        if status != "in_progress":
            raise AppException("MATCH_NOT_IN_PROGRESS", f"Match is not in progress.", {}, 409)
        team_id = payload.get("team_id")
        if team_id not in (match["home_team_id"], match["away_team_id"]):
            raise AppException("VALIDATION_ERROR", "team_id must be home or away team.", {"fields": ["team_id"]}, 400)
        event_type = payload.get("event_type")
        if event_type not in sport["scoring_events"]:
            raise AppException("UNKNOWN_EVENT_TYPE", f"Unknown event type '{event_type}'.", {}, 400)
        # Check model limits
        model = sport["scoring_model"]
        if model == "innings":
            ipt = sport["periods"]["innings_per_team"]
            opi = sport["periods"]["overs_per_innings"]
            bpo = sport["periods"]["balls_per_over"]
            wpi = sport["periods"]["wickets_per_innings"]
            max_balls = ipt * opi * bpo
            max_wickets = ipt * wpi
            team_data = state["home"] if team_id == match["home_team_id"] else state["away"]
            if team_data["balls"] >= max_balls or team_data["wickets"] >= max_wickets:
                raise AppException("INNINGS_COMPLETE", "Innings complete for this team.", {}, 409)
        elif model == "round":
            best_of = sport["periods"]["best_of"]
            needed = (best_of + 1) // 2
            team_data = state["home"] if team_id == match["home_team_id"] else state["away"]
            if team_data["score"] >= needed:
                raise AppException("SERIES_ALREADY_DECIDED", "Series already decided.", {}, 409)
    elif etype == "discipline":
        if status != "in_progress":
            raise AppException("MATCH_NOT_IN_PROGRESS", "Match is not in progress.", {}, 409)
    elif etype == "tiebreak_winner":
        if status != "in_progress":
            raise AppException("MATCH_NOT_IN_PROGRESS", "Match is not in progress.", {}, 409)
    elif etype == "compensation":
        # Any status after init
        target_id = payload.get("compensates")
        # Find target event in this match
        target_ev = next((e for e in events if e["event_id"] == target_id), None)
        if target_ev is None:
            raise AppException("EVENT_NOT_FOUND", f"Event '{target_id}' not found.", {}, 404)
        # Must be score/discipline/tiebreak_winner
        if target_ev["type"] not in ("score", "discipline", "tiebreak_winner"):
            raise AppException("INVALID_COMPENSATION", "Can only compensate score/discipline/tiebreak_winner events.", {}, 409)
        # Check not already compensated
        for ev in events:
            if ev["type"] == "compensation" and ev["payload"].get("compensates") == target_id:
                raise AppException("INVALID_COMPENSATION", "Event already compensated.", {}, 409)

    # Append event
    seq = len(events) + 1
    sig = sign(DAY1_SALT, event_id, payload)
    ev_record = {
        "event_id": event_id,
        "match_id": match_id,
        "type": etype,
        "payload": payload,
        "sequence": seq,
        "signature": sig,
        "timestamp": _now(),
    }
    events.append(ev_record)

    response = {
        "event_id": event_id,
        "match_id": match_id,
        "type": etype,
        "sequence": seq,
        "match_version": len(events),
        "signature": sig,
    }
    db_state.idempotency_events[event_id] = {"canonical": body_canonical, "response": response}
    return 201, response
