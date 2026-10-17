"""
Unit & Concurrency Test Suite: Store Concurrency & Inventory (Section 5.12 & NFR-3)
Tests:
1. 20-thread concurrent burst on 1 remaining stock item (exactly one 201, nineteen 409 OUT_OF_STOCK, zero oversell).
2. Gateway decline tests: tok_declined / tok_capture_fail -> 402 with stock rollback.
3. Discount code WELCOME10 (10% floor paisa) vs invalid code 400 INVALID_DISCOUNT_CODE.
"""

import threading
import time
import base64
import hmac
import hashlib
import json
import pytest
from typing import List, Dict, Any

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def sign_payload(salt: str, id_: str, payload_obj) -> str:
    msg = (id_ + "|" + canonical_json(payload_obj)).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()


class StoreConcurrencyEngine:
    """
    In-process concurrency-safe merchandise store engine.
    Implements two-phase row-level pessimistic locking matching Section 5.12.
    """
    def __init__(self, salt: str = "T09D1271f28b2611"):
        self.lock = threading.Lock()
        self.salt = salt
        self.inventory: Dict[str, Dict[str, int]] = {
            "var-jersey-001-M": {"stock": 1, "reserved": 0, "price": 450000},
            "var-jersey-001-L": {"stock": 5, "reserved": 0, "price": 450000},
        }
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.order_bodies: Dict[str, str] = {}

    def reset_stock(self, stock_map: Dict[str, int]):
        with self.lock:
            self.orders.clear()
            self.order_bodies.clear()
            for vid, qty in stock_map.items():
                self.inventory[vid] = {"stock": qty, "reserved": 0, "price": 450000}

    def checkout(self, req: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        order_id = req.get("order_id")
        items = req.get("items", [])
        payment = req.get("payment", {})
        token = payment.get("token")
        discount_code = req.get("discount_code")

        req_canon = canonical_json(req)

        with self.lock:
            # 1. Idempotency
            if order_id in self.orders:
                if self.order_bodies[order_id] == req_canon:
                    return 200, self.orders[order_id]
                return 409, {"error": {"code": "DUPLICATE_ORDER_ID", "message": "Duplicate ID", "details": {}}}

            # 2. Validation
            if not order_id or not items:
                return 400, {"error": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"fields": ["order_id"]}}}

            for item in items:
                vid = item.get("variant_id")
                if vid not in self.inventory:
                    return 404, {"error": {"code": "VARIANT_NOT_FOUND", "message": f"Variant {vid} not found", "details": {"variant_id": vid}}}

            # Discount validation: Section 5.12 explicitly states only WELCOME10 is valid
            if discount_code is not None and discount_code != "WELCOME10":
                return 400, {"error": {"code": "INVALID_DISCOUNT_CODE", "message": "Unknown discount code", "details": {}}}

            # 3. Two-phase reservation: Check and decrement stock atomically
            for item in items:
                vid = item["variant_id"]
                qty = item["quantity"]
                if self.inventory[vid]["stock"] < qty:
                    return 409, {
                        "error": {
                            "code": "OUT_OF_STOCK",
                            "message": f"Variant {vid} has no stock left.",
                            "details": {"variant_id": vid}
                        }
                    }

            for item in items:
                vid = item["variant_id"]
                qty = item["quantity"]
                self.inventory[vid]["stock"] -= qty
                self.inventory[vid]["reserved"] += qty

        # 4. Mock Gateway Phase (outside mutex lock)
        if token == "tok_declined":
            with self.lock:
                for item in items:
                    self.inventory[item["variant_id"]]["stock"] += item["quantity"]
                    self.inventory[item["variant_id"]]["reserved"] -= item["quantity"]
            return 402, {"error": {"code": "PAYMENT_DECLINED", "message": "Card declined.", "details": {}}}

        if token == "tok_capture_fail":
            with self.lock:
                for item in items:
                    self.inventory[item["variant_id"]]["stock"] += item["quantity"]
                    self.inventory[item["variant_id"]]["reserved"] -= item["quantity"]
            return 402, {"error": {"code": "PAYMENT_CAPTURE_FAILED", "message": "Capture failed.", "details": {}}}

        # 5. Success Phase: Commit reservation, generate signed receipt & PDF
        subtotal = sum(self.inventory[item["variant_id"]]["price"] * item["quantity"] for item in items)
        discount = (subtotal * 10 // 100) if discount_code == "WELCOME10" else 0
        total = subtotal - discount
        paid_at = "2026-10-17T11:20:05Z"

        receipt_payload = {
            "order_id": order_id,
            "customer_id": req.get("customer_id", "cust-001"),
            "items": [{"variant_id": it["variant_id"], "quantity": it["quantity"], "unit_price_minor": self.inventory[it["variant_id"]]["price"]} for it in items],
            "subtotal_minor": subtotal,
            "discount_minor": discount,
            "total_minor": total,
            "currency": "PKR",
            "paid_at": paid_at
        }

        sig = sign_payload(self.salt, order_id, receipt_payload)
        pdf_text = f"%PDF-1.4\nOrder: {order_id}\nTotal: PKR {total // 100}.{total % 100:02d}\n%%EOF"
        pdf_b64 = base64.b64encode(pdf_text.encode("utf-8")).decode("utf-8")

        response_body = {
            "order_id": order_id,
            "status": "paid",
            "currency": "PKR",
            "items": receipt_payload["items"],
            "subtotal_minor": subtotal,
            "discount_minor": discount,
            "total_minor": total,
            "payment": {"authorization_id": "auth_1", "capture_id": "cap_1", "state": "captured"},
            "receipt": {
                "payload": receipt_payload,
                "signature": sig,
                "pdf_base64": pdf_b64
            }
        }

        with self.lock:
            for item in items:
                self.inventory[item["variant_id"]]["reserved"] -= item["quantity"]
            self.orders[order_id] = response_body
            self.order_bodies[order_id] = req_canon

        return 201, response_body

    def get_inventory(self, variant_id: str) -> tuple[int, Dict[str, Any]]:
        with self.lock:
            if variant_id not in self.inventory:
                return 404, {"error": {"code": "VARIANT_NOT_FOUND", "message": "Not found", "details": {}}}
            inv = self.inventory[variant_id]
            return 200, {"variant_id": variant_id, "stock": inv["stock"], "reserved": inv["reserved"]}


class TestStoreConcurrency:
    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = StoreConcurrencyEngine()

    def test_20_thread_concurrent_burst_on_1_stock(self):
        """
        Assert 20 concurrent threads buying 1 stock item:
        - Exactly one 201 Created
        - Exactly nineteen 409 OUT_OF_STOCK
        - Zero overselling: final stock = 0, reserved = 0
        """
        variant_id = "var-jersey-001-M"
        self.engine.reset_stock({variant_id: 1})

        barrier = threading.Barrier(20)
        results = [None] * 20

        def worker(idx: int):
            req = {
                "order_id": f"ord-burst-{idx:03d}",
                "customer_id": f"cust-{idx:03d}",
                "items": [{"variant_id": variant_id, "quantity": 1}],
                "discount_code": None,
                "payment": {"token": "tok_success"}
            }
            barrier.wait()
            status, body = self.engine.checkout(req)
            results[idx] = (status, body)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        statuses = [r[0] for r in results]
        assert statuses.count(201) == 1, f"Expected 1 success (201), got {statuses.count(201)}"
        assert statuses.count(409) == 19, f"Expected 19 out of stock (409), got {statuses.count(409)}"

        # Final stock check
        inv_status, inv_body = self.engine.get_inventory(variant_id)
        assert inv_status == 200
        assert inv_body["stock"] == 0
        assert inv_body["reserved"] == 0

    def test_gateway_decline_and_stock_rollback(self):
        """
        Assert gateway failure rollbacks:
        tok_declined -> 402 PAYMENT_DECLINED
        tok_capture_fail -> 402 PAYMENT_CAPTURE_FAILED
        Both restore reserved stock back to stock.
        """
        variant_id = "var-jersey-001-M"
        self.engine.reset_stock({variant_id: 1})

        # Test tok_declined
        status1, body1 = self.engine.checkout({
            "order_id": "ord-dec-1",
            "items": [{"variant_id": variant_id, "quantity": 1}],
            "payment": {"token": "tok_declined"}
        })
        assert status1 == 402
        assert body1["error"]["code"] == "PAYMENT_DECLINED"

        # Verify stock restored
        _, inv1 = self.engine.get_inventory(variant_id)
        assert inv1["stock"] == 1
        assert inv1["reserved"] == 0

        # Test tok_capture_fail
        status2, body2 = self.engine.checkout({
            "order_id": "ord-cap-fail",
            "items": [{"variant_id": variant_id, "quantity": 1}],
            "payment": {"token": "tok_capture_fail"}
        })
        assert status2 == 402
        assert body2["error"]["code"] == "PAYMENT_CAPTURE_FAILED"

        # Verify stock restored
        _, inv2 = self.engine.get_inventory(variant_id)
        assert inv2["stock"] == 1
        assert inv2["reserved"] == 0

    def test_discount_codes_welcome10_vs_invalid(self):
        """
        Assert discount code validation:
        - WELCOME10: computes floor(subtotal * 10 / 100)
        - Invalid code: returns 400 INVALID_DISCOUNT_CODE
        """
        variant_id = "var-jersey-001-L"
        self.engine.reset_stock({variant_id: 5})

        # Valid WELCOME10
        status1, body1 = self.engine.checkout({
            "order_id": "ord-disc-valid",
            "items": [{"variant_id": variant_id, "quantity": 1}],
            "discount_code": "WELCOME10",
            "payment": {"token": "tok_success"}
        })
        assert status1 == 201
        assert body1["subtotal_minor"] == 450000
        assert body1["discount_minor"] == 45000
        assert body1["total_minor"] == 405000

        # Invalid discount code
        status2, body2 = self.engine.checkout({
            "order_id": "ord-disc-invalid",
            "items": [{"variant_id": variant_id, "quantity": 1}],
            "discount_code": "SUMMER50",
            "payment": {"token": "tok_success"}
        })
        assert status2 == 400
        assert body2["error"]["code"] == "INVALID_DISCOUNT_CODE"
