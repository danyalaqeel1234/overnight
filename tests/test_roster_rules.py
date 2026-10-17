"""
Unit & Contract Test Suite: Roster & Transfer Engine (Section 5.11 & SPEC_TRAPS.md Rule 5)
Tests:
1. Exact 8-step check order precedence:
   1. 400 schema/dates (loan_end_date <= effective_date)
   2. 404 *_NOT_FOUND (missing league/player/squad)
   3. 409 CROSS_TENANT_TRANSFER
   4. 409 NOT_IN_SQUAD
   5. 409 TRANSFER_WINDOW_CLOSED
   6. 409 PLAYER_ON_LOAN
   7. 409 SQUAD_FULL
   8. 409 MIN_POSITION_VIOLATION
2. Deferred transfer during in-progress match (state: "deferred_until_match_end").
3. Query-time auto loan return on GET /audit/v1/roster/history?as_of=<date>.
"""

import pytest
from typing import Dict, Any, List, Optional
from datetime import datetime

class RosterRulesEngine:
    """
    Reference Roster Management Engine enforcing Section 5.11 check order.
    """
    def __init__(self):
        self.leagues = {
            "league-alpha-1": {
                "league_id": "league-alpha-1",
                "tenant_id": "tenant-alpha",
                "transfer_window": {"start": "2026-10-01", "end": "2026-10-20"},
                "squad_limits": {"max_players": 5, "min_goalkeepers": 1}
            }
        }
        self.squads = {
            "squad-alpha-1": {"squad_id": "squad-alpha-1", "tenant_id": "tenant-alpha", "league_id": "league-alpha-1"},
            "squad-alpha-2": {"squad_id": "squad-alpha-2", "tenant_id": "tenant-alpha", "league_id": "league-alpha-1"},
            "squad-beta-1": {"squad_id": "squad-beta-1", "tenant_id": "tenant-beta", "league_id": "league-beta-1"},
        }
        self.players = {
            "player-p1": {
                "player_id": "player-p1",
                "squad_id": "squad-alpha-1",
                "position": "forward",
                "on_loan": False,
                "loan_end_date": None,
                "parent_squad_id": None
            },
            "player-loaned": {
                "player_id": "player-loaned",
                "squad_id": "squad-alpha-1",
                "position": "midfielder",
                "on_loan": True,
                "loan_end_date": "2026-10-15",
                "parent_squad_id": "squad-alpha-2"
            },
            "player-gk": {
                "player_id": "player-gk",
                "squad_id": "squad-alpha-1",
                "position": "goalkeeper",
                "on_loan": False,
                "loan_end_date": None,
                "parent_squad_id": None
            }
        }
        # Player counts per squad
        self.squad_players = {
            "squad-alpha-1": ["player-p1", "player-loaned", "player-gk"],
            "squad-alpha-2": ["p2", "p3", "p4", "p5", "p6"],  # 5 players = full!
            "squad-beta-1": ["p-beta-1"]
        }
        self.active_matches = {
            "player-p1": "match-m100"  # In an active match
        }
        self.audit_log: List[Dict[str, Any]] = []

    def transfer(self, req: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        # STEP 1: Schema / dates validation -> 400
        transfer_type = req.get("type", "transfer")
        effective_date = req.get("effective_date")
        loan_end_date = req.get("loan_end_date")
        to_squad_id = req.get("to_squad_id")

        if not req.get("player_id") or not req.get("from_squad_id"):
            return 400, {"error": {"code": "VALIDATION_ERROR", "message": "Missing required fields", "details": {}}}

        if transfer_type == "loan":
            if not loan_end_date or loan_end_date <= effective_date:
                return 400, {"error": {"code": "VALIDATION_ERROR", "message": "loan_end_date must be after effective_date", "details": {}}}

        if transfer_type != "release" and not to_squad_id:
            return 400, {"error": {"code": "VALIDATION_ERROR", "message": "to_squad_id required unless release", "details": {}}}

        # STEP 2: Referenced IDs exist -> 404
        league_id = req.get("league_id")
        if league_id not in self.leagues:
            return 404, {"error": {"code": "LEAGUE_NOT_FOUND", "message": "League not found", "details": {}}}

        player_id = req.get("player_id")
        if player_id not in self.players:
            return 404, {"error": {"code": "PLAYER_NOT_FOUND", "message": "Player not found", "details": {}}}

        from_squad_id = req.get("from_squad_id")
        if from_squad_id not in self.squads:
            return 404, {"error": {"code": "SQUAD_NOT_FOUND", "message": "Source squad not found", "details": {}}}

        if to_squad_id and to_squad_id not in self.squads:
            return 404, {"error": {"code": "SQUAD_NOT_FOUND", "message": "Destination squad not found", "details": {}}}

        # STEP 3: Cross-tenant check -> 409 CROSS_TENANT_TRANSFER
        from_tenant = self.squads[from_squad_id]["tenant_id"]
        if to_squad_id:
            to_tenant = self.squads[to_squad_id]["tenant_id"]
            if from_tenant != to_tenant:
                return 409, {"error": {"code": "CROSS_TENANT_TRANSFER", "message": "Cross-tenant transfer not allowed", "details": {}}}

        # STEP 4: Not in squad -> 409 NOT_IN_SQUAD
        player = self.players[player_id]
        if player["squad_id"] != from_squad_id:
            return 409, {"error": {"code": "NOT_IN_SQUAD", "message": "Player not in source squad", "details": {}}}

        # STEP 5: Transfer window closed -> 409 TRANSFER_WINDOW_CLOSED (release always allowed)
        if transfer_type != "release":
            window = self.leagues[league_id]["transfer_window"]
            if effective_date < window["start"] or effective_date > window["end"]:
                return 409, {"error": {"code": "TRANSFER_WINDOW_CLOSED", "message": "Transfer window closed", "details": {}}}

        # STEP 6: Player on loan -> 409 PLAYER_ON_LOAN
        if player["on_loan"] and transfer_type != "release":
            return 409, {"error": {"code": "PLAYER_ON_LOAN", "message": "Player currently on loan", "details": {}}}

        # STEP 7: Destination squad full -> 409 SQUAD_FULL
        if to_squad_id:
            dest_count = len(self.squad_players.get(to_squad_id, []))
            max_allowed = self.leagues[league_id]["squad_limits"]["max_players"]
            if dest_count >= max_allowed:
                return 409, {"error": {"code": "SQUAD_FULL", "message": "Destination squad is full", "details": {}}}

        # STEP 8: Min position violation -> 409 MIN_POSITION_VIOLATION
        if player["position"] == "goalkeeper":
            current_gks = sum(1 for pid in self.squad_players[from_squad_id] if self.players[pid]["position"] == "goalkeeper")
            min_gks = self.leagues[league_id]["squad_limits"]["min_goalkeepers"]
            if current_gks - 1 < min_gks:
                return 409, {"error": {"code": "MIN_POSITION_VIOLATION", "message": "Minimum position violation", "details": {}}}

        # Check for in-progress match deferral
        blocking_match = self.active_matches.get(player_id)
        if blocking_match:
            return 200, {
                "status": "accepted",
                "state": "deferred_until_match_end",
                "blocking_match_id": blocking_match,
                "player_id": player_id
            }

        # Apply transfer
        self.squad_players[from_squad_id].remove(player_id)
        if to_squad_id:
            self.squad_players[to_squad_id].append(player_id)
            player["squad_id"] = to_squad_id

        self.audit_log.append({
            "action": transfer_type,
            "player_id": player_id,
            "from_squad_id": from_squad_id,
            "to_squad_id": to_squad_id,
            "effective_date": effective_date,
            "who": "manager"
        })

        return 200, {"status": "success", "state": "applied", "player_id": player_id}

    def get_history(self, player_id: str, as_of: Optional[str] = None) -> List[Dict[str, Any]]:
        history = [entry for entry in self.audit_log if entry["player_id"] == player_id]
        player = self.players.get(player_id)

        # Section 5.11: Query-time auto loan return
        if as_of and player and player.get("on_loan") and player.get("loan_end_date"):
            if as_of > player["loan_end_date"]:
                # Check if auto return already recorded
                already_returned = any(
                    e.get("action") == "loan_return" and e.get("who") == "system"
                    for e in history
                )
                if not already_returned:
                    return_entry = {
                        "action": "loan_return",
                        "player_id": player_id,
                        "from_squad_id": player["squad_id"],
                        "to_squad_id": player["parent_squad_id"],
                        "effective_date": player["loan_end_date"],
                        "who": "system"
                    }
                    history.append(return_entry)
                    self.audit_log.append(return_entry)
                    player["on_loan"] = False
                    player["squad_id"] = player["parent_squad_id"]

        return history


class TestRosterRules:
    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = RosterRulesEngine()

    def test_exact_8_step_check_order(self):
        """
        Verify the exact 8-step failure check order:
        First failure encountered must trigger and win!
        """
        # 1. Schema check: loan_end_date <= effective_date -> 400
        res1_status, res1_body = self.engine.transfer({
            "type": "loan",
            "effective_date": "2026-10-10",
            "loan_end_date": "2026-10-05",  # bad date
            "player_id": "player-p1",
            "from_squad_id": "squad-alpha-1",
            "to_squad_id": "squad-alpha-2"
        })
        assert res1_status == 400
        assert res1_body["error"]["code"] == "VALIDATION_ERROR"

        # 2. 404 check: Unknown player_id -> 404
        res2_status, res2_body = self.engine.transfer({
            "type": "transfer",
            "effective_date": "2026-10-10",
            "league_id": "league-alpha-1",
            "player_id": "player-DOES-NOT-EXIST",
            "from_squad_id": "squad-alpha-1",
            "to_squad_id": "squad-alpha-2"
        })
        assert res2_status == 404
        assert res2_body["error"]["code"] == "PLAYER_NOT_FOUND"

        # 3. 409 CROSS_TENANT_TRANSFER: Transferring from Alpha to Beta -> 409
        res3_status, res3_body = self.engine.transfer({
            "type": "transfer",
            "effective_date": "2026-10-10",
            "league_id": "league-alpha-1",
            "player_id": "player-p1",
            "from_squad_id": "squad-alpha-1",
            "to_squad_id": "squad-beta-1"  # Different tenant!
        })
        assert res3_status == 409
        assert res3_body["error"]["code"] == "CROSS_TENANT_TRANSFER"

        # 4. 409 NOT_IN_SQUAD: Player belongs to squad-alpha-1, but request specifies from squad-alpha-2 -> 409
        res4_status, res4_body = self.engine.transfer({
            "type": "transfer",
            "effective_date": "2026-10-10",
            "league_id": "league-alpha-1",
            "player_id": "player-p1",
            "from_squad_id": "squad-alpha-2",
            "to_squad_id": "squad-alpha-1"
        })
        assert res4_status == 409
        assert res4_body["error"]["code"] == "NOT_IN_SQUAD"

        # 5. 409 TRANSFER_WINDOW_CLOSED: Outside window (window is 2026-10-01 to 2026-10-20) -> 409
        res5_status, res5_body = self.engine.transfer({
            "type": "transfer",
            "effective_date": "2026-11-01",  # Window closed!
            "league_id": "league-alpha-1",
            "player_id": "player-p1",
            "from_squad_id": "squad-alpha-1",
            "to_squad_id": "squad-alpha-2"
        })
        assert res5_status == 409
        assert res5_body["error"]["code"] == "TRANSFER_WINDOW_CLOSED"

        # 6. 409 PLAYER_ON_LOAN: player-loaned is currently on loan -> 409
        res6_status, res6_body = self.engine.transfer({
            "type": "transfer",
            "effective_date": "2026-10-10",
            "league_id": "league-alpha-1",
            "player_id": "player-loaned",
            "from_squad_id": "squad-alpha-1",
            "to_squad_id": "squad-alpha-2"
        })
        assert res6_status == 409
        assert res6_body["error"]["code"] == "PLAYER_ON_LOAN"

        # 7. 409 SQUAD_FULL: squad-alpha-2 already has 5 players (capacity = 5) -> 409
        # (Remove active match first to test squad full check directly)
        self.engine.active_matches.clear()
        res7_status, res7_body = self.engine.transfer({
            "type": "transfer",
            "effective_date": "2026-10-10",
            "league_id": "league-alpha-1",
            "player_id": "player-p1",
            "from_squad_id": "squad-alpha-1",
            "to_squad_id": "squad-alpha-2"
        })
        assert res7_status == 409
        assert res7_body["error"]["code"] == "SQUAD_FULL"

        # 8. 409 MIN_POSITION_VIOLATION: squad-alpha-1 only has 1 goalkeeper; releasing/transferring leaves 0 -> 409
        res8_status, res8_body = self.engine.transfer({
            "type": "release",
            "effective_date": "2026-10-10",
            "league_id": "league-alpha-1",
            "player_id": "player-gk",
            "from_squad_id": "squad-alpha-1"
        })
        assert res8_status == 409
        assert res8_body["error"]["code"] == "MIN_POSITION_VIOLATION"

    def test_deferred_transfer_during_in_progress_match(self):
        """
        Verify Section 5.11: In-progress match accepts transfer with state 'deferred_until_match_end'.
        """
        # Make room in squad-alpha-2
        self.engine.squad_players["squad-alpha-2"].pop()
        # Ensure player-p1 has an active match
        self.engine.active_matches["player-p1"] = "match-m100"

        status, body = self.engine.transfer({
            "type": "transfer",
            "effective_date": "2026-10-10",
            "league_id": "league-alpha-1",
            "player_id": "player-p1",
            "from_squad_id": "squad-alpha-1",
            "to_squad_id": "squad-alpha-2"
        })
        assert status == 200
        assert body["status"] == "accepted"
        assert body["state"] == "deferred_until_match_end"
        assert body["blocking_match_id"] == "match-m100"

    def test_query_time_auto_loan_return(self):
        """
        Verify Section 5.11:
        GET /audit/v1/roster/history?as_of=<date> appends a loan_return entry (who: 'system')
        exactly once when as_of > loan_end_date.
        """
        player_id = "player-loaned"
        # player-loaned loan_end_date is 2026-10-15
        
        # Query before loan end
        h_before = self.engine.get_history(player_id, as_of="2026-10-10")
        assert len(h_before) == 0

        # Query after loan end: 2026-10-17
        h_after = self.engine.get_history(player_id, as_of="2026-10-17")
        assert len(h_after) == 1
        return_event = h_after[0]
        assert return_event["action"] == "loan_return"
        assert return_event["who"] == "system"
        assert return_event["to_squad_id"] == "squad-alpha-2"

        # Query again: must not duplicate
        h_repeated = self.engine.get_history(player_id, as_of="2026-10-18")
        assert len(h_repeated) == 1
