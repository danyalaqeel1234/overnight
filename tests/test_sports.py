"""Tests for POST /audit/v1/sports."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def setup_function():
    client.post("/audit/v1/reset")


def test_create_event_sport():
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "kabaddi",
            "name": "Kabaddi",
            "scoring_model": "event",
            "periods": {"count": 2, "duration_minutes": 20},
            "scoring_events": {
                "raid_point": {"points": 1},
                "tackle_point": {"points": 1},
            },
            "draw_allowed": False,
            "overtime": {"policy": "golden_score", "duration_minutes": 5},
            "roster": {"min_squad_size": 7, "max_squad_size": 12, "required_positions": {}},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sport_id"] == "kabaddi"
    assert body["status"] == "created"
    assert body["config"]["scoring_model"] == "event"


def test_create_innings_sport():
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "cricket-test",
            "name": "Test Cricket",
            "scoring_model": "innings",
            "periods": {
                "innings_per_team": 2,
                "overs_per_innings": 90,
                "balls_per_over": 6,
                "wickets_per_innings": 10,
            },
            "scoring_events": {
                "run": {"runs": 1, "legal_ball": True, "wicket": False},
                "out": {"runs": 0, "legal_ball": True, "wicket": True},
            },
            "draw_allowed": True,
            "overtime": {"policy": "none"},
            "roster": {"min_squad_size": 11, "max_squad_size": 15, "required_positions": {}},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["sport_id"] == "cricket-test"


def test_create_round_sport():
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "fighting",
            "name": "Fighting Game",
            "scoring_model": "round",
            "periods": {"best_of": 5},
            "scoring_events": {"round_win": {"rounds": 1}},
            "draw_allowed": False,
            "overtime": {"policy": "none"},
            "roster": {"min_squad_size": 1, "max_squad_size": 1, "required_positions": {}},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["config"]["periods"]["best_of"] == 5


def test_duplicate_sport_409():
    client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "my-sport",
            "name": "My Sport",
            "scoring_model": "event",
            "periods": {"count": 1, "duration_minutes": 10},
            "scoring_events": {"score": {"points": 1}},
            "draw_allowed": False,
            "overtime": {"policy": "none"},
            "roster": {"min_squad_size": 1, "max_squad_size": 5, "required_positions": {}},
        },
    )
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "my-sport",
            "name": "My Sport Again",
            "scoring_model": "event",
            "periods": {"count": 1, "duration_minutes": 10},
            "scoring_events": {"score": {"points": 1}},
            "draw_allowed": False,
            "overtime": {"policy": "none"},
            "roster": {"min_squad_size": 1, "max_squad_size": 5, "required_positions": {}},
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SPORT_EXISTS"


def test_invalid_sport_id_400():
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "INVALID_ID",
            "name": "Bad",
            "scoring_model": "event",
            "periods": {"count": 1, "duration_minutes": 10},
            "scoring_events": {"score": {"points": 1}},
            "draw_allowed": False,
            "overtime": {"policy": "none"},
            "roster": {"min_squad_size": 1, "max_squad_size": 5, "required_positions": {}},
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "sport_id" in resp.json()["error"]["details"]["fields"]


def test_invalid_best_of_even_400():
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "bad-round",
            "name": "Bad Round",
            "scoring_model": "round",
            "periods": {"best_of": 4},  # even - invalid
            "scoring_events": {"win": {"rounds": 1}},
            "draw_allowed": False,
            "overtime": {"policy": "none"},
            "roster": {"min_squad_size": 1, "max_squad_size": 5, "required_positions": {}},
        },
    )
    assert resp.status_code == 400
    assert "periods.best_of" in resp.json()["error"]["details"]["fields"]


def test_tie_break_draw_lots_appended():
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "tbo-sport",
            "name": "TBO Sport",
            "scoring_model": "event",
            "periods": {"count": 1, "duration_minutes": 10},
            "scoring_events": {"score": {"points": 1}},
            "draw_allowed": False,
            "overtime": {"policy": "none"},
            "tie_break_order": ["h2h_points", "scored"],
            "roster": {"min_squad_size": 1, "max_squad_size": 5, "required_positions": {}},
        },
    )
    assert resp.status_code == 201
    tbo = resp.json()["config"]["tie_break_order"]
    assert tbo[-1] == "draw_lots"
    assert "h2h_points" in tbo
    assert "scored" in tbo


def test_baseline_sports_not_overwritten():
    """Baseline sports should exist after reset."""
    client.post("/audit/v1/reset")
    resp = client.post(
        "/audit/v1/sports",
        json={
            "sport_id": "football",  # baseline sport
            "name": "Football",
            "scoring_model": "event",
            "periods": {"count": 2, "duration_minutes": 45},
            "scoring_events": {"goal": {"points": 1}},
            "draw_allowed": True,
            "overtime": {"policy": "none"},
            "roster": {"min_squad_size": 11, "max_squad_size": 25, "required_positions": {}},
        },
    )
    assert resp.status_code == 409
