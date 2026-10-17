"""
Contract Test Suite: Cryptographic Signatures & Canonical JSON (Section 5.3 & Appendix A)
Tests Appendix A Test Vector 1 (HMAC-SHA256) and Test Vector 2 (Drawing of Lots SHA256).
"""

import hmac
import hashlib
import json
import pytest

def canonical_json(obj) -> str:
    """
    Canonical JSON generator matching Section 5.3:
    Recursively sorted object keys, no whitespace (separators=(',', ':')),
    UTF-8, non-ASCII unescaped, true/false/null lowercase.
    """
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def sign_payload(salt: str, id_: str, payload_obj) -> str:
    """
    Exact HMAC-SHA256 recipe matching Section 5.3 & Appendix A:
    sign(salt, id, payload) = hmac_sha256(salt_utf8, (id + "|" + canonical(payload)).utf8).hexdigest()
    """
    msg = (id_ + "|" + canonical_json(payload_obj)).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def lots_key(seed: int, league_id: str, team_id: str) -> str:
    """
    Drawing of lots key matching Section 5.10 & Appendix A:
    sha256(f"{seed}|{league_id}|{team_id}".encode("utf-8")).hexdigest()
    """
    return hashlib.sha256(f"{seed}|{league_id}|{team_id}".encode("utf-8")).hexdigest()


class TestCryptoHMACContract:
    def test_appendix_a_vector_1_hmac_signature(self):
        """
        Verify Appendix A Test Vector 1:
        Salt: 'demo-salt'
        ID: 'evt-1'
        Payload: {"team_id":"t1","event_type":"goal"}
        Expected canonical: {"event_type":"goal","team_id":"t1"}
        Expected signature: 972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501
        """
        salt = "demo-salt"
        event_id = "evt-1"
        payload = {"team_id": "t1", "event_type": "goal"}

        canonical_str = canonical_json(payload)
        assert canonical_str == '{"event_type":"goal","team_id":"t1"}', (
            f"Canonical JSON mismatch: got {canonical_str}"
        )

        signature = sign_payload(salt, event_id, payload)
        expected_sig = "972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501"

        assert signature == expected_sig, (
            f"Signature mismatch!\nExpected: {expected_sig}\nActual:   {signature}"
        )

    def test_appendix_a_vector_2_drawing_of_lots(self):
        """
        Verify Appendix A Test Vector 2:
        Seed: 42
        League: 'lg-1'
        Teams: t1, t2, t3
        Expected hashes:
          t1 -> 0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293
          t2 -> e3e3a14e22727f936e1f288cf5d02a8a9362b1da13c5432725fc10b2c7955dd9
          t3 -> c8f28e3c2f1eb6c4f636b4f57050e3362a2b39c07fda9b61742a26dd20397028
        Sorted order (ascending by key, first = best): t1, t3, t2
        """
        seed = 42
        league_id = "lg-1"

        h_t1 = lots_key(seed, league_id, "t1")
        h_t2 = lots_key(seed, league_id, "t2")
        h_t3 = lots_key(seed, league_id, "t3")

        assert h_t1 == "0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293"
        assert h_t2 == "e3e3a14e22727f936e1f288cf5d02a8a9362b1da13c5432725fc10b2c7955dd9"
        assert h_t3 == "c8f28e3c2f1eb6c4f636b4f57050e3362a2b39c07fda9b61742a26dd20397028"

        teams = ["t1", "t2", "t3"]
        sorted_teams = sorted(teams, key=lambda t: lots_key(seed, league_id, t))
        assert sorted_teams == ["t1", "t3", "t2"]

    def test_canonical_json_nested_and_unicode_compliance(self):
        """
        Test canonical JSON sorts nested keys and handles Unicode and boolean literals
        without escaping or whitespace.
        """
        nested_payload = {
            "z": 1,
            "a": {
                "b": True,
                "a": False,
                "c": None,
                "msg": "NaSCon ’26"
            },
            "list": [3, 1, 2]
        }
        res = canonical_json(nested_payload)
        # Verify keys sorted: 'a' before 'list' before 'z'
        # Inside 'a': 'a' before 'b' before 'c' before 'msg'
        # Array order preserved: [3, 1, 2]
        expected = '{"a":{"a":false,"b":true,"c":null,"msg":"NaSCon ’26"},"list":[3,1,2],"z":1}'
        assert res == expected
