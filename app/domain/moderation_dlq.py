from __future__ import annotations
import re
import uuid
import datetime
from typing import Any
from app.core.errors import AppException
from app.core.crypto import sign_day2


# Precompiled regexes for high performance
RE_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff\u2060]")
RE_SEPARATORS = re.compile(r"[_.\-*]")
RE_FLOOD_CHARS = re.compile(r"(.)\1{3,}", re.IGNORECASE)  # >= 4 identical chars
RE_FLOOD_PUNCT = re.compile(r"[!?]{3,}")  # >= 3 consecutive !/?

LEET_MAP = {
    "@": "a",
    "0": "o",
    "1": "i",
    "!": "i",
    "3": "e",
    "$": "s",
}

PROFANITY_WORDS = {
    "badword",
    "porn",
    "scam",
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "idiotspam",
}


def normalize_token_for_matching(raw_token: str) -> str:
    # 1. Strip zero-width
    s = RE_ZERO_WIDTH.sub("", raw_token)
    # 2. Strip separators
    s = RE_SEPARATORS.sub("", s)
    # 3. Map leetspeak
    s = "".join(LEET_MAP.get(c, c) for c in s).lower()
    # 4. Strip punctuation for dictionary lookup
    s_clean = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", s)
    return s_clean


def contains_profanity(token: str) -> bool:
    norm = normalize_token_for_matching(token)
    if not norm:
        return False
    if norm in PROFANITY_WORDS:
        return True
    # Check substring match for composite words like bad_word or asshole
    for bad in PROFANITY_WORDS:
        if bad in norm and len(bad) >= 4:
            return True
    return False


def is_flood(text: str) -> bool:
    if RE_FLOOD_CHARS.search(text):
        return True
    if RE_FLOOD_PUNCT.search(text):
        return True
    return False


class ModerationDLQDomain:
    def __init__(self) -> None:
        self.dlq: list[dict[str, Any]] = []
        self.room_kicked: dict[str, set[str]] = {}
        self.room_muted: dict[str, set[str]] = {}

    def reset(self) -> None:
        self.dlq.clear()
        self.room_kicked.clear()
        self.room_muted.clear()

    def process_moderation(
        self,
        chat_room_id: str,
        incoming_messages: list[dict[str, Any]],
        check_dlq: bool = True,
        simulate_failed_notifications: int = 0,
    ) -> dict[str, Any]:
        # Handle simulated failed notifications first
        if simulate_failed_notifications > 0:
            for _ in range(simulate_failed_notifications):
                event_id = f"dlq-{uuid.uuid4().hex[:8]}"
                self.dlq.append({
                    "event_id": event_id,
                    "type": "notification_delivery",
                    "target": f"sub-{uuid.uuid4().hex[:6]}",
                    "attempts": 3,
                    "last_error": "Subscriber connection refused",
                    "failed_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                })

        filtered_messages: list[dict[str, Any]] = []
        kicked_users_order: list[str] = []
        muted_users_order: list[str] = []

        kicked_set = set()
        muted_set = set()

        for msg in incoming_messages:
            msg_id = msg.get("message_id", "")
            sender = msg.get("sender", "")
            text = msg.get("text", "")

            # Rule 1: Check flood first
            if is_flood(text):
                # Flood message is DROPPED from filtered_messages
                if sender not in muted_set:
                    muted_set.add(sender)
                    muted_users_order.append(sender)
                continue

            # Rule 2: Check profanity
            tokens = text.split(" ")
            has_profanity = False
            masked_tokens = []

            for tok in tokens:
                if contains_profanity(tok):
                    has_profanity = True
                    # Preserve trailing punctuation if any (like exclamation point or period)
                    trailing_punct = re.search(r"([^a-zA-Z0-9@01!3$_\-.*]+)$", tok)
                    p_str = trailing_punct.group(1) if trailing_punct else ""
                    masked_tokens.append("***" + p_str)
                else:
                    masked_tokens.append(tok)

            if has_profanity:
                filtered_text = " ".join(masked_tokens)
                filtered_messages.append({
                    "message_id": msg_id,
                    "sender": sender,
                    "text": filtered_text,
                    "flagged": True,
                    "reason": "profanity_leetspeak",
                })
                if sender not in kicked_set:
                    kicked_set.add(sender)
                    kicked_users_order.append(sender)
            else:
                filtered_messages.append({
                    "message_id": msg_id,
                    "sender": sender,
                    "text": text,
                    "flagged": False,
                    "reason": None,
                })

        # Update room state sets
        room_k = self.room_kicked.setdefault(chat_room_id, set())
        room_k.update(kicked_set)
        room_m = self.room_muted.setdefault(chat_room_id, set())
        room_m.update(muted_set)

        flagged_count = sum(1 for m in filtered_messages if m["flagged"])
        queue_depth = len(self.dlq)

        dlq_status = {
            "queue_depth": queue_depth,
            "undelivered_events": list(self.dlq) if check_dlq else [],
        }

        sig_payload = {
            "chat_room_id": chat_room_id,
            "flagged_count": flagged_count,
            "kicked_users": kicked_users_order,
            "queue_depth": queue_depth,
        }
        signature = sign_day2(chat_room_id, sig_payload)

        return {
            "chat_room_id": chat_room_id,
            "filtered_messages": filtered_messages,
            "kicked_users": kicked_users_order,
            "muted_users": muted_users_order,
            "dlq_status": dlq_status,
            "signature": signature,
        }


moderation_dlq_domain = ModerationDLQDomain()
