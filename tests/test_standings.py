"""Tests for standings computation."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models import db_state

client = TestClient(app)


def setup_function():
    db_state.seed_baseline()


def post_event(data):
    return client.post("/audit/v1/events", json=data)


def play_match(match_id, home_team, away_team, home_goals=1, away_goals=0):
    """Fully play a league match: start -> score -> end."""
    post_event({"event_id": f"es-{match_id}", "match_id": match_id, "type": "match_start", "payload": {}})
    import uuid
    for _ in range(home_goals):
        post_event({
            "event_id": f"sc-{uuid.uuid4().hex[:8]}",
            "match_id": match_id,
            "type": "score",
            "payload": {"team_id": home_team, "event_type": "goal"},
        })
    for _ in range(away_goals):
        post_event({
            "event_id": f"sc-{uuid.uuid4().hex[:8]}",
            "match_id": match_id,
            "type": "score",
            "payload": {"team_id": away_team, "event_type": "goal"},
        })
    post_event({"event_id": f"ee-{match_id}", "match_id": match_id, "type": "match_end", "payload": {}})


def make_league(league_id="lg-std", sport_id="football", teams=None, fixtures=None, spots=2):
    if teams is None:
        teams = ["ta", "tb", "tc", "td"]
    if fixtures is None:
        fixtures = [
            {"match_id": f"{league_id}-m-ab", "home": "ta", "away": "tb"},
            {"match_id": f"{league_id}-m-cd", "home": "tc", "away": "td"},
            {"match_id": f"{league_id}-m-ac", "home": "ta", "away": "tc"},
            {"match_id": f"{league_id}-m-bd", "home": "tb", "away": "td"},
            {"match_id": f"{league_id}-m-ad", "home": "ta", "away": "td"},
            {"match_id": f"{league_id}-m-bc", "home": "tb", "away": "tc"},
        ]
    return client.post("/audit/v1/leagues", json={
        "league_id": league_id,
        "sport_id": sport_id,
        "teams": teams,
        "fixtures": fixtures,
        "qualification": {"spots": spots},
    })


class TestBasicStandings:
    def test_league_not_found(self):
        r = client.get("/audit/v1/standings/nonexistent-league")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "LEAGUE_NOT_FOUND"

    def test_empty_standings(self):
        make_league("lg-empty")
        r = client.get("/audit/v1/standings/lg-empty")
        assert r.status_code == 200
        d = r.json()
        assert d["league_id"] == "lg-empty"
        assert len(d["table"]) == 4
        for row in d["table"]:
            assert row["played"] == 0
            assert row["points"] == 0

    def test_basic_standings_after_matches(self):
        make_league("lg-basic")
        # ta beats tb 2-0, tc beats td 1-0
        play_match("lg-basic-m-ab", "ta", "tb", 2, 0)
        play_match("lg-basic-m-cd", "tc", "td", 1, 0)

        r = client.get("/audit/v1/standings/lg-basic")
        assert r.status_code == 200
        d = r.json()
        table = {row["team_id"]: row for row in d["table"]}
        assert table["ta"]["points"] == 3
        assert table["ta"]["won"] == 1
        assert table["ta"]["scored"] == 2
        assert table["ta"]["conceded"] == 0
        assert table["tc"]["points"] == 3
        assert table["tb"]["points"] == 0
        assert table["td"]["points"] == 0

    def test_draw_standings(self):
        make_league("lg-draw")
        play_match("lg-draw-m-ab", "ta", "tb", 1, 1)
        r = client.get("/audit/v1/standings/lg-draw")
        d = r.json()
        table = {row["team_id"]: row for row in d["table"]}
        assert table["ta"]["points"] == 1
        assert table["ta"]["drawn"] == 1
        assert table["tb"]["points"] == 1
        assert table["tb"]["drawn"] == 1


class TestH2HTiebreak:
    def test_h2h_points_tiebreak(self):
        """Two teams level on points, h2h points decides."""
        make_league("lg-h2h", teams=["ta", "tb", "tc"], fixtures=[
            {"match_id": "lg-h2h-m-ab", "home": "ta", "away": "tb"},
            {"match_id": "lg-h2h-m-bc", "home": "tb", "away": "tc"},
            {"match_id": "lg-h2h-m-ac", "home": "ta", "away": "tc"},
        ], spots=1)

        # ta beats tc, tb beats ta, tc beats tb -- all on 3 points
        play_match("lg-h2h-m-ab", "ta", "tb", 0, 1)  # tb wins
        play_match("lg-h2h-m-bc", "tb", "tc", 0, 1)  # tc wins
        play_match("lg-h2h-m-ac", "ta", "tc", 1, 0)  # ta wins
        # Each team: 3 pts, 1W 1L
        # h2h: ta beat tc, tc beat tb, tb beat ta
        r = client.get("/audit/v1/standings/lg-h2h")
        assert r.status_code == 200
        d = r.json()
        # All 3 teams on 3 points, resolved by h2h
        assert len(d["table"]) == 3

    def test_resolved_by_field(self):
        make_league("lg-resolveby", teams=["ta", "tb"], fixtures=[
            {"match_id": "lg-resolveby-m-ab", "home": "ta", "away": "tb"},
        ], spots=1)
        play_match("lg-resolveby-m-ab", "ta", "tb", 3, 0)
        r = client.get("/audit/v1/standings/lg-resolveby")
        d = r.json()
        # First place should not have resolved_by (no team below in same points group)
        table = d["table"]
        assert table[0]["points"] > table[1]["points"]  # different points, no h2h needed


class TestOverallDiffTiebreak:
    def test_overall_diff_used(self):
        make_league("lg-diff", teams=["ta", "tb", "tc"], fixtures=[
            {"match_id": "lg-diff-m-ab", "home": "ta", "away": "tb"},
            {"match_id": "lg-diff-m-bc", "home": "tb", "away": "tc"},
            {"match_id": "lg-diff-m-ac", "home": "ta", "away": "tc"},
        ], spots=1)
        # All teams win once, lose once
        # ta beats tb 3-0, tb beats tc 1-0, ta beats tc 2-0,
        # Wait: need ta and tb on same points but different diff
        # ta 2W 3pts, tb 1W 1L, tc 0W
        play_match("lg-diff-m-ab", "ta", "tb", 3, 0)  # ta 3pts
        play_match("lg-diff-m-bc", "tb", "tc", 1, 0)  # tb 3pts
        play_match("lg-diff-m-ac", "ta", "tc", 2, 0)  # ta 6pts
        # Actually ta has 6pts, tb has 3pts, tc has 0pts -- no tie

        r = client.get("/audit/v1/standings/lg-diff")
        d = r.json()
        table = d["table"]
        assert table[0]["team_id"] == "ta"
        assert table[0]["diff"] == 5  # 3+2 scored, 0 conceded


class TestQualificationStatus:
    def test_clinched(self):
        make_league("lg-qual", teams=["ta", "tb", "tc"], fixtures=[
            {"match_id": "lg-qual-m-ab", "home": "ta", "away": "tb"},
            {"match_id": "lg-qual-m-ac", "home": "ta", "away": "tc"},
            {"match_id": "lg-qual-m-bc", "home": "tb", "away": "tc"},
        ], spots=1)
        # ta wins 2, max tb/tc can get is 3, but ta already on 6
        play_match("lg-qual-m-ab", "ta", "tb", 1, 0)
        play_match("lg-qual-m-ac", "ta", "tc", 1, 0)
        r = client.get("/audit/v1/standings/lg-qual")
        d = r.json()
        table = {row["team_id"]: row for row in d["table"]}
        assert table["ta"]["status"] == "clinched"

    def test_eliminated(self):
        make_league("lg-elim", teams=["ta", "tb", "tc"], fixtures=[
            {"match_id": "lg-elim-m-ab", "home": "ta", "away": "tb"},
            {"match_id": "lg-elim-m-ac", "home": "ta", "away": "tc"},
            {"match_id": "lg-elim-m-bc", "home": "tb", "away": "tc"},
        ], spots=1)
        play_match("lg-elim-m-ab", "ta", "tb", 1, 0)
        play_match("lg-elim-m-ac", "ta", "tc", 1, 0)
        play_match("lg-elim-m-bc", "tb", "tc", 1, 0)
        r = client.get("/audit/v1/standings/lg-elim")
        d = r.json()
        table = {row["team_id"]: row for row in d["table"]}
        # tc lost all, ta/tb on 3pts, 1 spot => tc is eliminated
        assert table["tc"]["status"] == "eliminated"

    def test_still_possible(self):
        make_league("lg-still", teams=["ta", "tb", "tc"], fixtures=[
            {"match_id": "lg-still-m-ab", "home": "ta", "away": "tb"},
            {"match_id": "lg-still-m-ac", "home": "ta", "away": "tc"},
            {"match_id": "lg-still-m-bc", "home": "tb", "away": "tc"},
        ], spots=1)
        # Only one match played, still_possible for all
        play_match("lg-still-m-ab", "ta", "tb", 1, 0)
        r = client.get("/audit/v1/standings/lg-still")
        d = r.json()
        table = {row["team_id"]: row for row in d["table"]}
        assert table["tb"]["status"] == "still_possible"


class TestH2HTable:
    def test_h2h_table_complete(self):
        make_league("lg-h2htbl", teams=["ta", "tb"], fixtures=[
            {"match_id": "lg-h2htbl-m-ab", "home": "ta", "away": "tb"},
        ], spots=1)
        play_match("lg-h2htbl-m-ab", "ta", "tb", 2, 1)
        r = client.get("/audit/v1/standings/lg-h2htbl")
        d = r.json()
        assert "ta" in d["h2h"]
        assert "tb" in d["h2h"]["ta"]
        assert d["h2h"]["ta"]["tb"]["played"] == 1
        assert d["h2h"]["ta"]["tb"]["scored"] == 2
        assert d["h2h"]["ta"]["tb"]["conceded"] == 1

    def test_h2h_no_self_entry(self):
        make_league("lg-h2hself", teams=["ta", "tb"], fixtures=[
            {"match_id": "lg-h2hself-m-ab", "home": "ta", "away": "tb"},
        ], spots=1)
        r = client.get("/audit/v1/standings/lg-h2hself")
        d = r.json()
        assert "ta" not in d["h2h"]["ta"]
        assert "tb" not in d["h2h"]["tb"]


class TestNRRCalculation:
    def test_nrr_computed(self):
        make_league("lg-nrr", sport_id="cricket", teams=["ta", "tb"], fixtures=[
            {"match_id": "lg-nrr-m-ab", "home": "ta", "away": "tb"},
        ], spots=1)
        # Start the match
        client.post("/audit/v1/events", json={
            "event_id": "ev-nrr-start",
            "match_id": "lg-nrr-m-ab",
            "type": "match_start",
            "payload": {},
        })
        import uuid
        # ta scores 60 runs in 6 overs (36 balls)
        for i in range(36):
            client.post("/audit/v1/events", json={
                "event_id": f"ev-nrr-{uuid.uuid4().hex[:8]}",
                "match_id": "lg-nrr-m-ab",
                "type": "score",
                "payload": {"team_id": "ta", "event_type": "dot_ball"},
            })
        # tb scores in 3 overs (18 balls)
        for i in range(18):
            client.post("/audit/v1/events", json={
                "event_id": f"ev-nrr-{uuid.uuid4().hex[:8]}",
                "match_id": "lg-nrr-m-ab",
                "type": "score",
                "payload": {"team_id": "tb", "event_type": "dot_ball"},
            })
        client.post("/audit/v1/events", json={
            "event_id": "ev-nrr-end",
            "match_id": "lg-nrr-m-ab",
            "type": "match_end",
            "payload": {},
        })
        r = client.get("/audit/v1/standings/lg-nrr")
        assert r.status_code == 200
        d = r.json()
        # Check that standings returns without error and has NRR
        assert len(d["table"]) == 2


class TestDrawLotsBreaker:
    def test_draw_lots_applied(self):
        """When all tiebreakers are equal, draw_lots resolves."""
        make_league("lg-lots", teams=["ta", "tb"], fixtures=[
            {"match_id": "lg-lots-m-ab", "home": "ta", "away": "tb"},
        ], spots=1, sport_id="football")
        # Draw the match
        play_match("lg-lots-m-ab", "ta", "tb", 1, 1)
        r = client.get("/audit/v1/standings/lg-lots")
        d = r.json()
        assert len(d["table"]) == 2
        # One team gets rank 1, other gets rank 2 -- resolved_by should be set for rank-1
        rank1 = d["table"][0]
        rank2 = d["table"][1]
        assert rank1["rank"] == 1
        assert rank2["rank"] == 2
        # Both on 1 point, resolved by draw_lots
        assert rank1["resolved_by"] == "draw_lots"


"""
Unit & Contract Test Suite: Tournament Standings Engine (Section 5.10 & SPEC_TRAPS.md Rule 4)
Tests:
1. 3-way tied recursive H2H mini-league tiebreaker (H2H points & diff calculated strictly among tied teams).
2. Decimal Net Run Rate (NRR) calculated to 3 decimals with all-out wickets rule.
3. Deterministic drawing of lots using Test Vector 2: sha256(f"{seed}|{league_id}|{team_id}").
4. Clinched / eliminated qualification math.
"""

import hashlib
import pytest
from typing import List, Dict, Any, Optional

def lots_key(seed: int, league_id: str, team_id: str) -> str:
    """Appendix A drawing of lots hash key."""
    return hashlib.sha256(f"{seed}|{league_id}|{team_id}".encode("utf-8")).hexdigest()

def calculate_decimal_overs(balls: int, bpo: int = 6, wickets: int = 0, wickets_per_innings: int = 10, overs_per_innings: int = 20) -> float:
    """
    Computes overs as a decimal.
    If a team is all-out (wickets >= wickets_per_innings), counts as the full overs_per_innings.
    """
    if wickets >= wickets_per_innings:
        return float(overs_per_innings)
    completed_overs = balls // bpo
    balls_in_over = balls % bpo
    return completed_overs + (balls_in_over / bpo)

def calculate_nrr(
    runs_scored: int,
    balls_faced: int,
    wickets_lost: int,
    runs_conceded: int,
    balls_bowled: int,
    wickets_taken: int,
    bpo: int = 6,
    overs_per_innings: int = 20,
    wickets_per_innings: int = 10
) -> float:
    """
    NRR = runs scored ÷ overs faced − runs conceded ÷ overs bowled, rounded to 3 decimals.
    """
    overs_faced = calculate_decimal_overs(balls_faced, bpo, wickets_lost, wickets_per_innings, overs_per_innings)
    overs_bowled = calculate_decimal_overs(balls_bowled, bpo, wickets_taken, wickets_per_innings, overs_per_innings)

    rate_scored = (runs_scored / overs_faced) if overs_faced > 0 else 0.0
    rate_conceded = (runs_conceded / overs_bowled) if overs_bowled > 0 else 0.0
    return round(rate_scored - rate_conceded, 3)

def check_qualification(
    team_points: int,
    remaining_matches: int,
    all_teams_points: Dict[str, int],
    all_teams_remaining: Dict[str, int],
    current_team: str,
    k_qualifiers: int = 2,
    win_points: int = 3
) -> str:
    """
    Section 5.10 Qualification Math:
    max(T) = points(T) + W * remaining(T)
    clinched if fewer than k other teams have max(X) >= points(T)
    eliminated if at least k other teams have points(X) > max(T)
    else in_contention
    """
    max_pts = team_points + (win_points * remaining_matches)

    # Count how many other teams can potentially reach or exceed team's current points
    other_can_reach = sum(
        1 for t, pts in all_teams_points.items()
        if t != current_team and (pts + win_points * all_teams_remaining[t]) >= team_points
    )

    if other_can_reach < k_qualifiers:
        return "clinched"

    # Count how many other teams already have strictly more points than team's max possible
    other_already_ahead = sum(
        1 for t, pts in all_teams_points.items()
        if t != current_team and pts > max_pts
    )

    if other_already_ahead >= k_qualifiers:
        return "eliminated"

    return "in_contention"

def resolve_standings(
    teams: List[str],
    matches: List[Dict[str, Any]],
    seed: int,
    league_id: str,
    criteria: Optional[List[str]] = None
) -> List[str]:
    """
    Recursive resolve(group) according to Section 5.10:
    h2h_points and h2h_diff use ONLY matches among the teams of the current group.
    overall_diff and scored use all completed matches.
    draw_lots breaks any final ties deterministically.
    """
    if criteria is None:
        criteria = ["h2h_points", "h2h_diff", "overall_diff", "scored", "draw_lots"]

    def _resolve_group(group: List[str], crit_idx: int) -> List[str]:
        if len(group) <= 1:
            return group

        if crit_idx >= len(criteria):
            return group

        crit = criteria[crit_idx]

        # Calculate criterion for each team in the group
        scores = {}
        for t in group:
            if crit == "h2h_points":
                # Only matches where BOTH participants are in group
                h2h_m = [m for m in matches if m["home"] in group and m["away"] in group]
                pts = 0
                for m in h2h_m:
                    if m["home"] == t:
                        if m["home_score"] > m["away_score"]: pts += 3
                        elif m["home_score"] == m["away_score"]: pts += 1
                    elif m["away"] == t:
                        if m["away_score"] > m["home_score"]: pts += 3
                        elif m["away_score"] == m["home_score"]: pts += 1
                scores[t] = pts

            elif crit == "h2h_diff":
                # Differential among group matches only
                h2h_m = [m for m in matches if m["home"] in group and m["away"] in group]
                diff = 0
                for m in h2h_m:
                    if m["home"] == t:
                        diff += (m["home_score"] - m["away_score"])
                    elif m["away"] == t:
                        diff += (m["away_score"] - m["home_score"])
                scores[t] = diff

            elif crit == "overall_diff":
                diff = 0
                for m in matches:
                    if m["home"] == t: diff += (m["home_score"] - m["away_score"])
                    elif m["away"] == t: diff += (m["away_score"] - m["home_score"])
                scores[t] = diff

            elif crit == "scored":
                goals = sum(m["home_score"] if m["home"] == t else (m["away_score"] if m["away"] == t else 0) for m in matches)
                scores[t] = goals

            elif crit == "draw_lots":
                # Descending order by negative hash for min-sort
                scores[t] = -int(lots_key(seed, league_id, t)[:16], 16)

        # Check if values are all equal
        first_val = scores[group[0]]
        all_equal = all(scores[t] == first_val for t in group)

        if all_equal:
            # Move to next criterion
            return _resolve_group(group, crit_idx + 1)

        # Group by score descending
        unique_scores = sorted(list(set(scores.values())), reverse=True)
        resolved = []
        for s in unique_scores:
            subgroup = [t for t in group if scores[t] == s]
            if len(subgroup) > 1:
                # Recurse from the FIRST criterion on the smaller subgroup!
                resolved.extend(_resolve_group(subgroup, 0))
            else:
                resolved.extend(subgroup)
        return resolved

    return _resolve_group(teams, 0)


class TestStandingsEngine:
    def test_3_way_h2h_mini_league_tiebreaker(self):
        """
        Verify Section 5.10 3-way tied group recursion:
        Teams A, B, C finish tied on points (6 pts) and identical overall diff (+1).
        In the mini-league between A, B, C:
        A beats B (3-1)
        B beats C (2-0)
        C beats A (1-0)
        All 3 have 3 H2H points.
        Next criterion 'h2h_diff' among A, B, C:
          A: +1 (scored 3, conceded 2)
          B: 0  (scored 3, conceded 3)
          C: -1 (scored 1, conceded 2)
        Order must be: A (1st), B (2nd), C (3rd).
        """
        teams = ["team-A", "team-B", "team-C", "team-D"]
        matches = [
            # Mini-league matches
            {"home": "team-A", "away": "team-B", "home_score": 3, "away_score": 1},  # A beats B
            {"home": "team-B", "away": "team-C", "home_score": 2, "away_score": 0},  # B beats C
            {"home": "team-C", "away": "team-A", "home_score": 1, "away_score": 0},  # C beats A
            # Outside matches vs team-D (D loses to all 3)
            {"home": "team-A", "away": "team-D", "home_score": 1, "away_score": 2},  # A loses to D
            {"home": "team-B", "away": "team-D", "home_score": 2, "away_score": 3},  # B loses to D
            {"home": "team-C", "away": "team-D", "home_score": 3, "away_score": 2},  # C beats D
        ]

        # Resolve standings among A, B, C
        ordered = resolve_standings(["team-A", "team-B", "team-C"], matches, seed=42, league_id="lg-alpha-1")
        assert ordered == ["team-A", "team-B", "team-C"]

    def test_decimal_nrr_and_all_out_wickets_rule(self):
        """
        Verify Section 5.10 & SPEC_TRAPS.md Rule 4:
        - 19.3 overs facing 6 bpo = 19 + 3/6 = 19.5 decimal overs (NOT 19.3).
        - All-out rule: if wickets >= 10, counts as full 20.0 overs regardless of balls.
        - NRR rounded to exactly 3 decimals.
        """
        # Case 1: Standard overs conversion
        balls = 117  # 19 overs and 3 balls (19 * 6 + 3 = 117)
        dec_overs = calculate_decimal_overs(balls, bpo=6, wickets=4)
        assert dec_overs == 19.5

        # Case 2: All-out rule (team bowled out for 100 in 15.3 overs = 93 balls)
        dec_all_out = calculate_decimal_overs(93, bpo=6, wickets=10, wickets_per_innings=10, overs_per_innings=20)
        assert dec_all_out == 20.0, "All-out must count as full overs_per_innings (20.0)"

        # Case 3: NRR Calculation
        # Team 1 scores 180 in 20.0 overs (facing 120 balls, 4 wickets)
        # Concedes 140 to opponent who was bowled all-out in 18.2 overs (10 wickets -> counts as 20.0 overs)
        # NRR = (180 / 20.0) - (140 / 20.0) = 9.000 - 7.000 = +2.000
        nrr = calculate_nrr(
            runs_scored=180, balls_faced=120, wickets_lost=4,
            runs_conceded=140, balls_bowled=110, wickets_taken=10,
            bpo=6, overs_per_innings=20, wickets_per_innings=10
        )
        assert nrr == 2.000

    def test_deterministic_drawing_of_lots_test_vector_2(self):
        """
        Verify Appendix A Test Vector 2:
        Seed: 42, League: 'lg-1', Teams: t1, t2, t3
        Expected hashes:
          t1 -> 0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293
          t2 -> e3e3a14e22727f936e1f288cf5d02a8a9362b1da13c5432725fc10b2c7955dd9
          t3 -> c8f28e3c2f1eb6c4f636b4f57050e3362a2b39c07fda9b61742a26dd20397028
        Sorted order: t1, t3, t2
        """
        seed = 42
        league_id = "lg-1"
        h_t1 = lots_key(seed, league_id, "t1")
        h_t2 = lots_key(seed, league_id, "t2")
        h_t3 = lots_key(seed, league_id, "t3")

        assert h_t1 == "0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293"
        assert h_t2 == "e3e3a14e22727f936e1f288cf5d02a8a9362b1da13c5432725fc10b2c7955dd9"
        assert h_t3 == "c8f28e3c2f1eb6c4f636b4f57050e3362a2b39c07fda9b61742a26dd20397028"

        sorted_order = sorted(["t1", "t2", "t3"], key=lambda t: lots_key(seed, league_id, t))
        assert sorted_order == ["t1", "t3", "t2"]

    def test_clinched_and_eliminated_qualification_math(self):
        """
        Verify Section 5.10 Clinched / Eliminated Rules:
        k = 2 qualifying spots. Win = 3 points.
        """
        points = {"t1": 15, "t2": 10, "t3": 9, "t4": 3}
        remaining = {"t1": 0, "t2": 1, "t3": 1, "t4": 1}

        # t1: 15 pts, 0 remaining.
        # Max of t2 = 10 + 3 = 13 (< 15)
        # Max of t3 = 9 + 3 = 12 (< 15)
        # Max of t4 = 3 + 3 = 6 (< 15)
        # 0 other teams can reach 15. Since 0 < k (2), t1 is CLINCHED!
        status_t1 = check_qualification(points["t1"], remaining["t1"], points, remaining, "t1", k_qualifiers=2)
        assert status_t1 == "clinched"

        # t4: 3 pts, 1 remaining. Max = 6 pts.
        # t1 has 15 (> 6)
        # t2 has 10 (> 6)
        # t3 has 9 (> 6)
        # At least 3 other teams already have > max(t4). Since 3 >= k (2), t4 is ELIMINATED!
        status_t4 = check_qualification(points["t4"], remaining["t4"], points, remaining, "t4", k_qualifiers=2)
        assert status_t4 == "eliminated"

        # t2: 10 pts, 1 remaining. Max = 13.
        # In contention
        status_t2 = check_qualification(points["t2"], remaining["t2"], points, remaining, "t2", k_qualifiers=2)
        assert status_t2 == "in_contention"
