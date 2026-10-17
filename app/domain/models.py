"""In-memory state store and baseline seeding."""
from __future__ import annotations

import json
import threading
import pathlib
from typing import Any

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"

_DEFAULT_TIE_BREAK = [
    "h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"
]


class DBState:
    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        # --- tenants ---
        self.tenants: dict[str, dict] = {}

        # --- sports (baseline + custom) ---
        self.sports: dict[str, dict] = {}

        # --- store ---
        self.products: dict[str, dict] = {}
        self.variants: dict[str, dict] = {}      # variant_id -> {price, currency, product_id}
        self.stock: dict[str, int] = {}          # variant_id -> available units
        self.reserved: dict[str, int] = {}       # variant_id -> reserved units
        self.orders: dict[str, dict] = {}        # order_id -> order data

        # --- leagues / clubs / players (RBAC scenario) ---
        self.leagues: dict[str, dict] = {}
        self.clubs: dict[str, dict] = {}
        self.players: dict[str, dict] = {}

        # --- matches / events (scoring engine) ---
        self.matches: dict[str, dict] = {}
        self.events: dict[str, list] = {}         # match_id -> list of event dicts

        # --- roster state ---
        self.roster_leagues: dict[str, dict] = {}   # league_id -> {league, squads, players}
        self.roster_squads: dict[str, dict] = {}    # squad_id -> squad data
        self.roster_players: dict[str, dict] = {}   # player_id -> registration data
        self.roster_audit: list[dict] = []

        # --- idempotency stores ---
        self.idempotency_events: dict[str, dict] = {}   # event_id -> response
        self.idempotency_orders: dict[str, dict] = {}   # order_id -> response
        self.idempotency_transfers: dict[str, dict] = {} # request_id -> response

        # --- offline sync ---
        self.offline_actions: dict[str, set] = {}   # device_id -> set of action_ids

        # --- misc ---
        self.current_seed: int = 42
        self._store_lock = threading.Lock()

    def seed_baseline(self, seed: int = 42, custom_stock: dict | None = None) -> None:
        self._reset()
        self.current_seed = seed

        # Tenants
        self.tenants["tenant-alpha"] = {"tenant_id": "tenant-alpha", "name": "Alpha Sports"}
        self.tenants["tenant-beta"] = {"tenant_id": "tenant-beta", "name": "Beta Athletics"}

        # Sports from JSON data file
        sports_data: list[dict] = json.loads((_DATA_DIR / "baseline_sports.json").read_text())
        for s in sports_data:
            self.sports[s["sport_id"]] = s

        # Products / variants / stock
        m_stock = 1
        l_stock = 5
        if custom_stock:
            m_stock = custom_stock.get("var-jersey-001-M", m_stock)
            l_stock = custom_stock.get("var-jersey-001-L", l_stock)

        self.products["prod-jersey-001"] = {
            "product_id": "prod-jersey-001",
            "tenant_id": "tenant-alpha",
        }
        self.variants["var-jersey-001-M"] = {
            "variant_id": "var-jersey-001-M",
            "product_id": "prod-jersey-001",
            "price_minor": 450000,
            "currency": "PKR",
        }
        self.variants["var-jersey-001-L"] = {
            "variant_id": "var-jersey-001-L",
            "product_id": "prod-jersey-001",
            "price_minor": 450000,
            "currency": "PKR",
        }
        self.stock["var-jersey-001-M"] = m_stock
        self.stock["var-jersey-001-L"] = l_stock
        self.reserved["var-jersey-001-M"] = 0
        self.reserved["var-jersey-001-L"] = 0

        # RBAC scenario
        for lid in ("league-alpha-1", "league-alpha-2"):
            self.leagues[lid] = {"league_id": lid, "tenant_id": "tenant-alpha"}
        self.leagues["league-beta-1"] = {"league_id": "league-beta-1", "tenant_id": "tenant-beta"}

        for cid, tid in (
            ("club-alpha-1", "tenant-alpha"),
            ("club-alpha-2", "tenant-alpha"),
            ("club-beta-1", "tenant-beta"),
        ):
            self.clubs[cid] = {"club_id": cid, "tenant_id": tid}

        for pid, cid in (
            ("player-alpha-1", "club-alpha-1"),
            ("player-alpha-2", "club-alpha-2"),
            ("player-beta-1", "club-beta-1"),
        ):
            self.players[pid] = {"player_id": pid, "club_id": cid}

    def is_ready(self) -> bool:
        return bool(self.sports) and bool(self.tenants)

    def stock_snapshot(self) -> dict[str, int]:
        return {
            "var-jersey-001-M": self.stock.get("var-jersey-001-M", 0),
            "var-jersey-001-L": self.stock.get("var-jersey-001-L", 0),
        }


db_state = DBState()
