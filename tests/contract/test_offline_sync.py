"""
Contract Test Suite: Offline Sync Replay & Conflict Resolution (Section 5.14)
Verifies:
- Replaying score events & roster transfers
- Conflict resolution: appended, rebased_append, skipped_duplicate, server_wins
- INVALID_BASE_VERSION handling
- SQUAD_FULL rejection
- Sorting by queued_at ASC with response in original request order
"""

import pytest
from app.api.offline_sync import (
    OfflineSyncEngine,
    OfflineSyncRequest,
    OfflineActionItem
)

class TestOfflineSyncContract:
    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = OfflineSyncEngine(salt="T09D1271f28b2611")

    def test_offline_sync_happy_path_and_rebase(self):
        """
        Verify:
        Action 1: base_version == 2 (current = 2) -> applied / appended / server_version: 3
        Action 2: base_version == 1 (current = 3 after action 1) -> applied / rebased_append / server_version: 4
        """
        req = OfflineSyncRequest(
            device_id="dev-test-1",
            actions=[
                OfflineActionItem(
                    action_id="act-1",
                    type="score_event",
                    queued_at="2026-10-17T11:00:00Z",
                    base_version=2,
                    payload={"event_id": "evt-sync-1", "match_id": "m1", "type": "score", "payload": {"team_id": "t1", "event_type": "goal"}}
                ),
                OfflineActionItem(
                    action_id="act-2",
                    type="score_event",
                    queued_at="2026-10-17T11:05:00Z",
                    base_version=1,
                    payload={"event_id": "evt-sync-2", "match_id": "m1", "type": "score", "payload": {"team_id": "t2", "event_type": "goal"}}
                ),
            ]
        )

        res = self.engine.process_sync(req)
        assert res.device_id == "dev-test-1"
        assert res.summary == {"applied": 2, "rejected": 0, "duplicate": 0}

        r1 = res.results[0]
        assert r1.action_id == "act-1"
        assert r1.status == "applied"
        assert r1.resolution == "appended"
        assert r1.server_version == 3
        assert r1.signature is not None

        r2 = res.results[1]
        assert r2.action_id == "act-2"
        assert r2.status == "applied"
        assert r2.resolution == "rebased_append"
        assert r2.server_version == 4
        assert r2.signature is not None

    def test_offline_sync_duplicate_detection(self):
        """
        Section 5.14: Re-sending the same request again returns duplicate for every action and changes nothing.
        """
        req = OfflineSyncRequest(
            device_id="dev-test-dup",
            actions=[
                OfflineActionItem(
                    action_id="act-dup-1",
                    type="score_event",
                    queued_at="2026-10-17T11:00:00Z",
                    base_version=2,
                    payload={"event_id": "evt-dup-1", "match_id": "m1", "type": "score", "payload": {"team_id": "t1", "event_type": "goal"}}
                )
            ]
        )

        res1 = self.engine.process_sync(req)
        assert res1.results[0].status == "applied"

        # Resend identical request
        res2 = self.engine.process_sync(req)
        assert res2.summary == {"applied": 0, "rejected": 0, "duplicate": 1}
        r2 = res2.results[0]
        assert r2.status == "duplicate"
        assert r2.resolution == "skipped_duplicate"
        assert r2.error_code is None

    def test_offline_sync_invalid_base_version_and_squad_full(self):
        """
        Section 5.14:
        - base_version > current_version -> rejected / server_wins / INVALID_BASE_VERSION
        - Squad full -> rejected / server_wins / SQUAD_FULL
        """
        req = OfflineSyncRequest(
            device_id="dev-test-rejects",
            actions=[
                # Future base_version
                OfflineActionItem(
                    action_id="act-future",
                    type="score_event",
                    queued_at="2026-10-17T11:00:00Z",
                    base_version=999,
                    payload={"event_id": "evt-future", "match_id": "m1", "type": "score", "payload": {"team_id": "t1", "event_type": "goal"}}
                ),
                # Transfer into full squad (squad-alpha-2 is at capacity 25)
                OfflineActionItem(
                    action_id="act-roster-full",
                    type="roster_transfer",
                    queued_at="2026-10-17T11:01:00Z",
                    base_version=1,
                    payload={"player_id": "player-alpha-1", "from_squad_id": "squad-alpha-1", "to_squad_id": "squad-alpha-2"}
                )
            ]
        )

        res = self.engine.process_sync(req)
        assert res.summary == {"applied": 0, "rejected": 2, "duplicate": 0}

        r1 = res.results[0]
        assert r1.status == "rejected"
        assert r1.resolution == "server_wins"
        assert r1.error_code == "INVALID_BASE_VERSION"

        r2 = res.results[1]
        assert r2.status == "rejected"
        assert r2.resolution == "server_wins"
        assert r2.error_code == "SQUAD_FULL"

    def test_offline_sync_order_preservation(self):
        """
        Section 5.14:
        The server sorts actions by queued_at ascending to process them,
        but returns results in the original request order with processed_order recorded.
        """
        req = OfflineSyncRequest(
            device_id="dev-order",
            actions=[
                OfflineActionItem(
                    action_id="late-action",
                    type="score_event",
                    queued_at="2026-10-17T11:20:00Z",
                    base_version=2,
                    payload={"event_id": "evt-late", "match_id": "m1", "type": "score", "payload": {"team_id": "t1", "event_type": "goal"}}
                ),
                OfflineActionItem(
                    action_id="early-action",
                    type="score_event",
                    queued_at="2026-10-17T11:00:00Z",
                    base_version=2,
                    payload={"event_id": "evt-early", "match_id": "m1", "type": "score", "payload": {"team_id": "t1", "event_type": "goal"}}
                ),
            ]
        )

        res = self.engine.process_sync(req)
        # Results must be in request order: late-action first, early-action second
        assert res.results[0].action_id == "late-action"
        assert res.results[1].action_id == "early-action"

        # But early-action was processed first!
        assert res.results[1].processed_order == 1
        assert res.results[0].processed_order == 2
