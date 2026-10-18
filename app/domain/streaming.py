import secrets
from typing import Any
from app.core.errors import AppException
from app.core.crypto import sign_day2
from app.domain.models import db_state


class StreamingDomain:
    def __init__(self) -> None:
        self._revoked_keys: set[str] = set()

    def reset(self) -> None:
        self._revoked_keys.clear()

    @property
    def player_active_keys(self) -> dict[str, str]:
        return {
            pid: rec["stream_key"]
            for pid, rec in db_state.stream_keys.items()
            if rec.get("status") == "active"
        }

    def _validate_player(self, player_id: str) -> None:
        if player_id not in db_state.players:
            raise AppException(
                "PLAYER_NOT_FOUND",
                f"Player {player_id} not found",
                {"player_id": player_id},
                404,
            )

    def generate_key(self, player_id, label="default", stream_key_override=None):
        self._validate_player(player_id)
        stream_key = stream_key_override if stream_key_override else f"sk_live_{secrets.token_hex(8)}"
        status = "active"
        db_state.stream_keys[player_id] = {"stream_key": stream_key, "label": label, "status": status}
        sig_payload = {"action": "generate", "player_id": player_id, "status": status, "stream_key": stream_key}
        signature = sign_day2(stream_key, sig_payload)
        return {
            "player_id": player_id, "label": label, "stream_key": stream_key, "status": status,
            "ingest_endpoints": {
                "rtmp": f"rtmp://localhost:1935/live/{stream_key}",
                "webrtc": f"http://localhost:8889/live/{stream_key}/whip",
            },
            "playback_url": f"http://localhost:8888/live/{stream_key}/index.m3u8",
            "signature": signature,
        }

    def rotate_key(self, player_id, label="default", stream_key_override=None):
        self._validate_player(player_id)
        # Revoke old key if any
        old_rec = db_state.stream_keys.get(player_id)
        if old_rec:
            self._revoked_keys.add(old_rec["stream_key"])
        stream_key = stream_key_override if stream_key_override else f"sk_live_{secrets.token_hex(8)}"
        status = "active"
        db_state.stream_keys[player_id] = {"stream_key": stream_key, "label": label, "status": status}
        sig_payload = {"action": "rotate", "player_id": player_id, "status": status, "stream_key": stream_key}
        signature = sign_day2(stream_key, sig_payload)
        return {
            "player_id": player_id, "label": label, "stream_key": stream_key, "status": status,
            "ingest_endpoints": {
                "rtmp": f"rtmp://localhost:1935/live/{stream_key}",
                "webrtc": f"http://localhost:8889/live/{stream_key}/whip",
            },
            "playback_url": f"http://localhost:8888/live/{stream_key}/index.m3u8",
            "signature": signature,
        }

    def revoke_key(self, player_id):
        self._validate_player(player_id)
        rec = db_state.stream_keys.get(player_id)
        if not rec or rec.get("status") == "revoked":
            raise AppException("STREAM_NOT_FOUND", "Stream key not found", {}, 404)
        db_state.stream_keys[player_id]["status"] = "revoked"
        stream_key = rec["stream_key"]
        self._revoked_keys.add(stream_key)
        label = rec.get("label", "default")
        status = "revoked"
        sig_payload = {"action": "revoke", "player_id": player_id, "status": status, "stream_key": stream_key}
        signature = sign_day2(stream_key, sig_payload)
        return {
            "player_id": player_id, "label": label, "stream_key": stream_key, "status": status,
            "ingest_endpoints": None, "playback_url": None, "signature": signature,
        }

    def check_publish(self, stream_key: str) -> None:
        if stream_key in self._revoked_keys:
            raise AppException("KEY_REVOKED", "Stream key revoked", {"stream_key": stream_key}, 409)
        for rec in db_state.stream_keys.values():
            if rec.get("stream_key") == stream_key:
                if rec.get("status") == "revoked":
                    raise AppException("KEY_REVOKED", "Stream key revoked", {"stream_key": stream_key}, 409)
                return
        raise AppException("STREAM_NOT_FOUND", "Stream key not found", {"stream_key": stream_key}, 404)


streaming_domain = StreamingDomain()
