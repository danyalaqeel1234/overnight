"""Unit tests for crypto module."""
import pytest
from app.core.crypto import canonical, lots_key, sign


def test_canonical_sorts_keys():
    result = canonical({"b": 2, "a": 1})
    assert result == '{"a":1,"b":2}'


def test_canonical_nested():
    result = canonical({"z": {"b": 2, "a": 1}, "a": 0})
    assert result == '{"a":0,"z":{"a":1,"b":2}}'


def test_canonical_array_order_preserved():
    result = canonical({"arr": [3, 1, 2]})
    assert result == '{"arr":[3,1,2]}'


def test_canonical_bool_null():
    result = canonical({"x": True, "y": False, "z": None})
    assert result == '{"x":true,"y":false,"z":null}'


def test_canonical_int_no_decimal():
    result = canonical({"n": 42})
    assert result == '{"n":42}'


def test_sign_vector1():
    """Test vector 1: salt demo-salt, id evt-1, payload {"team_id":"t1","event_type":"goal"}"""
    sig = sign("demo-salt", "evt-1", {"team_id": "t1", "event_type": "goal"})
    assert sig == "972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501"


def test_sign_length():
    sig = sign("any-salt", "id-1", {"key": "val"})
    assert len(sig) == 64
    assert sig == sig.lower()


def test_lots_key_vector2_t1():
    key = lots_key(42, "lg-1", "t1")
    assert key == "0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293"


def test_lots_key_vector2_t2():
    key = lots_key(42, "lg-1", "t2")
    assert key == "e3e3a14e22727f936e1f288cf5d02a8a9362b1da13c5432725fc10b2c7955dd9"


def test_lots_key_t3():
    key = lots_key(42, "lg-1", "t3")
    assert key == "c8f28e3c2f1eb6c4f636b4f57050e3362a2b39c07fda9b61742a26dd20397028"
