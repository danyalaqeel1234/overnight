"""Standings computation (recomputed from scratch on every call)."""
from __future__ import annotations
import hashlib
from app.core.errors import AppException
from app.domain.models import db_state
from app.domain.scoring import project_match


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _compute_standings(league_id: str) -> dict:
    if league_id not in db_state.leagues:
        raise AppException("LEAGUE_NOT_FOUND", f"League '{league_id}' not found.", {}, 404)

    league = db_state.leagues[league_id]
    sport = db_state.sports[league["sport_id"]]
    model = sport["scoring_model"]
    bpo = sport["periods"].get("balls_per_over", 6) if model == "innings" else None
    wpi = sport["periods"].get("wickets_per_innings", 10) if model == "innings" else None
    opi = sport["periods"].get("overs_per_innings", 20) if model == "innings" else None

    points_cfg = league["points"]
    W = points_cfg.get("win", 3)
    D = points_cfg.get("draw", 1)
    L = points_cfg.get("loss", 0)
    tbo = league["tie_break_order"]
    lots_seed = league["lots_seed"]
    qual_spots = league["qualification"]["spots"]
    teams = league["teams"]

    # Project all matches
    projected: dict[str, dict] = {}
    for fix in league["fixtures"]:
        mid = fix["match_id"]
        state = project_match(mid)
        if state:
            projected[mid] = state

    # Build per-team stats
    stats: dict[str, dict] = {}
    for t in teams:
        stats[t] = {
            "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "scored": 0, "conceded": 0,
            "points": 0, "fair_play": 0,
            # For NRR
            "runs_scored": 0, "overs_faced": 0.0,
            "runs_conceded": 0, "overs_bowled": 0.0,
            # For round model diff
            "rounds_won": 0, "rounds_lost": 0,
        }

    # H2H table: h2h[a][b] = {played, points, scored, conceded}
    h2h: dict[str, dict[str, dict]] = {
        t1: {t2: {"played": 0, "points": 0, "scored": 0, "conceded": 0}
             for t2 in teams if t2 != t1}
        for t1 in teams
    }

    # Count remaining fixtures per team
    remaining: dict[str, int] = {t: 0 for t in teams}
    for fix in league["fixtures"]:
        mid = fix["match_id"]
        home_t = fix["home"]
        away_t = fix["away"]
        state = projected.get(mid)
        is_counted = state and state["status"] == "completed" and state["outcome"] != "undecided"
        if not is_counted:
            remaining[home_t] = remaining.get(home_t, 0) + 1
            remaining[away_t] = remaining.get(away_t, 0) + 1

    for fix in league["fixtures"]:
        mid = fix["match_id"]
        state = projected.get(mid)
        if not state or state["status"] != "completed" or state["outcome"] == "undecided":
            continue

        home_t = state["home"]["team_id"]
        away_t = state["away"]["team_id"]
        home_score = state["home"]["score"]
        away_score = state["away"]["score"]
        outcome = state["outcome"]
        home_fair = state["home"]["fair_play"]
        away_fair = state["away"]["fair_play"]

        # Played
        if home_t in stats:
            stats[home_t]["played"] += 1
            stats[home_t]["fair_play"] += home_fair
        if away_t in stats:
            stats[away_t]["played"] += 1
            stats[away_t]["fair_play"] += away_fair

        # Points + won/drawn/lost
        if outcome == "draw":
            if home_t in stats:
                stats[home_t]["drawn"] += 1
                stats[home_t]["points"] += D
            if away_t in stats:
                stats[away_t]["drawn"] += 1
                stats[away_t]["points"] += D
        elif outcome == "home_win":
            if home_t in stats:
                stats[home_t]["won"] += 1
                stats[home_t]["points"] += W
            if away_t in stats:
                stats[away_t]["lost"] += 1
                stats[away_t]["points"] += L
        elif outcome == "away_win":
            if away_t in stats:
                stats[away_t]["won"] += 1
                stats[away_t]["points"] += W
            if home_t in stats:
                stats[home_t]["lost"] += 1
                stats[home_t]["points"] += L

        # Scored/conceded + model-specific
        if model == "event":
            if home_t in stats:
                stats[home_t]["scored"] += home_score
                stats[home_t]["conceded"] += away_score
            if away_t in stats:
                stats[away_t]["scored"] += away_score
                stats[away_t]["conceded"] += home_score
        elif model == "round":
            if home_t in stats:
                stats[home_t]["scored"] += home_score
                stats[home_t]["conceded"] += away_score
                stats[home_t]["rounds_won"] += home_score
                stats[home_t]["rounds_lost"] += away_score
            if away_t in stats:
                stats[away_t]["scored"] += away_score
                stats[away_t]["conceded"] += home_score
                stats[away_t]["rounds_won"] += away_score
                stats[away_t]["rounds_lost"] += home_score
        elif model == "innings":
            home_balls = state["home"]["balls"] or 0
            away_balls = state["away"]["balls"] or 0
            home_wkts = state["home"]["wickets"] or 0
            away_wkts = state["away"]["wickets"] or 0
            home_runs = home_score
            away_runs = away_score

            # If all-out, count as full overs
            home_overs_dec = opi if home_wkts >= wpi else home_balls / bpo
            away_overs_dec = opi if away_wkts >= wpi else away_balls / bpo

            if home_t in stats:
                stats[home_t]["scored"] += home_runs
                stats[home_t]["conceded"] += away_runs
                stats[home_t]["runs_scored"] += home_runs
                stats[home_t]["overs_faced"] += home_overs_dec
                stats[home_t]["runs_conceded"] += away_runs
                stats[home_t]["overs_bowled"] += away_overs_dec
            if away_t in stats:
                stats[away_t]["scored"] += away_runs
                stats[away_t]["conceded"] += home_runs
                stats[away_t]["runs_scored"] += away_runs
                stats[away_t]["overs_faced"] += away_overs_dec
                stats[away_t]["runs_conceded"] += home_runs
                stats[away_t]["overs_bowled"] += home_overs_dec

        # H2H
        if home_t in h2h and away_t in h2h[home_t]:
            h2h[home_t][away_t]["played"] += 1
            h2h[home_t][away_t]["scored"] += home_score
            h2h[home_t][away_t]["conceded"] += away_score
            if outcome == "home_win":
                h2h[home_t][away_t]["points"] += W
            elif outcome == "draw":
                h2h[home_t][away_t]["points"] += D
        if away_t in h2h and home_t in h2h[away_t]:
            h2h[away_t][home_t]["played"] += 1
            h2h[away_t][home_t]["scored"] += away_score
            h2h[away_t][home_t]["conceded"] += home_score
            if outcome == "away_win":
                h2h[away_t][home_t]["points"] += W
            elif outcome == "draw":
                h2h[away_t][home_t]["points"] += D

    # Compute diff per team
    def team_diff(t: str) -> float:
        if model == "event":
            return stats[t]["scored"] - stats[t]["conceded"]
        elif model == "round":
            return stats[t]["rounds_won"] - stats[t]["rounds_lost"]
        else:  # innings/NRR
            of = stats[t]["overs_faced"]
            ob = stats[t]["overs_bowled"]
            if of == 0 or ob == 0:
                return 0.0
            nrr = (stats[t]["runs_scored"] / of) - (stats[t]["runs_conceded"] / ob)
            return round(nrr, 3)

    # ---- Tie-break resolution ----

    def get_criterion(team: str, criterion: str, group: list[str], group_context: dict) -> float:
        """Compute criterion value for team within the current group."""
        if criterion == "h2h_points":
            return group_context["h2h_pts"].get(team, 0)
        elif criterion == "h2h_diff":
            return group_context["h2h_dif"].get(team, 0.0)
        elif criterion == "overall_diff":
            return team_diff(team)
        elif criterion == "scored":
            return stats[team]["scored"]
        elif criterion == "fair_play":
            return stats[team]["fair_play"]
        elif criterion == "draw_lots":
            return _sha256_hex(f"{lots_seed}|{league_id}|{team}")
        return 0.0

    def build_h2h_context(group: list[str]) -> dict:
        """Build h2h points and diff for teams within a group (only matches among group members)."""
        h2h_pts: dict[str, int] = {t: 0 for t in group}
        h2h_runs_scored: dict[str, int] = {t: 0 for t in group}
        h2h_runs_conceded: dict[str, int] = {t: 0 for t in group}
        h2h_overs_faced: dict[str, float] = {t: 0.0 for t in group}
        h2h_overs_bowled: dict[str, float] = {t: 0.0 for t in group}
        h2h_scored: dict[str, int] = {t: 0 for t in group}
        h2h_conceded: dict[str, int] = {t: 0 for t in group}
        h2h_rounds_won: dict[str, int] = {t: 0 for t in group}
        h2h_rounds_lost: dict[str, int] = {t: 0 for t in group}
        group_set = set(group)

        for fix in league["fixtures"]:
            mid = fix["match_id"]
            state = projected.get(mid)
            if not state or state["status"] != "completed" or state["outcome"] == "undecided":
                continue
            ht = state["home"]["team_id"]
            at = state["away"]["team_id"]
            if ht not in group_set or at not in group_set:
                continue
            outcome = state["outcome"]
            hs = state["home"]["score"]
            as_ = state["away"]["score"]

            if outcome == "home_win":
                h2h_pts[ht] += W
            elif outcome == "away_win":
                h2h_pts[at] += W
            elif outcome == "draw":
                h2h_pts[ht] += D
                h2h_pts[at] += D

            if model == "event":
                h2h_scored[ht] += hs; h2h_conceded[ht] += as_
                h2h_scored[at] += as_; h2h_conceded[at] += hs
            elif model == "round":
                h2h_rounds_won[ht] += hs; h2h_rounds_lost[ht] += as_
                h2h_rounds_won[at] += as_; h2h_rounds_lost[at] += hs
                h2h_scored[ht] += hs; h2h_conceded[ht] += as_
                h2h_scored[at] += as_; h2h_conceded[at] += hs
            elif model == "innings":
                hb = state["home"]["balls"] or 0
                ab = state["away"]["balls"] or 0
                hw = state["home"]["wickets"] or 0
                aw = state["away"]["wickets"] or 0
                h_ov = opi if hw >= wpi else hb / bpo
                a_ov = opi if aw >= wpi else ab / bpo
                h2h_runs_scored[ht] += hs; h2h_overs_faced[ht] += h_ov
                h2h_runs_conceded[ht] += as_; h2h_overs_bowled[ht] += a_ov
                h2h_runs_scored[at] += as_; h2h_overs_faced[at] += a_ov
                h2h_runs_conceded[at] += hs; h2h_overs_bowled[at] += h_ov
                h2h_scored[ht] += hs; h2h_conceded[ht] += as_
                h2h_scored[at] += as_; h2h_conceded[at] += hs

        h2h_dif = {}
        for t in group:
            if model == "event":
                h2h_dif[t] = h2h_scored[t] - h2h_conceded[t]
            elif model == "round":
                h2h_dif[t] = h2h_rounds_won[t] - h2h_rounds_lost[t]
            elif model == "innings":
                of_ = h2h_overs_faced[t]
                ob_ = h2h_overs_bowled[t]
                if of_ == 0 or ob_ == 0:
                    h2h_dif[t] = 0.0
                else:
                    h2h_dif[t] = round((h2h_runs_scored[t] / of_) - (h2h_runs_conceded[t] / ob_), 3)
            else:
                h2h_dif[t] = 0.0

        return {"h2h_pts": h2h_pts, "h2h_dif": h2h_dif}

    def resolve_group(group: list[str], ctx: dict) -> list[tuple[str, str | None]]:
        """
        Returns list of (team_id, resolved_by) in order (best first).
        resolved_by = criterion that separated this team from the next team below it in the same group.
        """
        if len(group) <= 1:
            return [(t, None) for t in group]

        # Build h2h context for current group
        h2h_ctx = build_h2h_context(group)
        ctx = {**ctx, **h2h_ctx}

        for criterion in tbo + ["draw_lots"]:
            values = {}
            for t in group:
                v = get_criterion(t, criterion, group, ctx)
                values[t] = v

            # Check if all equal (for draw_lots, SHA256 values are always distinct)
            unique_vals = set(values.values())
            if len(unique_vals) == 1:
                continue  # all equal, try next

            # Sort groups by value (best first)
            # For draw_lots: ascending SHA256 = smaller is better
            if criterion == "draw_lots":
                sorted_vals = sorted(unique_vals)  # ascending = smaller first = best first
            else:
                sorted_vals = sorted(unique_vals, reverse=True)  # descending = larger first = best

            subgroups = [[t for t in group if values[t] == v] for v in sorted_vals]

            result = []
            for i, sg in enumerate(subgroups):
                sub_result = resolve_group(sg, {**ctx, **build_h2h_context(sg)})
                has_next_sg = i < len(subgroups) - 1
                for j, (team, rb) in enumerate(sub_result):
                    is_last_in_sg = j == len(sub_result) - 1
                    if is_last_in_sg and has_next_sg:
                        result.append((team, criterion))
                    else:
                        result.append((team, rb))
            return result

        return [(t, None) for t in group]

    # Sort teams by points descending, then resolve tied groups
    by_points: dict[int, list[str]] = {}
    for t in teams:
        pts = stats[t]["points"]
        by_points.setdefault(pts, []).append(t)

    table_order: list[tuple[str, str | None]] = []
    for pts in sorted(by_points.keys(), reverse=True):
        group = by_points[pts]
        if len(group) == 1:
            table_order.append((group[0], None))
        else:
            resolved = resolve_group(group, {})
            table_order.extend(resolved)

    # Qualification status
    def qual_status(t: str) -> str:
        pts_t = stats[t]["points"]
        max_t = pts_t + W * remaining[t]
        # clinched: fewer than k other teams have max(X) >= points(T)
        count_can_reach = sum(1 for x in teams if x != t and
                              (stats[x]["points"] + W * remaining[x]) >= pts_t)
        if count_can_reach < qual_spots:
            return "clinched"
        # eliminated: at least k other teams have points(X) > max(T)
        count_ahead = sum(1 for x in teams if x != t and stats[x]["points"] > max_t)
        if count_ahead >= qual_spots:
            return "eliminated"
        return "still_possible"

    table = []
    for rank, (team, resolved_by) in enumerate(table_order, 1):
        d = team_diff(team)
        table.append({
            "rank": rank,
            "team_id": team,
            "played": stats[team]["played"],
            "won": stats[team]["won"],
            "drawn": stats[team]["drawn"],
            "lost": stats[team]["lost"],
            "scored": stats[team]["scored"],
            "conceded": stats[team]["conceded"],
            "diff": d,
            "points": stats[team]["points"],
            "fair_play": stats[team]["fair_play"],
            "status": qual_status(team),
            "resolved_by": resolved_by,
        })

    return {
        "league_id": league_id,
        "sport_id": league["sport_id"],
        "qualification_spots": qual_spots,
        "table": table,
        "h2h": {
            t1: {t2: h2h[t1][t2] for t2 in teams if t2 != t1}
            for t1 in teams
        },
    }
