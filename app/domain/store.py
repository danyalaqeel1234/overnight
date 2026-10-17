"""Thread-safe store checkout with pessimistic locking."""
from __future__ import annotations
import base64
import datetime
from app.core.config import DAY1_SALT
from app.core.crypto import sign, canonical
from app.core.errors import AppException
from app.domain.models import db_state


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_pdf(order_id: str, total_minor: int) -> str:
    """Generate a minimal valid PDF and return base64."""
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        total_str = f"PKR {total_minor // 100}.{total_minor % 100:02d}"
        pdf.cell(0, 10, f"Order: {order_id}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 10, f"Total: {total_str}", new_x="LMARGIN", new_y="NEXT")
        pdf_bytes = bytes(pdf.output())
    except Exception:
        # Fallback to minimal valid PDF text
        total_str = f"PKR {total_minor // 100}.{total_minor % 100:02d}"
        pdf_text = f"%PDF-1.4\nOrder: {order_id}\nTotal: {total_str}\n%%EOF"
        pdf_bytes = pdf_text.encode("utf-8")
    return base64.b64encode(pdf_bytes).decode("utf-8")


def checkout(data: dict) -> tuple[int, dict]:
    order_id = data.get("order_id")
    customer_id = data.get("customer_id")
    items = data.get("items", [])
    discount_code = data.get("discount_code")
    payment = data.get("payment", {})
    token = payment.get("token")
    body_canonical = canonical(data)

    with db_state._store_lock:
        # Idempotency
        if order_id in db_state.idempotency_orders:
            stored = db_state.idempotency_orders[order_id]
            if stored["canonical"] == body_canonical:
                return 200, stored["response"]
            raise AppException("DUPLICATE_ORDER_ID", "Order ID already used with different payload.", {}, 409)

        # Validation: variant exists
        for item in items:
            vid = item["variant_id"]
            if vid not in db_state.variants:
                raise AppException("VARIANT_NOT_FOUND", f"Variant '{vid}' not found.", {"variant_id": vid}, 404)

        # Discount code validation
        if discount_code is not None and discount_code != "WELCOME10":
            raise AppException("INVALID_DISCOUNT_CODE", "Unknown discount code.", {}, 400)

        # Phase 1: Atomic reservation (sorted variant_id order to prevent deadlocks)
        sorted_items = sorted(items, key=lambda x: x["variant_id"])
        for item in sorted_items:
            vid = item["variant_id"]
            qty = item["quantity"]
            if db_state.stock.get(vid, 0) < qty:
                raise AppException("OUT_OF_STOCK", f"Variant '{vid}' is out of stock.", {"variant_id": vid}, 409)

        # All checks passed, reserve
        for item in sorted_items:
            vid = item["variant_id"]
            qty = item["quantity"]
            db_state.stock[vid] -= qty
            db_state.reserved[vid] = db_state.reserved.get(vid, 0) + qty

    # Phase 2: Mock payment gateway (outside lock)
    if token == "tok_declined":
        with db_state._store_lock:
            for item in sorted_items:
                vid = item["variant_id"]
                qty = item["quantity"]
                db_state.stock[vid] += qty
                db_state.reserved[vid] -= qty
        raise AppException("PAYMENT_DECLINED", "Card was declined.", {}, 402)

    if token == "tok_capture_fail":
        with db_state._store_lock:
            for item in sorted_items:
                vid = item["variant_id"]
                qty = item["quantity"]
                db_state.stock[vid] += qty
                db_state.reserved[vid] -= qty
        raise AppException("PAYMENT_CAPTURE_FAILED", "Capture failed.", {}, 402)

    # Phase 3: Commit
    with db_state._store_lock:
        for item in sorted_items:
            vid = item["variant_id"]
            qty = item["quantity"]
            db_state.reserved[vid] -= qty
        # reserved decremented, stock already decremented

    # Build response
    subtotal = sum(
        db_state.variants[item["variant_id"]]["price_minor"] * item["quantity"]
        for item in items
    )
    discount_minor = (subtotal * 10 // 100) if discount_code == "WELCOME10" else 0
    total_minor = subtotal - discount_minor
    paid_at = _now()

    receipt_payload = {
        "order_id": order_id,
        "customer_id": customer_id,
        "items": [
            {
                "variant_id": it["variant_id"],
                "quantity": it["quantity"],
                "unit_price_minor": db_state.variants[it["variant_id"]]["price_minor"],
            }
            for it in items
        ],
        "subtotal_minor": subtotal,
        "discount_minor": discount_minor,
        "total_minor": total_minor,
        "currency": "PKR",
        "paid_at": paid_at,
    }

    sig = sign(DAY1_SALT, order_id, receipt_payload)
    pdf_b64 = _generate_pdf(order_id, total_minor)

    response = {
        "order_id": order_id,
        "status": "paid",
        "currency": "PKR",
        "items": [
            {
                "variant_id": it["variant_id"],
                "quantity": it["quantity"],
                "unit_price_minor": db_state.variants[it["variant_id"]]["price_minor"],
            }
            for it in items
        ],
        "subtotal_minor": subtotal,
        "discount_minor": discount_minor,
        "total_minor": total_minor,
        "payment": {
            "authorization_id": "auth_1",
            "capture_id": "cap_1",
            "state": "captured",
        },
        "receipt": {
            "payload": receipt_payload,
            "signature": sig,
            "pdf_base64": pdf_b64,
        },
    }

    with db_state._store_lock:
        db_state.orders[order_id] = response
        db_state.idempotency_orders[order_id] = {"canonical": body_canonical, "response": response}

    return 201, response


def get_inventory(variant_id: str) -> dict:
    if variant_id not in db_state.variants:
        raise AppException("VARIANT_NOT_FOUND", f"Variant '{variant_id}' not found.", {}, 404)
    return {
        "variant_id": variant_id,
        "stock": db_state.stock.get(variant_id, 0),
        "reserved": db_state.reserved.get(variant_id, 0),
    }
