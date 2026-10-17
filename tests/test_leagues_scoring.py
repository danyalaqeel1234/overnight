"""Tests for league registration and scoring engine."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models import db_state

client = TestClient(app)


def setup_function():
    db_state.seed_baseline()


# ---- Helpers ----

def make_league(
    league_id="lg-test",
    sport_id="football",
    teams=None,
    fixtures=None,
    spots=2,
):
    if teams is None:
        teams = ["team-a", "team-b", "team-c", "team-d"]
    if fixtures is None:
        fixtures = [
            {"match_id": "m-ab", "home": "team-a", "away": "team-b"},
            {"match_id": "m-cd", "home": "team-c", "away": "team-d"},
            {"match_id": "m-ac", "home": "team-a", "away": "team-c"},
            {"match_id": "m-bd", "home": "team-b", "away": "team-d"},
        ]
    return client.post("/audit/v1/leagues", json={
        "league_id": league_id,
        "sport_id": sport_id,
        "teams": teams,
        "fixtures": fixtures,
        "qualification": {"spots": spots},
    })


def post_event(data):
    return client.post("/audit/v1/events", json=data)


def init_match(match_id, sport_id="football", home="team-a", away="team-b", league_id=None):
    return post_event({
        "event_id": f"ev-init-{match_id}",
        "match_id": match_id,
        "type": "match_init",
        "payload": {
            "sport_id": sport_id,
            "home_team_id": home,
            "away_team_id": away,
            "league_id": league_id,
        },
    })


def start_match(match_id, ev_id=None):
    return post_event({
        "event_id": ev_id or f"ev-start-{match_id}",
        "match_id": match_id,
        "type": "match_start",
        "payload": {},
    })


def score(match_id, team_id, event_type="goal", ev_id=None):
    import uuid
    return post_event({
        "event_id": ev_id or f"ev-score-{uuid.uuid4().hex[:8]}",
        "match_id": match_id,
        "type": "score",
        "payload": {"team_id": team_id, "event_type": event_type},
    })


def end_match(match_id, ev_id=None):
    return post_event({
        "event_id": ev_id or f"ev-end-{match_id}",
        "match_id": match_id,
        "type": "match_end",
        "payload": {},
    })


def play_full_match(match_id, home_team, away_team, home_goals=1, away_goals=0):
    start_match(match_id)
    for i in range(home_goals):
        score(match_id, home_team, "goal")
    for i in range(away_goals):
        score(match_id, away_team, "goal")
    end_match(match_id)


# ---- create_league tests ----

class TestCreateLeague:
    def test_create_league_success(self):
        r = make_league()
        assert r.status_code == 201
        d = r.json()
        assert d["league_id"] == "lg-test"
        assert d["status"] == "created"
        assert d["team_count"] == 4
        assert d["fixture_count"] == 4

    def test_create_league_creates_matches(self):
        make_league()
        r = client.get("/audit/v1/score/m-ab")
        assert r.status_code == 200
        assert r.json()["status"] == "upcoming"

    def test_sport_not_found(self):
        r = make_league(sport_id="nonexistent-sport")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SPORT_NOT_FOUND"

    def test_league_exists(self):
        make_league()
        r = make_league()
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "LEAGUE_EXISTS"

    def test_match_exists_conflict(self):
        make_league()
        # Try to create another league with same fixture match_id
        r = client.post("/audit/v1/leagues", json={
            "league_id": "lg-other",
            "sport_id": "football",
            "teams": ["team-x", "team-y"],
            "fixtures": [{"match_id": "m-ab", "home": "team-x", "away": "team-y"}],
            "qualification": {"spots": 1},
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "MATCH_EXISTS"

    def test_duplicate_match_id_in_fixtures(self):
        r = client.post("/audit/v1/leagues", json={
            "league_id": "lg-dup",
            "sport_id": "football",
            "teams": ["team-x", "team-y"],
            "fixtures": [
                {"match_id": "m-dup", "home": "team-x", "away": "team-y"},
                {"match_id": "m-dup", "home": "team-y", "away": "team-x"},
            ],
            "qualification": {"spots": 1},
        })
        assert r.status_code == 409

    def test_duplicate_teams(self):
        r = client.post("/audit/v1/leagues", json={
            "league_id": "lg-dup-teams",
            "sport_id": "football",
            "teams": ["team-x", "team-x"],
            "fixtures": [],
            "qualification": {"spots": 1},
        })
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_fixture_team_not_in_league(self):
        r = client.post("/audit/v1/leagues", json={
            "league_id": "lg-badfix",
            "sport_id": "football",
            "teams": ["team-x", "team-y"],
            "fixtures": [{"match_id": "m-xy", "home": "team-x", "away": "team-z"}],
            "qualification": {"spots": 1},
        })
        assert r.status_code == 400

    def test_home_equals_away(self):
        r = client.post("/audit/v1/leagues", json={
            "league_id": "lg-same",
            "sport_id": "football",
            "teams": ["team-x", "team-y"],
            "fixtures": [{"match_id": "m-xx", "home": "team-x", "away": "team-x"}],
            "qualification": {"spots": 1},
        })
        assert r.status_code == 400


# ---- add_event / match state machine tests ----

class TestMatchInit:
    def test_match_init_success(self):
        r = init_match("m-new")
        assert r.status_code == 201
        d = r.json()
        assert d["type"] == "match_init"
        assert d["sequence"] == 1

    def test_match_init_sport_not_found(self):
        r = post_event({
            "event_id": "ev-init-bad",
            "match_id": "m-badsport",
            "type": "match_init",
            "payload": {"sport_id": "bad", "home_team_id": "a", "away_team_id": "b"},
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SPORT_NOT_FOUND"

    def test_match_init_duplicate_match(self):
        init_match("m-dup2")
        # Use a different event_id to avoid idempotency return, but same match_id
        r = post_event({
            "event_id": "ev-init-m-dup2-second",
            "match_id": "m-dup2",
            "type": "match_init",
            "payload": {
                "sport_id": "football",
                "home_team_id": "team-a",
                "away_team_id": "team-b",
            },
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "MATCH_EXISTS"

    def test_match_not_found(self):
        r = start_match("m-nonexistent")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "MATCH_NOT_FOUND"


class TestMatchStateMachine:
    def test_full_match_lifecycle(self):
        init_match("m-full")
        r = start_match("m-full")
        assert r.status_code == 201
        r = score("m-full", "team-a", "goal")
        assert r.status_code == 201
        r = end_match("m-full")
        assert r.status_code == 201

        state = client.get("/audit/v1/score/m-full").json()
        assert state["status"] == "completed"
        assert state["outcome"] == "home_win"
        assert state["winner_team_id"] == "team-a"

    def test_start_already_in_progress(self):
        init_match("m-state1")
        start_match("m-state1")
        r = start_match("m-state1", ev_id="ev-start2-m-state1")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "ILLEGAL_TRANSITION"

    def test_end_upcoming_match(self):
        init_match("m-state2")
        r = end_match("m-state2")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "ILLEGAL_TRANSITION"

    def test_score_upcoming_match(self):
        init_match("m-state3")
        r = score("m-state3", "team-a", "goal")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "MATCH_NOT_IN_PROGRESS"

    def test_score_completed_match(self):
        init_match("m-state4")
        start_match("m-state4")
        end_match("m-state4")
        r = score("m-state4", "team-a", "goal")
        assert r.status_code == 409

    def test_draw_football(self):
        init_match("m-draw")
        start_match("m-draw")
        end_match("m-draw")
        state = client.get("/audit/v1/score/m-draw").json()
        assert state["outcome"] == "draw"

    def test_away_win(self):
        init_match("m-away")
        start_match("m-away")
        score("m-away", "team-b", "goal")
        score("m-away", "team-b", "goal")
        end_match("m-away")
        state = client.get("/audit/v1/score/m-away").json()
        assert state["outcome"] == "away_win"
        assert state["winner_team_id"] == "team-b"


class TestScoreValidation:
    def test_unknown_event_type(self):
        init_match("m-unk")
        start_match("m-unk")
        r = post_event({
            "event_id": "ev-unk",
            "match_id": "m-unk",
            "type": "score",
            "payload": {"team_id": "team-a", "event_type": "nonexistent"},
        })
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "UNKNOWN_EVENT_TYPE"

    def test_wrong_team_id(self):
        init_match("m-wrongteam")
        start_match("m-wrongteam")
        r = post_event({
            "event_id": "ev-wrongteam",
            "match_id": "m-wrongteam",
            "type": "score",
            "payload": {"team_id": "team-unknown", "event_type": "goal"},
        })
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


class TestDisciplineEvent:
    def test_discipline_in_progress(self):
        init_match("m-disc")
        start_match("m-disc")
        r = post_event({
            "event_id": "ev-disc",
            "match_id": "m-disc",
            "type": "discipline",
            "payload": {"team_id": "team-a", "points": -1},
        })
        assert r.status_code == 201
        state = client.get("/audit/v1/score/m-disc").json()
        assert state["home"]["fair_play"] == -1

    def test_discipline_not_in_progress(self):
        init_match("m-disc2")
        r = post_event({
            "event_id": "ev-disc2",
            "match_id": "m-disc2",
            "type": "discipline",
            "payload": {"team_id": "team-a", "points": -1},
        })
        assert r.status_code == 409


class TestTiebreakEvent:
    def test_tiebreak_winner(self):
        # esports doesn't allow draw
        init_match("m-tb", sport_id="esports", home="team-a", away="team-b")
        start_match("m-tb")
        r = post_event({
            "event_id": "ev-tb",
            "match_id": "m-tb",
            "type": "tiebreak_winner",
            "payload": {"team_id": "team-a"},
        })
        assert r.status_code == 201
        end_match("m-tb")
        state = client.get("/audit/v1/score/m-tb").json()
        assert state["tiebreak_winner_team_id"] == "team-a"
        assert state["outcome"] == "home_win"

    def test_no_draw_allowed_without_tiebreak(self):
        init_match("m-nodraw", sport_id="esports")
        start_match("m-nodraw")
        r = end_match("m-nodraw")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "TIE_NOT_ALLOWED"


class TestCompensation:
    def test_compensate_score(self):
        init_match("m-comp")
        start_match("m-comp")
        r = score("m-comp", "team-a", "goal", ev_id="ev-score-comp1")
        assert r.status_code == 201
        state = client.get("/audit/v1/score/m-comp").json()
        assert state["home"]["score"] == 1

        # Compensate the goal
        r = post_event({
            "event_id": "ev-comp-1",
            "match_id": "m-comp",
            "type": "compensation",
            "payload": {"compensates": "ev-score-comp1"},
        })
        assert r.status_code == 201
        state = client.get("/audit/v1/score/m-comp").json()
        assert state["home"]["score"] == 0

    def test_compensate_nonexistent_event(self):
        init_match("m-comp2")
        start_match("m-comp2")
        r = post_event({
            "event_id": "ev-comp-bad",
            "match_id": "m-comp2",
            "type": "compensation",
            "payload": {"compensates": "ev-nonexistent"},
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "EVENT_NOT_FOUND"

    def test_double_compensate(self):
        init_match("m-comp3")
        start_match("m-comp3")
        score("m-comp3", "team-a", "goal", ev_id="ev-score-comp3")
        post_event({
            "event_id": "ev-comp3-1",
            "match_id": "m-comp3",
            "type": "compensation",
            "payload": {"compensates": "ev-score-comp3"},
        })
        r = post_event({
            "event_id": "ev-comp3-2",
            "match_id": "m-comp3",
            "type": "compensation",
            "payload": {"compensates": "ev-score-comp3"},
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "INVALID_COMPENSATION"

    def test_cannot_compensate_match_start(self):
        init_match("m-comp4")
        r_start = start_match("m-comp4", ev_id="ev-start-comp4")
        r = post_event({
            "event_id": "ev-comp4-bad",
            "match_id": "m-comp4",
            "type": "compensation",
            "payload": {"compensates": "ev-start-comp4"},
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "INVALID_COMPENSATION"

    def test_compensation_flag_in_events_list(self):
        init_match("m-comp5")
        start_match("m-comp5")
        score("m-comp5", "team-a", "goal", ev_id="ev-score-comp5")
        post_event({
            "event_id": "ev-comp5-1",
            "match_id": "m-comp5",
            "type": "compensation",
            "payload": {"compensates": "ev-score-comp5"},
        })
        state = client.get("/audit/v1/score/m-comp5").json()
        events = {ev["event_id"]: ev for ev in state["events"]}
        assert events["ev-score-comp5"]["compensated"] is True
        assert events["ev-score-comp5"]["compensated_by"] == "ev-comp5-1"
        assert events["ev-comp5-1"]["compensated"] is False


class TestIdempotency:
    def test_same_event_id_same_body(self):
        data = {
            "event_id": "ev-idem-1",
            "match_id": "m-idem",
            "type": "match_init",
            "payload": {
                "sport_id": "football",
                "home_team_id": "team-a",
                "away_team_id": "team-b",
            },
        }
        r1 = post_event(data)
        assert r1.status_code == 201
        r2 = post_event(data)
        assert r2.status_code == 200
        assert r1.json() == r2.json()

    def test_same_event_id_different_body(self):
        data1 = {
            "event_id": "ev-idem-2",
            "match_id": "m-idem2",
            "type": "match_init",
            "payload": {
                "sport_id": "football",
                "home_team_id": "team-a",
                "away_team_id": "team-b",
            },
        }
        post_event(data1)
        data2 = {**data1, "match_id": "m-idem2-other"}
        r2 = post_event(data2)
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "DUPLICATE_EVENT_ID"


class TestCricketScoring:
    def test_cricket_innings_model(self):
        init_match("m-cricket", sport_id="cricket", home="team-a", away="team-b")
        start_match("m-cricket")
        # Score runs
        r = score("m-cricket", "team-a", "dot_ball")
        assert r.status_code == 201
        r = score("m-cricket", "team-a", "single")
        assert r.status_code == 201
        state = client.get("/audit/v1/score/m-cricket").json()
        assert state["home"]["balls"] == 2  # two legal balls
        assert state["home"]["score"] == 1  # 0 + 1

    def test_cricket_wicket(self):
        init_match("m-crick2", sport_id="cricket", home="team-a", away="team-b")
        start_match("m-crick2")
        r = score("m-crick2", "team-a", "wicket")
        assert r.status_code == 201
        state = client.get("/audit/v1/score/m-crick2").json()
        assert state["home"]["wickets"] == 1

    def test_cricket_overs_display(self):
        init_match("m-crick3", sport_id="cricket")
        start_match("m-crick3")
        # 7 legal balls = 1.1 overs
        for _ in range(7):
            score("m-crick3", "team-a", "dot_ball")
        state = client.get("/audit/v1/score/m-crick3").json()
        assert state["home"]["overs"] == "1.1"


class TestEsportsRoundModel:
    def test_esports_round_scoring(self):
        init_match("m-esports", sport_id="esports")
        start_match("m-esports")
        r = score("m-esports", "team-a", "round_win")
        assert r.status_code == 201
        state = client.get("/audit/v1/score/m-esports").json()
        assert state["home"]["score"] == 1

    def test_esports_series_decided(self):
        # best_of = 3, need 2 wins
        init_match("m-esports2", sport_id="esports")
        start_match("m-esports2")
        score("m-esports2", "team-a", "round_win")
        score("m-esports2", "team-a", "round_win")
        # third round_win should fail
        r = score("m-esports2", "team-a", "round_win")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "SERIES_ALREADY_DECIDED"


class TestGetScore:
    def test_get_score_not_found(self):
        r = client.get("/audit/v1/score/nonexistent-match")
        assert r.status_code == 404

    def test_get_score_upcoming(self):
        init_match("m-up")
        r = client.get("/audit/v1/score/m-up")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "upcoming"
        assert d["outcome"] == "pending"

    def test_get_score_has_signature(self):
        init_match("m-sig")
        start_match("m-sig")
        state = client.get("/audit/v1/score/m-sig").json()
        events = state["events"]
        for ev in events:
            assert "signature" in ev
            assert ev["signature"]
