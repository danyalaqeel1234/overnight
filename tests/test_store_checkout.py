"""Tests for store checkout and inventory."""
from __future__ import annotations
import base64
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models import db_state

client = TestClient(app)


def setup_function():
    db_state.seed_baseline()


def checkout(data):
    return client.post("/audit/v1/checkout", json=data)


def basic_order(order_id="ord-1", token="tok_success", discount_code=None, qty_m=1, qty_l=0):
    items = []
    if qty_m > 0:
        items.append({"variant_id": "var-jersey-001-M", "quantity": qty_m})
    if qty_l > 0:
        items.append({"variant_id": "var-jersey-001-L", "quantity": qty_l})
    data = {
        "order_id": order_id,
        "customer_id": "cust-1",
        "items": items,
        "payment": {"token": token},
    }
    if discount_code is not None:
        data["discount_code"] = discount_code
    return checkout(data)


class TestSuccessfulCheckout:
    def setup_method(self):
        db_state.seed_baseline()

    def test_basic_success(self):
        r = basic_order()
        assert r.status_code == 201
        d = r.json()
        assert d["status"] == "paid"
        assert d["order_id"] == "ord-1"
        assert d["currency"] == "PKR"
        assert d["subtotal_minor"] == 450000
        assert d["discount_minor"] == 0
        assert d["total_minor"] == 450000

    def test_payment_details(self):
        r = basic_order()
        d = r.json()
        assert d["payment"]["state"] == "captured"
        assert d["payment"]["authorization_id"]
        assert d["payment"]["capture_id"]

    def test_receipt_signature_present(self):
        r = basic_order()
        d = r.json()
        assert "receipt" in d
        assert "signature" in d["receipt"]
        assert len(d["receipt"]["signature"]) == 64  # sha256 hex

    def test_receipt_pdf_base64(self):
        r = basic_order()
        d = r.json()
        pdf_b64 = d["receipt"]["pdf_base64"]
        assert pdf_b64
        # Should be valid base64
        decoded = base64.b64decode(pdf_b64)
        assert len(decoded) > 0

    def test_stock_decremented(self):
        r = client.get("/audit/v1/inventory/var-jersey-001-M")
        assert r.status_code == 200
        before = r.json()["stock"]
        basic_order()
        r2 = client.get("/audit/v1/inventory/var-jersey-001-M")
        assert r2.json()["stock"] == before - 1

    def test_multiple_items(self):
        r = basic_order(qty_m=1, qty_l=2)
        assert r.status_code == 201
        d = r.json()
        assert d["subtotal_minor"] == 450000 * 3

    def test_items_in_response(self):
        r = basic_order()
        d = r.json()
        assert len(d["items"]) == 1
        assert d["items"][0]["variant_id"] == "var-jersey-001-M"
        assert d["items"][0]["unit_price_minor"] == 450000


class TestDiscount:
    def setup_method(self):
        db_state.seed_baseline()

    def test_welcome10_discount(self):
        r = basic_order(discount_code="WELCOME10")
        assert r.status_code == 201
        d = r.json()
        assert d["discount_minor"] == 45000  # 10% of 450000
        assert d["total_minor"] == 405000

    def test_invalid_discount_code(self):
        r = basic_order(discount_code="INVALID")
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_DISCOUNT_CODE"

    def test_no_discount_code(self):
        r = basic_order()
        d = r.json()
        assert d["discount_minor"] == 0


class TestOutOfStock:
    def setup_method(self):
        db_state.seed_baseline()

    def test_out_of_stock(self):
        # M has stock=1, buy 2
        r = checkout({
            "order_id": "ord-oos",
            "customer_id": "cust-1",
            "items": [{"variant_id": "var-jersey-001-M", "quantity": 2}],
            "payment": {"token": "tok_success"},
        })
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "OUT_OF_STOCK"

    def test_stock_not_decremented_on_oos(self):
        r = client.get("/audit/v1/inventory/var-jersey-001-M")
        before = r.json()["stock"]
        checkout({
            "order_id": "ord-oos2",
            "customer_id": "cust-1",
            "items": [{"variant_id": "var-jersey-001-M", "quantity": 999}],
            "payment": {"token": "tok_success"},
        })
        r2 = client.get("/audit/v1/inventory/var-jersey-001-M")
        assert r2.json()["stock"] == before  # unchanged


class TestPaymentDeclined:
    def setup_method(self):
        db_state.seed_baseline()

    def test_payment_declined(self):
        r = basic_order(token="tok_declined")
        assert r.status_code == 402
        assert r.json()["error"]["code"] == "PAYMENT_DECLINED"

    def test_stock_restored_on_decline(self):
        r_inv = client.get("/audit/v1/inventory/var-jersey-001-M")
        before = r_inv.json()["stock"]
        basic_order(token="tok_declined")
        r_inv2 = client.get("/audit/v1/inventory/var-jersey-001-M")
        assert r_inv2.json()["stock"] == before  # stock restored

    def test_payment_capture_fail(self):
        r = basic_order(token="tok_capture_fail")
        assert r.status_code == 402
        assert r.json()["error"]["code"] == "PAYMENT_CAPTURE_FAILED"

    def test_stock_restored_on_capture_fail(self):
        r_inv = client.get("/audit/v1/inventory/var-jersey-001-M")
        before = r_inv.json()["stock"]
        basic_order(token="tok_capture_fail")
        r_inv2 = client.get("/audit/v1/inventory/var-jersey-001-M")
        assert r_inv2.json()["stock"] == before


class TestVariantNotFound:
    def test_variant_not_found(self):
        r = checkout({
            "order_id": "ord-bad-var",
            "customer_id": "cust-1",
            "items": [{"variant_id": "var-nonexistent", "quantity": 1}],
            "payment": {"token": "tok_success"},
        })
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "VARIANT_NOT_FOUND"


class TestIdempotency:
    def setup_method(self):
        db_state.seed_baseline()

    def test_same_order_id_same_body(self):
        data = {
            "order_id": "ord-idem",
            "customer_id": "cust-1",
            "items": [{"variant_id": "var-jersey-001-M", "quantity": 1}],
            "payment": {"token": "tok_success"},
        }
        r1 = checkout(data)
        assert r1.status_code == 201
        r2 = checkout(data)
        assert r2.status_code == 200
        assert r1.json() == r2.json()

    def test_stock_not_double_decremented(self):
        data = {
            "order_id": "ord-idem2",
            "customer_id": "cust-1",
            "items": [{"variant_id": "var-jersey-001-M", "quantity": 1}],
            "payment": {"token": "tok_success"},
        }
        checkout(data)
        inv_after_first = client.get("/audit/v1/inventory/var-jersey-001-M").json()["stock"]
        checkout(data)
        inv_after_second = client.get("/audit/v1/inventory/var-jersey-001-M").json()["stock"]
        assert inv_after_first == inv_after_second

    def test_same_order_id_different_body(self):
        data = {
            "order_id": "ord-idem3",
            "customer_id": "cust-1",
            "items": [{"variant_id": "var-jersey-001-M", "quantity": 1}],
            "payment": {"token": "tok_success"},
        }
        checkout(data)
        data2 = {**data, "customer_id": "cust-99"}
        r2 = checkout(data2)
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "DUPLICATE_ORDER_ID"


class TestInventory:
    def setup_method(self):
        db_state.seed_baseline()

    def test_get_inventory(self):
        r = client.get("/audit/v1/inventory/var-jersey-001-M")
        assert r.status_code == 200
        d = r.json()
        assert d["variant_id"] == "var-jersey-001-M"
        assert "stock" in d
        assert "reserved" in d

    def test_get_inventory_not_found(self):
        r = client.get("/audit/v1/inventory/var-nonexistent")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "VARIANT_NOT_FOUND"

    def test_inventory_after_purchase(self):
        r1 = client.get("/audit/v1/inventory/var-jersey-001-L")
        before = r1.json()["stock"]
        basic_order(order_id="ord-inv-l", qty_m=0, qty_l=1)
        r2 = client.get("/audit/v1/inventory/var-jersey-001-L")
        assert r2.json()["stock"] == before - 1


class TestReceiptPayload:
    def setup_method(self):
        db_state.seed_baseline()

    def test_receipt_payload_fields(self):
        r = basic_order()
        d = r.json()
        payload = d["receipt"]["payload"]
        assert payload["order_id"] == "ord-1"
        assert payload["currency"] == "PKR"
        assert "paid_at" in payload
        assert payload["subtotal_minor"] == 450000

    def test_receipt_signature_verifiable(self):
        from app.core.crypto import sign, canonical
        from app.core.config import DAY1_SALT
        r = basic_order(order_id="ord-sig-test")
        d = r.json()
        receipt = d["receipt"]
        expected_sig = sign(DAY1_SALT, "ord-sig-test", receipt["payload"])
        assert receipt["signature"] == expected_sig
