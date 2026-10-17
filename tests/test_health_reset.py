"""Integration tests for /health and /audit/v1/reset."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_reset_default():
    resp = client.post("/audit/v1/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reset_complete"
    assert body["seed"] == 42
    assert set(body["sports"]) == {"football", "basketball", "cricket", "esports"}
    assert set(body["tenants"]) == {"tenant-alpha", "tenant-beta"}
    assert body["stock"]["var-jersey-001-M"] == 1
    assert body["stock"]["var-jersey-001-L"] == 5


def test_reset_with_seed_and_stock():
    resp = client.post(
        "/audit/v1/reset",
        json={"seed": 99, "stock": {"var-jersey-001-M": 10, "var-jersey-001-L": 20}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["seed"] == 99
    assert body["stock"]["var-jersey-001-M"] == 10
    assert body["stock"]["var-jersey-001-L"] == 20


def test_reset_idempotent():
    r1 = client.post("/audit/v1/reset", json={"seed": 42})
    r2 = client.post("/audit/v1/reset", json={"seed": 42})
    assert r1.json()["sports"] == r2.json()["sports"]
    assert r1.json()["tenants"] == r2.json()["tenants"]


def test_health_after_reset():
    client.post("/audit/v1/reset")
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
