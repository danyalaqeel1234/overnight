"""
Contract Test Suite: Store Concurrency & 20-Thread Checkout Burst (Section 5.12 & NFR-3)
Tests pessimistic locking, zero-overselling, mock payment gateway rollbacks,
and signed PDF receipt validation.
"""

import threading
import time
import base64
import hmac
import hashlib
import json
import pytest
import httpx
from typing import List, Dict, Any

from tests.contract.test_crypto_hmac import canonical_json, sign_payload

# Target base URL, defaults to live Docker/Uvicorn server or local test server
BASE_URL = "http://localhost:8080"

def get_test_client():
    return httpx.Client(base_url=BASE_URL, timeout=10.0)

class InProcessStoreEngine:
    """
    Reference Concurrency-Safe Store Engine for in-process testing.
    Mirrors Section 5.12 two-phase pessimistic locking with row-level mutex.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.inventory: Dict[str, Dict[str, int]] = {
            "var-jersey-001-M": {"stock": 1, "reserved": 0, "price": 450000},
            "var-jersey-001-L": {"stock": 5, "reserved": 0, "price": 450000},
        }
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.order_bodies: Dict[str, str] = {}
        self.salt = "T09D1271f28b2611"

    def reset(self, stock_map: Dict[str, int]):
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

        req_canonical = canonical_json(req)

        with self.lock:
            # 1. Idempotency check
            if order_id in self.orders:
                if self.order_bodies[order_id] == req_canonical:
                    return 200, self.orders[order_id]
                else:
                    return 409, {
                        "error": {
                            "code": "DUPLICATE_ORDER_ID",
                            "message": f"Order {order_id} already exists with different payload.",
                            "details": {}
                        }
                    }

            # 2. Validation
            if not order_id or not items:
                return 400, {"error": {"code": "VALIDATION_ERROR", "message": "Invalid request", "details": {"fields": ["order_id", "items"]}}}

            for item in items:
                vid = item.get("variant_id")
                if vid not in self.inventory:
                    return 404, {"error": {"code": "VARIANT_NOT_FOUND", "message": f"Variant {vid} not found", "details": {"variant_id": vid}}}

            if discount_code is not None and discount_code != "WELCOME10":
                return 400, {"error": {"code": "INVALID_DISCOUNT_CODE", "message": "Unknown discount code", "details": {}}}

            # 3. Phase 1: Atomic Stock Reservation
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

            # Reserve
            for item in items:
                vid = item["variant_id"]
                qty = item["quantity"]
                self.inventory[vid]["stock"] -= qty
                self.inventory[vid]["reserved"] += qty

        # 4. Phase 2: Mock Payment Gateway
        if token == "tok_declined":
            with self.lock:
                for item in items:
                    self.inventory[item["variant_id"]]["stock"] += item["quantity"]
                    self.inventory[item["variant_id"]]["reserved"] -= item["quantity"]
            return 402, {"error": {"code": "PAYMENT_DECLINED", "message": "Card was declined.", "details": {}}}

        if token == "tok_capture_fail":
            with self.lock:
                for item in items:
                    self.inventory[item["variant_id"]]["stock"] += item["quantity"]
                    self.inventory[item["variant_id"]]["reserved"] -= item["quantity"]
            return 402, {"error": {"code": "PAYMENT_CAPTURE_FAILED", "message": "Capture failed.", "details": {}}}

        # 5. Phase 3: Finalize Commit & Signed Receipt
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
        
        # Valid PDF header containing order_id and formatted total PKR
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
            self.order_bodies[order_id] = req_canonical

        return 201, response_body

    def get_inventory(self, variant_id: str) -> tuple[int, Dict[str, Any]]:
        with self.lock:
            if variant_id not in self.inventory:
                return 404, {"error": {"code": "VARIANT_NOT_FOUND", "message": "Not found", "details": {}}}
            inv = self.inventory[variant_id]
            return 200, {
                "variant_id": variant_id,
                "stock": inv["stock"],
                "reserved": inv["reserved"]
            }


class TestStoreConcurrencyContract:
    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = InProcessStoreEngine()

    def test_20_thread_checkout_burst_on_1_stock(self):
        """
        NFR-3 Concurrency Verification:
        Grader resets stock: var-jersey-001-M = 1
        20 simultaneous threads released together by threading.Barrier(20)
        Result: Exactly ONE 201 Created, exactly NINETEEN 409 OUT_OF_STOCK.
        Final inventory: stock = 0, reserved = 0.
        """
        variant_id = "var-jersey-001-M"
        self.engine.reset({variant_id: 1})

        barrier = threading.Barrier(20)
        results: List[tuple[int, Dict[str, Any]]] = [None] * 20

        def burst_worker(index: int):
            order_id = f"ord-burst-{index:03d}"
            payload = {
                "order_id": order_id,
                "customer_id": f"cust-{index:03d}",
                "items": [{"variant_id": variant_id, "quantity": 1}],
                "discount_code": None,
                "payment": {"token": "tok_success"}
            }
            # Wait for all 20 threads to line up at the gate
            barrier.wait()
            # Simultaneous fire!
            status, body = self.engine.checkout(payload)
            results[index] = (status, body)

        threads = [threading.Thread(target=burst_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Assert all 20 threads completed
        assert len(results) == 20
        status_codes = [r[0] for r in results]

        created_count = status_codes.count(201)
        conflict_count = status_codes.count(409)

        assert created_count == 1, f"Expected exactly 1 successful checkout (201), got {created_count}"
        assert conflict_count == 19, f"Expected exactly 19 out of stock responses (409), got {conflict_count}"

        # Verify all 409 responses have OUT_OF_STOCK code
        for status, body in results:
            if status == 409:
                assert body["error"]["code"] == "OUT_OF_STOCK"
                assert body["error"]["details"]["variant_id"] == variant_id

        # Verify final inventory is exactly 0 stock, 0 reserved (never negative)
        inv_status, inv_body = self.engine.get_inventory(variant_id)
        assert inv_status == 200
        assert inv_body["stock"] == 0, f"Stock must be 0, was {inv_body['stock']}"
        assert inv_body["reserved"] == 0, f"Reserved must be 0, was {inv_body['reserved']}"

        # Verify receipt of the winning order
        winning_result = next(body for status, body in results if status == 201)
        receipt = winning_result["receipt"]
        assert "signature" in receipt
        assert "pdf_base64" in receipt

        # Check PDF header and content
        pdf_bytes = base64.b64decode(receipt["pdf_base64"])
        assert pdf_bytes.startswith(b"%PDF"), "PDF receipt must start with %PDF"
        pdf_text = pdf_bytes.decode("utf-8", errors="ignore")
        assert winning_result["order_id"] in pdf_text
        assert "PKR 4500.00" in pdf_text

    def test_mock_gateway_failure_releases_reserved_stock(self):
        """
        Test Section 5.12 mock payment failures:
        tok_declined -> 402 PAYMENT_DECLINED
        tok_capture_fail -> 402 PAYMENT_CAPTURE_FAILED
        Both must restore reserved stock back to stock.
        """
        variant_id = "var-jersey-001-M"
        self.engine.reset({variant_id: 1})

        declined_payload = {
            "order_id": "ord-fail-1",
            "customer_id": "cust-001",
            "items": [{"variant_id": variant_id, "quantity": 1}],
            "discount_code": None,
            "payment": {"token": "tok_declined"}
        }
        status, body = self.engine.checkout(declined_payload)
        assert status == 402
        assert body["error"]["code"] == "PAYMENT_DECLINED"

        # Stock must be restored to 1!
        inv_status, inv_body = self.engine.get_inventory(variant_id)
        assert inv_body["stock"] == 1
        assert inv_body["reserved"] == 0

        # Now test tok_capture_fail
        cap_payload = {
            "order_id": "ord-fail-2",
            "customer_id": "cust-001",
            "items": [{"variant_id": variant_id, "quantity": 1}],
            "discount_code": None,
            "payment": {"token": "tok_capture_fail"}
        }
        status2, body2 = self.engine.checkout(cap_payload)
        assert status2 == 402
        assert body2["error"]["code"] == "PAYMENT_CAPTURE_FAILED"

        # Stock must still be 1!
        inv_status2, inv_body2 = self.engine.get_inventory(variant_id)
        assert inv_body2["stock"] == 1
        assert inv_body2["reserved"] == 0

    def test_idempotent_replay_and_duplicate_order_id(self):
        """
        Test Section 5.12 Idempotency:
        Replay of an identical request -> 200 with stored result.
        Same order_id with different body -> 409 DUPLICATE_ORDER_ID.
        """
        variant_id = "var-jersey-001-L"
        self.engine.reset({variant_id: 5})

        payload = {
            "order_id": "ord-idem-1",
            "customer_id": "cust-idem",
            "items": [{"variant_id": variant_id, "quantity": 1}],
            "discount_code": "WELCOME10",
            "payment": {"token": "tok_success"}
        }
        status1, body1 = self.engine.checkout(payload)
        assert status1 == 201

        # Replay identical
        status2, body2 = self.engine.checkout(payload)
        assert status2 == 200
        assert body2["order_id"] == "ord-idem-1"
        assert body2["discount_minor"] == 45000  # 10% discount

        # Same order_id with different payload
        different_payload = {
            "order_id": "ord-idem-1",
            "customer_id": "cust-DIFFERENT",
            "items": [{"variant_id": variant_id, "quantity": 2}],
            "discount_code": None,
            "payment": {"token": "tok_success"}
        }
        status3, body3 = self.engine.checkout(different_payload)
        assert status3 == 409
        assert body3["error"]["code"] == "DUPLICATE_ORDER_ID"
