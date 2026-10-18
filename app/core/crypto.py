import hmac
import hashlib
import json
from typing import Any


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(salt: str, id_: str, payload: Any) -> str:
    msg = (id_ + "|" + canonical(payload)).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), msg, hashlib.sha256).hexdigest()


import os

def sign_day2(id_: str, payload: Any) -> str:
    salt = os.environ.get("DAY2_SALT", "")
    return sign(salt, id_, payload)


def lots_key(seed: int, league_id: str, team_id: str) -> str:
    return hashlib.sha256(f"{seed}|{league_id}|{team_id}".encode("utf-8")).hexdigest()
