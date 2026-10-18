"""Transactional PostgreSQL persistence for domain entities and append-only logs.

Domain services operate on a per-request unit of work. An advisory transaction lock
serializes writers across API processes; only changed entity rows are persisted.
The single-worker Compose service bounds memory and keeps websocket reads current.
"""
import asyncio
import copy
import json
import os
import threading
from contextlib import asynccontextmanager
from app.domain.models import db_state


def state_data():
    return {k: v for k, v in vars(db_state).items() if not k.startswith("_")}


class Store:
    def __init__(self):
        self.url = os.environ.get("DATABASE_URL")

    def connect(self):
        import psycopg
        return psycopg.connect(self.url, connect_timeout=5)

    def initialize(self):
        if not self.url:
            db_state.seed_baseline()
            return
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(260017)")
            conn.execute("CREATE TABLE IF NOT EXISTS domain_entities (collection text NOT NULL, entity_id text NOT NULL, payload jsonb NOT NULL, PRIMARY KEY(collection, entity_id))")
            conn.execute("CREATE TABLE IF NOT EXISTS match_events (event_id text PRIMARY KEY, match_id text NOT NULL, sequence integer NOT NULL, payload jsonb NOT NULL, UNIQUE(match_id, sequence))")
            conn.execute("CREATE TABLE IF NOT EXISTS roster_history (audit_id text PRIMARY KEY, player_id text NOT NULL, payload jsonb NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS outbox (event_id text PRIMARY KEY, payload jsonb NOT NULL, published boolean NOT NULL DEFAULT false)")
            if not self.load(conn):
                db_state.seed_baseline()
                self.save(conn, {})

    def load(self, conn):
        rows = conn.execute("SELECT collection, entity_id, payload FROM domain_entities").fetchall()
        if not rows:
            return False
        values = {}
        for collection, key, payload in rows:
            if key == "$value":
                values[collection] = payload
            else:
                values.setdefault(collection, {})[key] = payload
        for key in state_data():
            if key in values:
                setattr(db_state, key, values[key])
        return True

    def rows(self, state):
        result = {}
        for collection, value in state.items():
            if isinstance(value, dict) and value:
                result.update({(collection, key): payload for key, payload in value.items()})
            else:
                result[(collection, "$value")] = value
        return result

    def save(self, conn, before, reset=False):
        from psycopg.types.json import Jsonb
        old, new = self.rows(before), self.rows(state_data())
        for key in old.keys() - new.keys():
            conn.execute("DELETE FROM domain_entities WHERE collection=%s AND entity_id=%s", key)
        for (collection, key), value in new.items():
            if old.get((collection, key)) != value:
                conn.execute("INSERT INTO domain_entities VALUES (%s,%s,%s) ON CONFLICT(collection,entity_id) DO UPDATE SET payload=EXCLUDED.payload", (collection, key, Jsonb(value)))
        if reset:
            conn.execute("TRUNCATE match_events, roster_history, outbox")
        for mid, events in db_state.events.items():
            old_count = 0 if reset else len(before.get("events", {}).get(mid, []))
            for event in events[old_count:]:
                conn.execute("INSERT INTO match_events VALUES (%s,%s,%s,%s)", (event["event_id"], mid, event["sequence"], Jsonb(event)))
        old_audits = set() if reset else {a["audit_id"] for a in before.get("roster_audit", [])}
        for entry in db_state.roster_audit:
            if entry["audit_id"] not in old_audits:
                conn.execute("INSERT INTO roster_history VALUES (%s,%s,%s)", (entry["audit_id"], entry["player_id"], Jsonb(entry)))
        for event in db_state.order_events:
            conn.execute("INSERT INTO outbox(event_id,payload) VALUES (%s,%s) ON CONFLICT DO NOTHING", (event["event_id"], Jsonb(event)))

    def healthy(self):
        if not self.url:
            return True
        try:
            with self.connect() as conn:
                return conn.execute("SELECT 1").fetchone()[0] == 1
        except Exception:
            return False


store = Store()
transaction_lock = threading.Lock()


@asynccontextmanager
async def acquire(lock):
    # Requests can arrive from different event loops in embedded/test servers.
    # Never block either loop while another request owns the transaction.
    while not lock.acquire(blocking=False):
        await asyncio.sleep(0.001)
    try:
        yield
    finally:
        lock.release()


class TransactionMiddleware:
    """Buffer the response until durable commit succeeds; never acknowledge lost writes."""
    def __init__(self, app):
        self.app = app
        self.lock = transaction_lock

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in ("/health", "/api/v1/ping"):
            return await self.app(scope, receive, send)
        async with acquire(self.lock):
            buffered = []
            async def capture(message):
                buffered.append(message)
            before = copy.deepcopy(state_data())
            if store.url:
                with store.connect() as conn:
                    conn.execute("SELECT pg_advisory_xact_lock(260017)")
                    store.load(conn)
                    before = copy.deepcopy(state_data())
                    try:
                        await self.app(scope, receive, capture)
                        status = next((m["status"] for m in buffered if m["type"] == "http.response.start"), 500)
                        if status >= 500:
                            raise RuntimeError("Request failed before persistence")
                        store.save(conn, before, reset=scope["path"] == "/audit/v1/reset" and status < 300)
                    except Exception:
                        for k, v in before.items():
                            setattr(db_state, k, v)
                        raise
            else:
                await self.app(scope, receive, capture)
            for message in buffered:
                await send(message)
