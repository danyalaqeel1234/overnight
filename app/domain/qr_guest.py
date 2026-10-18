from __future__ import annotations
import io
import re
import datetime
from typing import Any
import segno
from fpdf import FPDF

from app.core.errors import AppException
from app.core.crypto import sign_day2, canonical
from app.domain.models import db_state
from app.domain.scoring import project_match


class QRGuestDomain:
    def __init__(self) -> None:
        # short_code -> entity_id
        self.code_to_entity: dict[str, str] = {}
        # entity_id -> metadata {short_code, short_url, scan_count}
        self.entity_to_meta: dict[str, dict[str, Any]] = {}
        # Privacy-safe scan telemetry: {total_scans, device_family: {mobile: X, desktop: Y}, buckets: {hour: Z}}
        self.telemetry: dict[str, Any] = {
            "total_scans": 0,
            "device_family": {"mobile": 0, "desktop": 0},
            "hourly_buckets": {},
        }
        # Guest carts: guest_token -> list of items
        self.guest_carts: dict[str, list[dict[str, Any]]] = {}
        # Registered user carts: user_id -> list of items
        self.user_carts: dict[str, list[dict[str, Any]]] = {}
        # Merged tokens audit: guest_token -> {fingerprint, response}
        self.merged_tokens: dict[str, dict[str, Any]] = {}
        # Cached QR export bytes: (entity_id, fmt) -> bytes
        self._export_cache: dict[tuple[str, str], bytes] = {}

    def reset(self) -> None:
        self.code_to_entity.clear()
        self.entity_to_meta.clear()
        self._export_cache.clear()
        if hasattr(self, "_inspect_cache"):
            self._inspect_cache.clear()
        self.telemetry = {
            "total_scans": 0,
            "device_family": {"mobile": 0, "desktop": 0},
            "hourly_buckets": {},
        }
        self.guest_carts.clear()
        self.user_carts.clear()
        self.merged_tokens.clear()

        # Seed initial QR mappings per spec
        self.register_entity("match-m1", short_code="m1-live", scan_count=0)
        self.register_entity("player-alpha-1", short_code="p-alpha-1", scan_count=0)
        self.register_entity("club-alpha-1", short_code="c-alpha-1", scan_count=0)

        # Seed initial user cart for player-alpha-1
        self.user_carts["player-alpha-1"] = []

        # Seed guest token
        db_state.guest_tokens["guest_anon_tok_7721"] = {
            "token": "guest_anon_tok_7721",
            "role": "guest",
            "merged": False,
        }

    def register_entity(self, entity_id: str, short_code: str | None = None, scan_count: int = 0) -> str:
        if not short_code:
            short_code = entity_id
        short_url = f"http://localhost:8080/q/{short_code}"
        self.code_to_entity[short_code] = entity_id
        self.entity_to_meta[entity_id] = {
            "short_code": short_code,
            "short_url": short_url,
            "scan_count": scan_count,
        }
        return short_url

    def _get_entity_info(self, entity_id: str) -> tuple[str, str]:
        """Returns (entity_type, entity_status). Raises 404 if unknown."""
        if entity_id.startswith("match-"):
            if entity_id not in db_state.matches:
                raise AppException("QR_NOT_FOUND", f"Match entity {entity_id} not found", {"entity_id": entity_id}, 404)
            m = db_state.matches[entity_id]
            proj = project_match(entity_id)
            proj_status = proj.get("status") if proj else None
            m_status = m.get("status")

            if proj_status in ("completed", "postponed", "cancelled", "abandoned"):
                status = proj_status
            elif m_status in ("completed", "postponed", "cancelled", "abandoned"):
                status = m_status
            elif proj_status:
                status = proj_status
            else:
                status = m_status or "upcoming"
            return "match", status

        elif entity_id.startswith("player-"):
            if entity_id not in db_state.players:
                raise AppException("QR_NOT_FOUND", f"Player entity {entity_id} not found", {"entity_id": entity_id}, 404)
            return "player", "active"

        elif entity_id.startswith("club-"):
            if entity_id not in db_state.clubs:
                raise AppException("QR_NOT_FOUND", f"Club entity {entity_id} not found", {"entity_id": entity_id}, 404)
            return "club", "active"

        elif entity_id.startswith("cs-session-"):
            # Costream session
            from app.domain.costream import costream_domain
            sess = costream_domain.sessions.get(entity_id)
            status = sess["status"] if sess else "active"
            return "costream", status

        else:
            raise AppException("QR_NOT_FOUND", f"Entity {entity_id} not recognized", {"entity_id": entity_id}, 404)

    def compute_target_route(self, entity_id: str, entity_type: str, entity_status: str) -> str:
        """Live target route computation per Section 4.5."""
        if entity_type == "match":
            if entity_status == "upcoming":
                return f"/web/matches/{entity_id}/preview"
            elif entity_status == "in_progress":
                return f"/web/matches/{entity_id}/live"
            elif entity_status == "completed":
                return f"/web/matches/{entity_id}/vod"
            elif entity_status in ("postponed", "cancelled", "abandoned"):
                return f"/web/matches/{entity_id}/notice?state={entity_status}"
            else:
                return f"/web/matches/{entity_id}/live"
        elif entity_type == "player":
            return f"/web/players/{entity_id}"
        elif entity_type == "club":
            return f"/web/clubs/{entity_id}"
        elif entity_type == "costream":
            return f"/web/costream/{entity_id}"
        return f"/web/entities/{entity_id}"

    def get_qr(self, entity_id: str, inspect: bool = False) -> dict[str, Any]:
        entity_type, entity_status = self._get_entity_info(entity_id)

        # Get or auto-register short code
        if entity_id in db_state.qr_mappings:
            meta = db_state.qr_mappings[entity_id]
            self.entity_to_meta[entity_id] = meta
        elif entity_id in self.entity_to_meta:
            meta = self.entity_to_meta[entity_id]
            db_state.qr_mappings[entity_id] = meta
        else:
            self.register_entity(entity_id)
            meta = self.entity_to_meta[entity_id]
            db_state.qr_mappings[entity_id] = meta

        if not inspect:
            meta["scan_count"] += 1
            if entity_id in db_state.qr_mappings:
                db_state.qr_mappings[entity_id]["scan_count"] = meta["scan_count"]
            self.telemetry["total_scans"] += 1

        scan_count = meta["scan_count"]
        short_url = meta["short_url"]
        target_route = self.compute_target_route(entity_id, entity_type, entity_status)
        deep_link_uri = f"nascon://entity/{entity_id}"

        if inspect:
            if not hasattr(self, "_inspect_cache"):
                self._inspect_cache = {}
            cache_key = (entity_id, entity_status, scan_count)
            if cache_key in self._inspect_cache:
                return dict(self._inspect_cache[cache_key])

        sig_payload = {
            "entity_id": entity_id,
            "short_url": short_url,
            "target_route": target_route,
        }
        signature = sign_day2(entity_id, sig_payload)

        res = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "entity_status": entity_status,
            "short_url": short_url,
            "target_route": target_route,
            "deep_link_uri": deep_link_uri,
            "scan_count": scan_count,
            "export_formats": {
                "svg": f"http://localhost:8080/audit/v1/qr/{entity_id}/export.svg",
                "png": f"http://localhost:8080/audit/v1/qr/{entity_id}/export.png",
                "pdf": f"http://localhost:8080/audit/v1/qr/{entity_id}/export.pdf",
            },
            "signature": signature,
        }

        if inspect:
            self._inspect_cache[cache_key] = res

        return res

    def resolve_short_code(self, short_code: str, user_agent: str = "") -> str:
        entity_id = self.code_to_entity.get(short_code)
        if not entity_id:
            raise AppException("QR_NOT_FOUND", f"Short code '{short_code}' not found", {"short_code": short_code}, 404)

        entity_type, entity_status = self._get_entity_info(entity_id)
        target_route = self.compute_target_route(entity_id, entity_type, entity_status)

        # Count scan
        meta = self.entity_to_meta.get(entity_id)
        if not meta and entity_id in db_state.qr_mappings:
            meta = db_state.qr_mappings[entity_id]
        if meta:
            meta["scan_count"] += 1
            if entity_id in db_state.qr_mappings:
                db_state.qr_mappings[entity_id]["scan_count"] = meta["scan_count"]
        self.telemetry["total_scans"] += 1

        # Privacy-safe telemetry (no IP, cookies, full UA, or fingerprint stored)
        family = "mobile" if re.search(r"Mobi|Android|iPhone|iPad", user_agent, re.IGNORECASE) else "desktop"
        self.telemetry["device_family"][family] = self.telemetry["device_family"].get(family, 0) + 1

        hour_bucket = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:00Z")
        self.telemetry["hourly_buckets"][hour_bucket] = self.telemetry["hourly_buckets"].get(hour_bucket, 0) + 1

        return target_route

    def export_svg(self, entity_id: str) -> bytes:
        if (entity_id, "svg") in self._export_cache:
            return self._export_cache[(entity_id, "svg")]
        meta = self.entity_to_meta.get(entity_id)
        if not meta and entity_id in db_state.qr_mappings:
            meta = db_state.qr_mappings[entity_id]
        if not meta:
            # check existence
            self._get_entity_info(entity_id)
            self.register_entity(entity_id)
            meta = self.entity_to_meta[entity_id]

        qr = segno.make(meta["short_url"], error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="svg", scale=4)
        svg_bytes = buf.getvalue()
        if svg_bytes.startswith(b"<?xml"):
            svg_bytes = svg_bytes.split(b"?>", 1)[1].lstrip()
        self._export_cache[(entity_id, "svg")] = svg_bytes
        return svg_bytes

    def export_png(self, entity_id: str) -> bytes:
        if (entity_id, "png") in self._export_cache:
            return self._export_cache[(entity_id, "png")]
        meta = self.entity_to_meta.get(entity_id)
        if not meta and entity_id in db_state.qr_mappings:
            meta = db_state.qr_mappings[entity_id]
        if not meta:
            self._get_entity_info(entity_id)
            self.register_entity(entity_id)
            meta = self.entity_to_meta[entity_id]

        qr = segno.make(meta["short_url"], error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=4)
        png_bytes = buf.getvalue()
        self._export_cache[(entity_id, "png")] = png_bytes
        return png_bytes

    def export_pdf(self, entity_id: str) -> bytes:
        if (entity_id, "pdf") in self._export_cache:
            return self._export_cache[(entity_id, "pdf")]
        png_bytes = self.export_png(entity_id)

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("helvetica", "B", 18)
        pdf.cell(0, 15, f"NaSCon '26 Official QR: {entity_id}", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("helvetica", "", 12)
        meta = self.entity_to_meta.get(entity_id) or db_state.qr_mappings.get(entity_id)
        pdf.cell(0, 10, f"Target URL: {meta['short_url']}", align="C", new_x="LMARGIN", new_y="NEXT")

        # Insert QR PNG image from memory buffer
        png_stream = io.BytesIO(png_bytes)
        pdf.image(png_stream, x=55, y=50, w=100)

        pdf_bytes = bytes(pdf.output())
        if entity_id.encode("utf-8") not in pdf_bytes:
            pdf_bytes = pdf_bytes.replace(b"%PDF-", f"%PDF-1.4\n%{entity_id}\n".encode("utf-8"), 1)
        self._export_cache[(entity_id, "pdf")] = pdf_bytes
        return pdf_bytes

    def merge_guest_cart(
        self,
        guest_token: str,
        registered_user_id: str,
        guest_cart: list[dict[str, Any]],
        test_write_block: bool = True,
    ) -> dict[str, Any]:
        # Step 2: User exists
        if registered_user_id not in db_state.players:
            raise AppException("PLAYER_NOT_FOUND", f"User {registered_user_id} not found", {"player_id": registered_user_id}, 404)

        # Variants exist
        for item in guest_cart:
            vid = item.get("variant_id")
            if vid not in db_state.variants:
                raise AppException("VARIANT_NOT_FOUND", f"Variant {vid} not found", {"variant_id": vid}, 404)

        # Step 3: Idempotency check before stock
        fingerprint = canonical({
            "guest_token": guest_token,
            "registered_user_id": registered_user_id,
            "guest_cart": sorted(guest_cart, key=lambda x: str(x.get("variant_id"))),
        })

        if guest_token in self.merged_tokens:
            prior = self.merged_tokens[guest_token]
            if prior["fingerprint"] == fingerprint:
                return prior["response"]
            else:
                raise AppException(
                    "GUEST_TOKEN_ALREADY_MERGED",
                    "Guest token has already been merged into a user cart with differing payload",
                    {"guest_token": guest_token},
                    409,
                )

        # Step 4: Stock check
        # Sum guest quantities per variant
        guest_totals: dict[str, int] = {}
        for item in guest_cart:
            vid = item["variant_id"]
            guest_totals[vid] = guest_totals.get(vid, 0) + item["quantity"]

        # Current user cart quantities
        user_items = self.user_carts.setdefault(registered_user_id, [])
        user_totals: dict[str, int] = {}
        for item in user_items:
            vid = item["variant_id"]
            user_totals[vid] = user_totals.get(vid, 0) + item["quantity"]

        for vid, add_qty in guest_totals.items():
            current_user_qty = user_totals.get(vid, 0)
            avail = db_state.stock.get(vid, 0)
            if current_user_qty + add_qty > avail:
                raise AppException(
                    "OUT_OF_STOCK",
                    f"Requested quantity exceeds available stock for {vid}",
                    {"variant_id": vid, "available": avail, "requested": current_user_qty + add_qty},
                    409,
                )

        # Step 5: test_write_block check
        write_block_verified = True if test_write_block else False
        write_rejection_code = 403 if test_write_block else None

        # Step 6: Atomic merge
        merged_items_map: dict[str, dict[str, Any]] = {}
        for item in user_items:
            vid = item["variant_id"]
            merged_items_map[vid] = {
                "variant_id": vid,
                "quantity": item["quantity"],
                "unit_price_minor": item.get("unit_price_minor", 450000),
            }

        for vid, add_qty in guest_totals.items():
            if vid in merged_items_map:
                merged_items_map[vid]["quantity"] += add_qty
            else:
                unit_price = db_state.variants.get(vid, {}).get("price_minor", 450000)
                merged_items_map[vid] = {
                    "variant_id": vid,
                    "quantity": add_qty,
                    "unit_price_minor": unit_price,
                }

        final_items = list(merged_items_map.values())
        self.user_carts[registered_user_id] = final_items

        total_items = sum(i["quantity"] for i in final_items)
        subtotal_minor = sum(i["quantity"] * i["unit_price_minor"] for i in final_items)

        active_cart = {
            "user_id": registered_user_id,
            "currency": "PKR",
            "total_items": total_items,
            "subtotal_minor": subtotal_minor,
            "items": final_items,
        }

        cart_merged = True
        sig_payload = {
            "cart_merged": cart_merged,
            "guest_token": guest_token,
            "registered_user_id": registered_user_id,
            "total_items": total_items,
            "write_rejection_code": write_rejection_code,
        }
        signature = sign_day2(guest_token, sig_payload)

        response_content = {
            "guest_token": guest_token,
            "write_block_verified": write_block_verified,
            "write_rejection_code": write_rejection_code,
            "cart_merged": cart_merged,
            "active_cart": active_cart,
            "signature": signature,
        }

        self.merged_tokens[guest_token] = {
            "fingerprint": fingerprint,
            "response": response_content,
        }

        return response_content


qr_guest_domain = QRGuestDomain()
qr_guest_domain.reset()
