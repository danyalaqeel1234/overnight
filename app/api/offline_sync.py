"""
Offline Sync Engine (Section 5.14)
Processes offline-queued score events and roster actions,
resolves conflicts, sorts by queued_at ASC, and returns results in request order.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import os
import hmac
import hashlib
import json

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def sign_event(salt: str, event_id: str, payload_obj: Any) -> str:
    msg = (event_id + "|" + canonical_json(payload_obj)).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()


class OfflineActionItem(BaseModel):
    action_id: str
    type: str  # 'score_event' | 'roster_transfer'
    queued_at: str
    base_version: int
    payload: Dict[str, Any]


class OfflineSyncRequest(BaseModel):
    device_id: str
    actions: List[OfflineActionItem] = Field(..., min_length=1, max_length=100)


class OfflineActionResult(BaseModel):
    action_id: str
    status: str  # 'applied' | 'rejected' | 'duplicate'
    resolution: str  # 'appended' | 'rebased_append' | 'skipped_duplicate' | 'server_wins'
    error_code: Optional[str] = None
    processed_order: int
    server_version: int
    signature: Optional[str] = None


class OfflineSyncResponse(BaseModel):
    device_id: str
    results: List[OfflineActionResult]
    summary: Dict[str, int]


class OfflineSyncEngine:
    def __init__(self, salt: Optional[str] = None):
        self.salt = salt or os.environ.get("DAY1_SALT", "T09D1271f28b2611")
        # In-memory tracking for replay and state
        self.processed_actions: Dict[tuple[str, str], OfflineActionResult] = {}  # (device_id, action_id) -> result
        self.processed_events: Dict[str, str] = {}  # event_id -> canonical_payload
        self.match_versions: Dict[str, int] = {"m1": 2, "m2": 0}
        self.player_versions: Dict[str, int] = {"player-alpha-1": 1}
        self.squad_capacities: Dict[str, int] = {"squad-alpha-1": 18, "squad-alpha-2": 25}
        self.squad_counts: Dict[str, int] = {"squad-alpha-1": 18, "squad-alpha-2": 25}

    def process_sync(self, req: OfflineSyncRequest) -> OfflineSyncResponse:
        device_id = req.device_id
        actions = req.actions

        # 1. Index actions to preserve request order
        indexed_actions = list(enumerate(actions))

        # 2. Sort by queued_at ascending (ties: original index order)
        sorted_actions = sorted(indexed_actions, key=lambda x: (x[1].queued_at, x[0]))

        # Map index -> result
        results_by_index: Dict[int, OfflineActionResult] = {}
        processed_order_counter = 1

        for orig_idx, action in sorted_actions:
            key = (device_id, action.action_id)

            # Check duplicate (device_id, action_id)
            if key in self.processed_actions:
                cached = self.processed_actions[key]
                res = OfflineActionResult(
                    action_id=action.action_id,
                    status="duplicate",
                    resolution="skipped_duplicate",
                    error_code=None,
                    processed_order=processed_order_counter,
                    server_version=cached.server_version,
                    signature=cached.signature,
                )
                results_by_index[orig_idx] = res
                processed_order_counter += 1
                continue

            # Process by action type
            if action.type == "score_event":
                res = self._process_score_event(device_id, action, processed_order_counter)
            elif action.type == "roster_transfer":
                res = self._process_roster_transfer(device_id, action, processed_order_counter)
            else:
                res = OfflineActionResult(
                    action_id=action.action_id,
                    status="rejected",
                    resolution="server_wins",
                    error_code="VALIDATION_ERROR",
                    processed_order=processed_order_counter,
                    server_version=0,
                    signature=None,
                )

            # Store for idempotency
            self.processed_actions[key] = res
            results_by_index[orig_idx] = res
            processed_order_counter += 1

        # 3. Assemble results in original request order
        results = [results_by_index[i] for i in range(len(actions))]

        summary = {
            "applied": sum(1 for r in results if r.status == "applied"),
            "rejected": sum(1 for r in results if r.status == "rejected"),
            "duplicate": sum(1 for r in results if r.status == "duplicate"),
        }

        return OfflineSyncResponse(device_id=device_id, results=results, summary=summary)

    def _process_score_event(self, device_id: str, action: OfflineActionItem, order: int) -> OfflineActionResult:
        payload = action.payload
        match_id = payload.get("match_id")
        event_id = payload.get("event_id")

        if match_id not in self.match_versions:
            return OfflineActionResult(
                action_id=action.action_id,
                status="rejected",
                resolution="server_wins",
                error_code="MATCH_NOT_FOUND",
                processed_order=order,
                server_version=0,
                signature=None
            )

        current_v = self.match_versions[match_id]

        # Check duplicate event_id
        if event_id in self.processed_events:
            canon = canonical_json(payload)
            if self.processed_events[event_id] == canon:
                return OfflineActionResult(
                    action_id=action.action_id,
                    status="duplicate",
                    resolution="skipped_duplicate",
                    error_code=None,
                    processed_order=order,
                    server_version=current_v,
                    signature=sign_event(self.salt, event_id, payload.get("payload", {}))
                )
            else:
                return OfflineActionResult(
                    action_id=action.action_id,
                    status="rejected",
                    resolution="server_wins",
                    error_code="DUPLICATE_EVENT_ID",
                    processed_order=order,
                    server_version=current_v,
                    signature=None
                )

        # base_version check
        if action.base_version > current_v:
            return OfflineActionResult(
                action_id=action.action_id,
                status="rejected",
                resolution="server_wins",
                error_code="INVALID_BASE_VERSION",
                processed_order=order,
                server_version=current_v,
                signature=None
            )

        resolution = "appended" if action.base_version == current_v else "rebased_append"
        new_v = current_v + 1
        self.match_versions[match_id] = new_v
        self.processed_events[event_id] = canonical_json(payload)

        sig = sign_event(self.salt, event_id, payload.get("payload", {}))

        return OfflineActionResult(
            action_id=action.action_id,
            status="applied",
            resolution=resolution,
            error_code=None,
            processed_order=order,
            server_version=new_v,
            signature=sig
        )

    def _process_roster_transfer(self, device_id: str, action: OfflineActionItem, order: int) -> OfflineActionResult:
        payload = action.payload
        player_id = payload.get("player_id")
        to_squad = payload.get("to_squad_id")

        if player_id not in self.player_versions:
            return OfflineActionResult(
                action_id=action.action_id,
                status="rejected",
                resolution="server_wins",
                error_code="PLAYER_NOT_FOUND",
                processed_order=order,
                server_version=0,
                signature=None
            )

        current_v = self.player_versions[player_id]

        if action.base_version > current_v:
            return OfflineActionResult(
                action_id=action.action_id,
                status="rejected",
                resolution="server_wins",
                error_code="INVALID_BASE_VERSION",
                processed_order=order,
                server_version=current_v,
                signature=None
            )

        # Check squad capacity
        if to_squad and self.squad_counts.get(to_squad, 0) >= self.squad_capacities.get(to_squad, 25):
            return OfflineActionResult(
                action_id=action.action_id,
                status="rejected",
                resolution="server_wins",
                error_code="SQUAD_FULL",
                processed_order=order,
                server_version=current_v,
                signature=None
            )

        resolution = "appended" if action.base_version == current_v else "rebased_append"
        new_v = current_v + 1
        self.player_versions[player_id] = new_v

        return OfflineActionResult(
            action_id=action.action_id,
            status="applied",
            resolution=resolution,
            error_code=None,
            processed_order=order,
            server_version=new_v,
            signature=None
        )
