"""Tests for roster management."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models import db_state

client = TestClient(app)


def setup_function():
    db_state.seed_baseline()


BASE_LEAGUE = {
    "league_id": "rl-test",
    "tenant_id": "tenant-alpha",
    "sport_id": "football",
    "transfer_window": {"open": "2026-01-01", "close": "2026-12-31"},
    "max_squad_size": 5,
    "required_positions": {"goalkeeper": 1},
}

SQUAD_A = {"squad_id": "sq-a", "club_id": "club-alpha-1", "tenant_id": "tenant-alpha", "name": "Squad A"}
SQUAD_B = {"squad_id": "sq-b", "club_id": "club-alpha-2", "tenant_id": "tenant-alpha", "name": "Squad B"}

PLAYER_1 = {"player_id": "pl-1", "name": "Alice", "position": "goalkeeper", "squad_id": "sq-a"}
PLAYER_2 = {"player_id": "pl-2", "name": "Bob", "position": "midfielder", "squad_id": "sq-a"}
PLAYER_3 = {"player_id": "pl-3", "name": "Charlie", "position": "forward", "squad_id": "sq-b"}


def setup_roster(league=None, squads=None, players=None):
    return client.post("/audit/v1/roster/setup", json={
        "league": league or BASE_LEAGUE,
        "squads": squads or [SQUAD_A, SQUAD_B],
        "players": players or [PLAYER_1, PLAYER_2, PLAYER_3],
    })


def transfer(data):
    return client.post("/audit/v1/roster/transfer", json=data)


class TestSetupRoster:
    def test_setup_success(self):
        r = setup_roster()
        assert r.status_code == 201
        d = r.json()
        assert d["league_id"] == "rl-test"
        assert d["status"] == "configured"
        assert d["squad_counts"]["sq-a"] == 2
        assert d["squad_counts"]["sq-b"] == 1

    def test_setup_overwrites_existing(self):
        setup_roster()
        # Re-setup with different players
        r = setup_roster(players=[PLAYER_1])
        assert r.status_code == 201
        d = r.json()
        assert d["squad_counts"]["sq-a"] == 1

    def test_setup_no_squads(self):
        r = client.post("/audit/v1/roster/setup", json={
            "league": BASE_LEAGUE,
            "squads": [],
            "players": [],
        })
        assert r.status_code == 201


class TestTransferPlayer:
    def setup_method(self):
        db_state.seed_baseline()
        setup_roster()

    def test_transfer_success(self):
        r = transfer({
            "request_id": "req-1",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
            "requested_by": "admin",
        })
        assert r.status_code == 201
        d = r.json()
        assert d["status"] == "accepted"
        assert d["state"] == "active"
        assert d["registration"]["squad_id"] == "sq-b"

    def test_loan_success(self):
        r = transfer({
            "request_id": "req-loan-1",
            "type": "loan",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
            "loan_end_date": "2026-12-31",
        })
        assert r.status_code == 201
        d = r.json()
        assert d["registration"]["registration_type"] == "loan"
        assert d["registration"]["parent_squad_id"] == "sq-a"

    def test_release_success(self):
        r = transfer({
            "request_id": "req-rel-1",
            "type": "release",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": None,
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 201
        d = r.json()
        assert d["registration"] is None

    def test_invalid_type(self):
        r = transfer({
            "request_id": "req-bad-type",
            "type": "borrow",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_league_not_found(self):
        r = transfer({
            "request_id": "req-no-league",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "nonexistent",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "LEAGUE_NOT_FOUND"

    def test_player_not_found(self):
        r = transfer({
            "request_id": "req-no-player",
            "type": "transfer",
            "player_id": "pl-nonexistent",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "PLAYER_NOT_FOUND"

    def test_squad_not_found(self):
        r = transfer({
            "request_id": "req-no-squad",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-nonexistent",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SQUAD_NOT_FOUND"

    def test_to_squad_not_found(self):
        r = transfer({
            "request_id": "req-no-tosquad",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-nonexistent",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SQUAD_NOT_FOUND"

    def test_not_in_squad(self):
        r = transfer({
            "request_id": "req-not-in-squad",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-b",  # pl-2 is in sq-a
            "to_squad_id": "sq-a",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "NOT_IN_SQUAD"

    def test_transfer_window_closed(self):
        r = transfer({
            "request_id": "req-window",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2025-01-01",  # before window
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "TRANSFER_WINDOW_CLOSED"

    def test_squad_full(self):
        # Fill sq-b to max (5)
        for i in range(4):
            client.post("/audit/v1/roster/setup", json={
                "league": {**BASE_LEAGUE, "max_squad_size": 1},
                "squads": [SQUAD_A, SQUAD_B],
                "players": [PLAYER_1, PLAYER_2, PLAYER_3],
            })
        # Setup a league with tiny max_squad_size
        client.post("/audit/v1/roster/setup", json={
            "league": {**BASE_LEAGUE, "max_squad_size": 1},
            "squads": [SQUAD_A, SQUAD_B],
            "players": [
                {"player_id": "pl-1", "name": "Alice", "position": "goalkeeper", "squad_id": "sq-a"},
                {"player_id": "pl-2", "name": "Bob", "position": "midfielder", "squad_id": "sq-a"},
                {"player_id": "pl-3", "name": "Charlie", "position": "forward", "squad_id": "sq-b"},
            ],
        })
        r = transfer({
            "request_id": "req-full",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "SQUAD_FULL"

    def test_min_position_violation(self):
        # pl-1 is the only goalkeeper in sq-a, required_positions = {"goalkeeper": 1}
        r = transfer({
            "request_id": "req-min-pos",
            "type": "transfer",
            "player_id": "pl-1",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "MIN_POSITION_VIOLATION"

    def test_loan_end_date_required(self):
        r = transfer({
            "request_id": "req-no-lend",
            "type": "loan",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 400

    def test_loan_end_before_effective(self):
        r = transfer({
            "request_id": "req-loan-bad-date",
            "type": "loan",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
            "loan_end_date": "2026-05-01",
        })
        assert r.status_code == 400

    def test_player_on_loan(self):
        transfer({
            "request_id": "req-loan-first",
            "type": "loan",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
            "loan_end_date": "2026-12-31",
        })
        # Try to loan again while on loan
        r = transfer({
            "request_id": "req-loan-second",
            "type": "loan",
            "player_id": "pl-2",
            "from_squad_id": "sq-b",
            "to_squad_id": "sq-a",
            "league_id": "rl-test",
            "effective_date": "2026-07-01",
            "loan_end_date": "2026-12-31",
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "PLAYER_ON_LOAN"

    def test_cross_tenant_transfer(self):
        # Setup a second tenant squad
        client.post("/audit/v1/roster/setup", json={
            "league": {**BASE_LEAGUE, "league_id": "rl-beta", "tenant_id": "tenant-beta"},
            "squads": [{"squad_id": "sq-beta", "tenant_id": "tenant-beta", "name": "Beta Squad"}],
            "players": [],
        })
        # Now try to transfer from alpha tenant squad to beta tenant squad in alpha league
        client.post("/audit/v1/roster/setup", json={
            "league": BASE_LEAGUE,
            "squads": [SQUAD_A, {"squad_id": "sq-beta2", "tenant_id": "tenant-beta", "name": "Beta"}],
            "players": [PLAYER_1, PLAYER_2],
        })
        r = transfer({
            "request_id": "req-cross-tenant",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-beta2",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "CROSS_TENANT_TRANSFER"

    def test_in_progress_match_defers(self):
        # Reset and setup with matches_in_progress (setup_roster already called in setup_method,
        # but we re-call it to inject matches_in_progress)
        db_state.seed_baseline()
        client.post("/audit/v1/roster/setup", json={
            "league": BASE_LEAGUE,
            "squads": [SQUAD_A, SQUAD_B],
            "players": [PLAYER_1, PLAYER_2, PLAYER_3],
            "matches_in_progress": [
                {"match_id": "m-live-1", "home_squad_id": "sq-a", "away_squad_id": "sq-b"}
            ],
        })
        r = transfer({
            "request_id": "req-deferred",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        assert r.status_code == 201
        d = r.json()
        assert d["state"] == "deferred_until_match_end"
        assert d["blocking_match_id"] == "m-live-1"


class TestTransferIdempotency:
    def setup_method(self):
        db_state.seed_baseline()
        setup_roster()

    def test_same_request_id_same_body(self):
        data = {
            "request_id": "req-idem",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        }
        r1 = transfer(data)
        assert r1.status_code == 201
        r2 = transfer(data)
        assert r2.status_code == 200
        assert r1.json() == r2.json()

    def test_same_request_id_different_body(self):
        data = {
            "request_id": "req-idem-diff",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        }
        transfer(data)
        data2 = {**data, "effective_date": "2026-07-01"}
        r2 = transfer(data2)
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "DUPLICATE_REQUEST_ID"


class TestGetHistory:
    def setup_method(self):
        db_state.seed_baseline()
        setup_roster()

    def test_history_not_found(self):
        r = client.get("/audit/v1/roster/history/pl-nonexistent")
        assert r.status_code == 404

    def test_history_no_transfers(self):
        r = client.get("/audit/v1/roster/history/pl-1")
        assert r.status_code == 200
        d = r.json()
        assert d["player_id"] == "pl-1"
        assert d["history"] == []

    def test_history_with_transfer(self):
        transfer({
            "request_id": "req-hist",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-06-01",
        })
        r = client.get("/audit/v1/roster/history/pl-2")
        assert r.status_code == 200
        d = r.json()
        assert len(d["history"]) == 1
        assert d["history"][0]["action"] == "transfer"
        assert d["current_squad_id"] == "sq-b"

    def test_loan_auto_return(self):
        transfer({
            "request_id": "req-loan-hist",
            "type": "loan",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-01-01",
            "loan_end_date": "2026-03-31",
        })
        # Query as of after loan_end_date
        r = client.get("/audit/v1/roster/history/pl-2?as_of=2026-10-01")
        assert r.status_code == 200
        d = r.json()
        # Should have loan + loan_return entries
        actions = [e["action"] for e in d["history"]]
        assert "loan" in actions
        assert "loan_return" in actions
        # Player should be back in sq-a
        assert d["current_squad_id"] == "sq-a"

    def test_as_of_parameter(self):
        transfer({
            "request_id": "req-asof",
            "type": "transfer",
            "player_id": "pl-2",
            "from_squad_id": "sq-a",
            "to_squad_id": "sq-b",
            "league_id": "rl-test",
            "effective_date": "2026-09-01",
        })
        # Query before the transfer
        r = client.get("/audit/v1/roster/history/pl-2?as_of=2026-08-01")
        assert r.status_code == 200
        d = r.json()
        # Transfer effective_date is 2026-09-01, as_of is 2026-08-01 => not yet applied
        assert d["current_squad_id"] is None  # no transfer applied yet
