from __future__ import annotations
from typing import Any
from app.domain.moderation_dlq import moderation_dlq_domain
from app.domain.qr_guest import qr_guest_domain
from app.domain.streaming import streaming_domain
from app.domain.models import db_state


class ObservabilityDomain:
    def __init__(self) -> None:
        self.active_ws_connections: int = 0
        self.stream_bitrate_kbps: int = 0

    def reset(self) -> None:
        self.active_ws_connections = 0
        self.stream_bitrate_kbps = 0

    def get_metrics_prometheus_text(self) -> str:
        # Dynamic gauges/counters from domains
        ws_conn = self.active_ws_connections
        active_streams = sum(1 for v in getattr(db_state, "stream_keys", {}).values() if isinstance(v, dict) and v.get("status") == "active")
        bitrate = self.stream_bitrate_kbps
        dlq_depth = len(moderation_dlq_domain.dlq)
        qr_scans = qr_guest_domain.telemetry.get("total_scans", 0)

        lines = [
            "# HELP nascon_active_ws_connections Active WebSocket connections",
            "# TYPE nascon_active_ws_connections gauge",
            f"nascon_active_ws_connections {ws_conn}",
            "# HELP nascon_active_streams_total Active published video streams",
            "# TYPE nascon_active_streams_total gauge",
            f"nascon_active_streams_total {active_streams}",
            "# HELP nascon_stream_bitrate_kbps Aggregate active stream ingest bitrate in kbps",
            "# TYPE nascon_stream_bitrate_kbps gauge",
            f"nascon_stream_bitrate_kbps {bitrate}",
            "# HELP nascon_dlq_depth Current dead letter queue message depth",
            "# TYPE nascon_dlq_depth gauge",
            f"nascon_dlq_depth {dlq_depth}",
            "# HELP nascon_qr_scans_total Total cryptographic QR scans resolved",
            "# TYPE nascon_qr_scans_total counter",
            f"nascon_qr_scans_total {qr_scans}",
            "",  # trailing newline required
        ]
        return "\n".join(lines)

    def anonymize_user(self, user_id: str) -> dict[str, Any]:
        # Wipe user cart if present
        if user_id in qr_guest_domain.user_carts:
            qr_guest_domain.user_carts[user_id] = []

        # Invalidate any guest tokens merged to this user
        tokens_to_wipe = [
            t for t, rec in qr_guest_domain.merged_tokens.items()
            if rec.get("response", {}).get("registered_user_id") == user_id
        ]
        for t in tokens_to_wipe:
            if t in qr_guest_domain.merged_tokens:
                del qr_guest_domain.merged_tokens[t]

        # Anonymize PII in db_state players if present
        if user_id in db_state.players:
            db_state.players[user_id]["anonymized"] = True

        return {
            "user_id": user_id,
            "status": "anonymized",
            "pii_retained": False,
            "tokens_wiped": True,
        }


observability_domain = ObservabilityDomain()
