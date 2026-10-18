"""Seed real, editable application records. No simulated client responses."""
from functools import lru_cache
from app.core.auth import password_hash


CLUB_PROFILES = {
    "club-alpha-1": {"staff": [{"name": "Sana Malik", "role": "Coach"}, {"name": "Hamza Iqbal", "role": "Manager"}, {"name": "Omar Ali", "role": "Physio"}],
                     "venue": {"name": "University Ground", "latitude": 33.656, "longitude": 73.016},
                     "social": {"website": "alphaunited.club", "instagram": "@alphaunited"},
                     "history": [{"season": "2024", "played": 14, "wins": 8}, {"season": "2025", "played": 16, "wins": 10}]},
    "club-alpha-2": {"staff": [{"name": "Usman Tariq", "role": "Coach"}, {"name": "Ayesha Noor", "role": "Manager"}, {"name": "Fahad Raza", "role": "Physio"}],
                     "venue": {"name": "Riverside Stadium", "latitude": 33.684, "longitude": 73.048},
                     "social": {"website": "riversidefc.club", "instagram": "@riversidefc"},
                     "history": [{"season": "2024", "played": 14, "wins": 6}, {"season": "2025", "played": 16, "wins": 7}]},
    "club-beta-1": {"staff": [{"name": "Kamran Akmal", "role": "Coach"}, {"name": "Hina Javed", "role": "Manager"}, {"name": "Saad Butt", "role": "Physio"}],
                    "venue": {"name": "Beta Arena", "latitude": 31.520, "longitude": 74.358},
                    "social": {"website": "betaathletic.club", "instagram": "@betaathletic"},
                    "history": [{"season": "2025", "played": 12, "wins": 5}]},
}


@lru_cache
def demo_password_hash():
    return password_hash("Nascon@26")


def seed_mobile(state):
    for email, role, uid in [("admin", "super_admin", "admin-1"), ("organizer", "league_organizer", "org-1"),
                             ("manager", "club_manager", "mgr-1"), ("player", "player", "player-1"), ("viewer", "viewer", "view-1")]:
        address = email + "@nascon.test"
        state.users[address] = {"email": address, "role": role, "sub": uid, "name": role.replace("_", " ").title(),
                                "tenant_id": "tenant-alpha", "league_id": "league-alpha-1", "club_id": "club-alpha-1",
                                "player_id": "player-alpha-1" if role == "player" else None,
                                "password_hash": demo_password_hash()}
    for tenant in state.tenants.values():
        tenant.update({"color": "#63F3B0", "logo": "AS" if tenant["tenant_id"] == "tenant-alpha" else "BA"})
    for cid, club in state.clubs.items():
        club.update({"name": {"club-alpha-1": "Alpha United", "club-alpha-2": "Riverside FC", "club-beta-1": "Beta Athletic"}[cid],
                     "staff": CLUB_PROFILES[cid]["staff"], "home_venue": CLUB_PROFILES[cid]["venue"],
                     "social_handles": CLUB_PROFILES[cid]["social"], "history": CLUB_PROFILES[cid]["history"]})
    for lid, league in state.leagues.items():
        tid = league["tenant_id"]
        teams = ["squad-alpha-1", "squad-alpha-2"] if tid == "tenant-alpha" else ["squad-beta-1", "squad-beta-2"]
        league.update({"name": {"league-alpha-1": "Campus League", "league-alpha-2": "Campus Cup", "league-beta-1": "Beta Premier League"}.get(lid, lid), "season": "2026", "sport_id": "football",
                       "teams": teams, "fixtures": [], "points": {"win": 3, "draw": 1, "loss": 0},
                       "tie_break_order": state.sports["football"]["tie_break_order"], "qualification": {"spots": 1},
                       "lots_seed": state.current_seed, "format": "round_robin", "divisions": [], "promotion": {}, "relegation": {}})
    lid = "league-alpha-1"
    mid = "demo-match-1"
    state.leagues[lid]["fixtures"] = [{"match_id": mid, "home": "squad-alpha-1", "away": "squad-alpha-2"}]
    state.matches[mid] = {"match_id": mid, "sport_id": "football", "home_team_id": "squad-alpha-1", "away_team_id": "squad-alpha-2", "league_id": lid}
    state.events[mid] = []
    from app.domain.scoring import add_event
    add_event({"event_id": "demo-start", "match_id": mid, "type": "match_start", "payload": {}})
    state.matches[mid]["pinned_product_id"] = "prod-jersey-001"
    from app.domain.roster import setup_roster
    setup_roster({"league": {"league_id": lid, "tenant_id": "tenant-alpha", "sport_id": "football",
                             "transfer_window": {"open": "2026-01-01", "close": "2030-12-31"}, "max_squad_size": 25, "required_positions": {"gk": 1}},
                  "squads": [{"squad_id": "squad-alpha-1", "club_id": "club-alpha-1", "tenant_id": "tenant-alpha", "name": "Alpha United"},
                             {"squad_id": "squad-alpha-2", "club_id": "club-alpha-2", "tenant_id": "tenant-alpha", "name": "Riverside FC"}],
                  "players": [{"player_id": "player-alpha-1", "name": "Ali Khan", "position": "df", "squad_id": "squad-alpha-1", "role": "captain"},
                              {"player_id": "keeper-alpha-1", "name": "Sara Ahmed", "position": "gk", "squad_id": "squad-alpha-1", "role": "starter"},
                              {"player_id": "player-alpha-2", "name": "Bilal Shah", "position": "df", "squad_id": "squad-alpha-2", "role": "starter"},
                              {"player_id": "keeper-alpha-2", "name": "Zain Ali", "position": "gk", "squad_id": "squad-alpha-2", "role": "starter"}],
                  "matches_in_progress": []})
    state.products["prod-jersey-001"].update({"name": "Alpha United Home Jersey", "description": "Official club apparel", "category": "apparel", "club_id": "club-alpha-1"})
    for vid, variant in state.variants.items():
        variant.update({"size": vid.rsplit("-", 1)[-1], "color": "Navy", "scheduled_prices": []})
    state.venues["venue-main"] = {"venue_id": "venue-main", "tenant_id": "tenant-alpha", "name": "University Ground", "availability": []}
    state.schedules[mid] = {"match_id": mid, "venue_id": "venue-main", "start": "2026-10-18T06:00:00Z", "end": "2026-10-18T08:00:00Z", "min_rest_minutes": 30}
