"""Tests for POST /audit/v1/fixtures."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Round Robin
# ---------------------------------------------------------------------------

def test_rr_even_teams():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "round_robin", "teams": ["t1", "t2", "t3", "t4"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["team_count"] == 4
    assert body["round_count"] == 3
    assert len(body["rounds"]) == 3
    # Each round has 2 matches
    for r in body["rounds"]:
        assert len(r["matches"]) == 2
        assert r["byes"] == []


def test_rr_odd_teams():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "round_robin", "teams": ["t1", "t2", "t3", "t4", "t5"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["team_count"] == 5
    assert body["round_count"] == 5
    # Each round has 2 matches and 1 bye
    for r in body["rounds"]:
        assert len(r["matches"]) == 2
        assert len(r["byes"]) == 1


def test_rr_each_pair_meets_once():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "round_robin", "teams": ["t1", "t2", "t3", "t4"]},
    )
    body = resp.json()
    pairs = set()
    for r in body["rounds"]:
        for m in r["matches"]:
            pair = frozenset([m["home"], m["away"]])
            assert pair not in pairs, f"Duplicate pair: {pair}"
            pairs.add(pair)
    assert len(pairs) == 6  # C(4,2)


def test_rr_home_away_balance():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "round_robin", "teams": ["t1", "t2", "t3", "t4", "t5", "t6"]},
    )
    body = resp.json()
    home_count = {}
    away_count = {}
    for r in body["rounds"]:
        for m in r["matches"]:
            home_count[m["home"]] = home_count.get(m["home"], 0) + 1
            away_count[m["away"]] = away_count.get(m["away"], 0) + 1
    for t in ["t1", "t2", "t3", "t4", "t5", "t6"]:
        diff = abs(home_count.get(t, 0) - away_count.get(t, 0))
        assert diff <= 1, f"Team {t} home/away imbalance: {diff}"


def test_rr_legs_2():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "round_robin", "teams": ["t1", "t2", "t3", "t4"], "params": {"legs": 2}},
    )
    body = resp.json()
    assert body["legs"] == 2
    assert body["round_count"] == 6
    # Leg 2 should have swapped home/away
    leg1_pairs = {
        frozenset([m["home"], m["away"]]): (m["home"], m["away"])
        for r in body["rounds"][:3]
        for m in r["matches"]
    }
    leg2_pairs = {
        frozenset([m["home"], m["away"]]): (m["home"], m["away"])
        for r in body["rounds"][3:]
        for m in r["matches"]
    }
    for key in leg1_pairs:
        assert key in leg2_pairs
        # home/away should be swapped
        l1h, l1a = leg1_pairs[key]
        l2h, l2a = leg2_pairs[key]
        assert l1h == l2a
        assert l1a == l2h


def test_rr_withdrawal_forfeit():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "round_robin",
            "teams": ["t1", "t2", "t3", "t4", "t5"],
            "params": {
                "withdrawals": [{"team_id": "t3", "after_round": 2}],
                "withdrawal_policy": "forfeit_remaining",
            },
        },
    )
    body = resp.json()
    for r in body["rounds"]:
        for m in r["matches"]:
            if m["home"] == "t3" or m["away"] == "t3":
                if r["round"] > 2:
                    assert m["status"] == "forfeit"
                    assert m["awarded_to"] != "t3"
                else:
                    assert m["status"] == "scheduled"


def test_rr_withdrawal_void_all():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "round_robin",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {
                "withdrawals": [{"team_id": "t2", "after_round": 0}],
                "withdrawal_policy": "void_all",
            },
        },
    )
    body = resp.json()
    for r in body["rounds"]:
        for m in r["matches"]:
            if m["home"] == "t2" or m["away"] == "t2":
                assert m["status"] == "voided"
                assert m["awarded_to"] is None


def test_rr_unknown_withdrawal_400():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "round_robin",
            "teams": ["t1", "t2"],
            "params": {"withdrawals": [{"team_id": "t99", "after_round": 0}]},
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Swiss
# ---------------------------------------------------------------------------

def test_swiss_round1_exact():
    """Round 1: m=floor(n/2), pair seed i with seed i+m."""
    teams = ["t1", "t2", "t3", "t4", "t5", "t6"]
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "swiss", "teams": teams, "params": {"round": 1}},
    )
    assert resp.status_code == 200
    body = resp.json()
    # n=6, m=3, pairs: (t1,t4),(t2,t5),(t3,t6)
    pairings = {frozenset([p["home"], p["away"]]) for p in body["pairings"]}
    assert frozenset(["t1", "t4"]) in pairings
    assert frozenset(["t2", "t5"]) in pairings
    assert frozenset(["t3", "t6"]) in pairings
    assert body["bye"] is None


def test_swiss_round1_odd_bye():
    """Odd n: last seed gets the bye."""
    teams = ["t1", "t2", "t3", "t4", "t5"]
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "swiss", "teams": teams, "params": {"round": 1}},
    )
    body = resp.json()
    assert body["bye"] == "t5"
    assert len(body["pairings"]) == 2


def test_swiss_round2_pairing():
    """Round 2 uses history to compute standings and pairings."""
    teams = ["t1", "t2", "t3", "t4"]
    history = [
        {
            "round": 1,
            "bye": None,
            "matches": [
                {"home": "t1", "away": "t3", "result": "home"},
                {"home": "t2", "away": "t4", "result": "home"},
            ],
        }
    ]
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "swiss",
            "teams": teams,
            "params": {"round": 2, "total_rounds": 3, "history": history},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["round"] == 2
    assert len(body["pairings"]) == 2
    # Check standings are computed from history
    for s in body["standings"]:
        if s["team_id"] in ("t1", "t2"):
            assert s["score"] == 1.0
        else:
            assert s["score"] == 0.0


def test_swiss_invalid_history_400():
    """history must have exactly rounds 1..round-1."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "swiss",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"round": 2, "history": []},  # missing round 1
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Single Elimination
# ---------------------------------------------------------------------------

def test_single_elim_bracket_size():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "single_elim", "teams": ["t1", "t2", "t3", "t4", "t5", "t6"]},
    )
    body = resp.json()
    assert body["bracket_size"] == 8


def test_single_elim_seed_order():
    """n=6, B=8, order=[1,8,4,5,2,7,3,6]. R1M1: seed1 vs seed8 (bye)."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "single_elim", "teams": ["t1", "t2", "t3", "t4", "t5", "t6"]},
    )
    body = resp.json()
    r1 = body["rounds"][0]["matches"]
    # R1M1: seed 1 vs seed 8 -> bye
    m1 = next(m for m in r1 if m["match_id"] == "R1M1")
    assert m1["bye"] is True
    assert m1["away"] is None
    assert m1["home"] == "t1"


def test_single_elim_advancement():
    """Winner propagates to next round."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "single_elim",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"results": [{"match_id": "R1M1", "winner": "t1"}]},
        },
    )
    body = resp.json()
    r2 = body["rounds"][1]["matches"]
    r2m1 = next(m for m in r2 if m["match_id"] == "R2M1")
    assert r2m1["home"] == "t1"


def test_single_elim_invalid_winner_400():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "single_elim",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"results": [{"match_id": "R1M1", "winner": "t99"}]},
        },
    )
    assert resp.status_code == 400


def test_single_elim_third_place():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "single_elim",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"third_place_match": True},
        },
    )
    body = resp.json()
    assert "third_place_match" in body
    assert body["third_place_match"]["match_id"] == "TP"


# ---------------------------------------------------------------------------
# Double Elimination
# ---------------------------------------------------------------------------

def test_double_elim_structure():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "double_elim", "teams": ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bracket_size"] == 8
    assert len(body["winners"]) == 3  # WR rounds 1,2,3
    assert len(body["losers"]) == 4   # LR rounds 1..4
    assert len(body["grand_final"]) == 1  # GF1 only (no bracket_reset)


def test_double_elim_bracket_reset():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "double_elim",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"bracket_reset": True},
        },
    )
    body = resp.json()
    assert body["bracket_reset"] is True
    assert len(body["grand_final"]) == 2
    gf2 = body["grand_final"][1]
    assert gf2["conditional"] is True
    assert gf2["required"] is None  # no result yet


def test_swiss_invalid_round_400():
    """round > total_rounds -> 400."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "swiss",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"round": 10, "total_rounds": 3, "history": []},
        },
    )
    assert resp.status_code == 400


def test_rr_both_withdrawn_voided():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "round_robin",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {
                "withdrawals": [
                    {"team_id": "t1", "after_round": 0},
                    {"team_id": "t2", "after_round": 0},
                ],
                "withdrawal_policy": "forfeit_remaining",
            },
        },
    )
    body = resp.json()
    for r in body["rounds"]:
        for m in r["matches"]:
            if m["home"] in ("t1", "t2") and m["away"] in ("t1", "t2"):
                assert m["status"] == "voided"


def test_rr_summary_counts():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "round_robin",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {
                "withdrawals": [{"team_id": "t1", "after_round": 1}],
                "withdrawal_policy": "forfeit_remaining",
            },
        },
    )
    body = resp.json()
    s = body["summary"]
    assert s["total"] == s["scheduled"] + s["forfeit"] + s["voided"]


def test_single_elim_n_equals_power_of_two():
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "single_elim", "teams": ["t1", "t2", "t3", "t4"]},
    )
    body = resp.json()
    assert body["bracket_size"] == 4
    assert len(body["rounds"]) == 2
    # No byes
    r1 = body["rounds"][0]["matches"]
    for m in r1:
        assert m["bye"] is False


def test_single_elim_bye_winner_propagated():
    """WR1 bye winner propagated immediately to R2."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "single_elim", "teams": ["t1", "t2", "t3"]},  # B=4
    )
    body = resp.json()
    r1 = body["rounds"][0]["matches"]
    r2 = body["rounds"][1]["matches"]
    # Find the bye match
    bye_match = next((m for m in r1 if m["bye"]), None)
    assert bye_match is not None
    # Its winner should already appear in R2
    wt_mid = bye_match["winner_to"]["match_id"]
    wt_slot = bye_match["winner_to"]["slot"]
    r2_match = next(m for m in r2 if m["match_id"] == wt_mid)
    assert r2_match[wt_slot] == bye_match["winner"]


def test_swiss_standings_order():
    """Standings sorted by score desc, buchholz desc."""
    teams = ["t1", "t2", "t3", "t4"]
    history = [
        {
            "round": 1,
            "bye": None,
            "matches": [
                {"home": "t1", "away": "t3", "result": "home"},
                {"home": "t2", "away": "t4", "result": "draw"},
            ],
        }
    ]
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "swiss", "teams": teams, "params": {"round": 2, "history": history}},
    )
    body = resp.json()
    standings = body["standings"]
    scores = [s["score"] for s in standings]
    assert scores == sorted(scores, reverse=True)


def test_double_elim_total_lr_matches():
    """Total LR matches = B - 2."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "double_elim", "teams": ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"]},
    )
    body = resp.json()
    B = body["bracket_size"]
    total_lr = sum(len(r["matches"]) for r in body["losers"])
    assert total_lr == B - 2


def test_double_elim_with_results():
    """Apply results and check winner propagation."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "double_elim",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"results": [{"match_id": "WR1M1", "winner": "t1"}]},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # WR1M1 winner should be t1
    wr1_matches = body["winners"][0]["matches"]
    m = next(m for m in wr1_matches if m["match_id"] == "WR1M1")
    assert m["winner"] == "t1"


def test_double_elim_invalid_winner_400():
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "double_elim",
            "teams": ["t1", "t2", "t3", "t4"],
            "params": {"results": [{"match_id": "WR1M1", "winner": "t99"}]},
        },
    )
    assert resp.status_code == 400


def test_swiss_odd_round2_bye():
    """Round 2 with odd n: bye goes to lowest scoring team without previous bye."""
    teams = ["t1", "t2", "t3", "t4", "t5"]
    history = [
        {
            "round": 1,
            "bye": "t5",
            "matches": [
                {"home": "t1", "away": "t3", "result": "home"},
                {"home": "t2", "away": "t4", "result": "home"},
            ],
        }
    ]
    resp = client.post(
        "/audit/v1/fixtures",
        json={
            "format": "swiss",
            "teams": teams,
            "params": {"round": 2, "total_rounds": 3, "history": history},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # t5 had a bye in round 1, so round 2 bye should NOT be t5
    assert body["bye"] != "t5"
    assert len(body["pairings"]) == 2


def test_rr_match_id_format():
    """Verify match IDs follow RR-L{leg}-R{round}-M{index} format."""
    resp = client.post(
        "/audit/v1/fixtures",
        json={"format": "round_robin", "teams": ["t1", "t2", "t3", "t4"], "params": {"legs": 2}},
    )
    body = resp.json()
    for r in body["rounds"]:
        for m in r["matches"]:
            mid = m["match_id"]
            assert mid.startswith("RR-L")
            parts = mid.split("-")
            assert len(parts) == 4
