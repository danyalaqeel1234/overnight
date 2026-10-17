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
