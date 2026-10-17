"""Pure-computation fixture generation for all four formats."""
from __future__ import annotations

import math
from typing import Any

from app.core.errors import AppException


def _validation_err(fields: list[str], msg: str = "Validation error") -> AppException:
    return AppException("VALIDATION_ERROR", msg, {"fields": sorted(set(fields))}, 400)


# ---------------------------------------------------------------------------
# Round Robin
# ---------------------------------------------------------------------------

def generate_round_robin(
    teams: list[str],
    legs: int = 1,
    withdrawals: list[dict] | None = None,
    withdrawal_policy: str = "forfeit_remaining",
) -> dict:
    if withdrawals is None:
        withdrawals = []

    n = len(teams)
    if n < 2 or n > 40:
        raise _validation_err(["teams"])
    if legs not in (1, 2):
        raise _validation_err(["params.legs"])

    team_set = set(teams)

    # Pad to even
    odd = n % 2 == 1
    if odd:
        all_teams = teams + ["__bye__"]
        N = n + 1
    else:
        all_teams = list(teams)
        N = n

    rounds_per_leg = N - 1
    total_rounds = rounds_per_leg * legs

    # Validate withdrawals
    for wd in withdrawals:
        if wd["team_id"] not in team_set:
            raise _validation_err(["withdrawals"])
        ar = wd.get("after_round", 0)
        if ar < 0 or ar > total_rounds:
            raise _validation_err(["withdrawals"])

    withdrawn_map: dict[str, int] = {}  # team_id -> after_round (only for forfeit_remaining)
    withdrawn_all: set[str] = set()
    for wd in withdrawals:
        withdrawn_all.add(wd["team_id"])
        withdrawn_map[wd["team_id"]] = wd.get("after_round", 0)

    # --- Generate pairings via circle method ---
    # Fix the last element, rotate the rest
    fixed = all_teams[N - 1]
    rotatable = all_teams[:N - 1]

    # home_count tracking for balance
    home_count: dict[str, int] = {t: 0 for t in teams}
    away_count: dict[str, int] = {t: 0 for t in teams}

    leg1_rounds: list[tuple[list[tuple[str, str]], str | None]] = []

    for r in range(rounds_per_leg):
        # Rotate right by r: rotatable[-r:] + rotatable[:-r]
        if r == 0:
            rotated = list(rotatable)
        else:
            rotated = rotatable[-r:] + rotatable[:-r]

        table = [fixed] + rotated

        pairs: list[tuple[str, str]] = []
        bye_team: str | None = None
        for k in range(N // 2):
            a = table[k]
            b = table[N - 1 - k]
            if a == "__bye__":
                bye_team = b
            elif b == "__bye__":
                bye_team = a
            else:
                pairs.append((a, b))

        # Assign home/away for balance
        assigned: list[tuple[str, str]] = []
        for a, b in pairs:
            if home_count[a] < home_count[b]:
                h, aw = a, b
            elif home_count[b] < home_count[a]:
                h, aw = b, a
            else:
                # Tie: use string comparison for determinism
                h, aw = (a, b) if a < b else (b, a)
            home_count[h] += 1
            away_count[aw] += 1
            assigned.append((h, aw))

        leg1_rounds.append((assigned, bye_team))

    # --- Build result rounds ---
    result_rounds: list[dict] = []
    global_round = 0

    for leg in range(1, legs + 1):
        for r_idx, (assigned, bye_team) in enumerate(leg1_rounds):
            global_round += 1
            matches: list[dict] = []
            for m_idx, (h, aw) in enumerate(assigned):
                if leg == 2:
                    h, aw = aw, h  # swap for leg 2
                matches.append({
                    "match_id": f"RR-L{leg}-R{global_round}-M{m_idx + 1}",
                    "leg": leg,
                    "home": h,
                    "away": aw,
                    "status": "scheduled",
                    "awarded_to": None,
                })
            result_rounds.append({
                "round": global_round,
                "matches": matches,
                "byes": [bye_team] if bye_team else [],
            })

    # --- Apply withdrawals ---
    for round_data in result_rounds:
        rn = round_data["round"]
        for match in round_data["matches"]:
            h = match["home"]
            aw = match["away"]
            h_wd = h in withdrawn_all
            a_wd = aw in withdrawn_all

            if h_wd and a_wd:
                match["status"] = "voided"
                match["awarded_to"] = None
                continue

            if withdrawal_policy == "void_all":
                if h_wd or a_wd:
                    match["status"] = "voided"
                    match["awarded_to"] = None
            else:  # forfeit_remaining
                h_forfeit = h_wd and rn > withdrawn_map.get(h, 0)
                a_forfeit = a_wd and rn > withdrawn_map.get(aw, 0)
                if h_forfeit and a_forfeit:
                    match["status"] = "voided"
                    match["awarded_to"] = None
                elif h_forfeit:
                    match["status"] = "forfeit"
                    match["awarded_to"] = aw
                elif a_forfeit:
                    match["status"] = "forfeit"
                    match["awarded_to"] = h

    # --- Summary ---
    all_matches = [m for r in result_rounds for m in r["matches"]]
    total = len(all_matches)
    scheduled = sum(1 for m in all_matches if m["status"] == "scheduled")
    forfeit = sum(1 for m in all_matches if m["status"] == "forfeit")
    voided = sum(1 for m in all_matches if m["status"] == "voided")

    return {
        "format": "round_robin",
        "legs": legs,
        "team_count": n,
        "round_count": total_rounds,
        "rounds": result_rounds,
        "summary": {"total": total, "scheduled": scheduled, "forfeit": forfeit, "voided": voided},
    }


# ---------------------------------------------------------------------------
# Swiss
# ---------------------------------------------------------------------------

def _compute_standings(teams: list[str], history: list[dict]) -> tuple[
    dict[str, float], dict[str, float], dict[str, bool], dict[str, list[str]]
]:
    """Returns scores, buchholz, byes, opponents per team."""
    scores: dict[str, float] = {t: 0.0 for t in teams}
    byes: dict[str, bool] = {t: False for t in teams}
    opponents: dict[str, list[str]] = {t: [] for t in teams}

    for rd in history:
        bt = rd.get("bye")
        if bt and bt in scores:
            scores[bt] += 1.0
            byes[bt] = True
        for m in rd.get("matches", []):
            hm, aw, res = m["home"], m["away"], m["result"]
            opponents[hm].append(aw)
            opponents[aw].append(hm)
            if res == "home":
                scores[hm] += 1.0
            elif res == "away":
                scores[aw] += 1.0
            else:
                scores[hm] += 0.5
                scores[aw] += 0.5

    buchholz: dict[str, float] = {}
    for t in teams:
        buchholz[t] = sum(scores[opp] for opp in opponents[t])

    return scores, buchholz, byes, opponents


def _find_best_pairing(
    remaining: list[str],
    scores: dict[str, float],
    played_set: set[frozenset],
) -> tuple[list[tuple[str, str]] | None, float]:
    """Backtracking: find pairing of remaining teams minimising total |score diff|, no rematches."""
    if not remaining:
        return [], 0.0

    best: list[tuple[str, str]] | None = None
    best_cost: list[float] = [float("inf")]

    def bt(rest: list[str], pairs: list[tuple[str, str]], cost: float) -> None:
        if not rest:
            if cost < best_cost[0]:
                best_cost[0] = cost
                nonlocal best
                best = list(pairs)
            return
        if cost >= best_cost[0]:
            return  # prune

        first = rest[0]
        for i in range(1, len(rest)):
            partner = rest[i]
            if frozenset([first, partner]) in played_set:
                continue
            c = abs(scores[first] - scores[partner])
            if cost + c >= best_cost[0]:
                continue  # prune
            pairs.append((first, partner))
            bt(rest[1:i] + rest[i + 1:], pairs, cost + c)
            pairs.pop()

    bt(remaining, [], 0.0)
    return (best, best_cost[0]) if best is not None else (None, float("inf"))


def generate_swiss(
    teams: list[str],
    total_rounds: int | None,
    round_num: int,
    history: list[dict],
) -> dict:
    n = len(teams)
    if n < 2 or n > 64:
        raise _validation_err(["teams"])

    if total_rounds is None:
        total_rounds = math.ceil(math.log2(n))
    if not (1 <= total_rounds <= n - 1):
        raise _validation_err(["params.total_rounds"])
    if not (1 <= round_num <= total_rounds):
        raise _validation_err(["params.round"])

    # Validate history has exactly rounds 1..round_num-1
    expected_rounds = set(range(1, round_num))
    actual_rounds = {rd["round"] for rd in history} if history else set()
    if expected_rounds != actual_rounds:
        raise _validation_err(["params.history"])

    scores, buchholz, byes, opponents = _compute_standings(teams, history)

    seed_idx = {t: i for i, t in enumerate(teams)}

    # Build standings (history only, before this round)
    standings_order = sorted(
        teams,
        key=lambda t: (-scores[t], -buchholz[t], seed_idx[t]),
    )
    standings = [
        {
            "rank": rank,
            "team_id": t,
            "score": scores[t],
            "buchholz": buchholz[t],
        }
        for rank, t in enumerate(standings_order, 1)
    ]

    if round_num == 1:
        m = n // 2
        bye_team = teams[n - 1] if n % 2 == 1 else None
        pairings = []
        for i in range(m):
            home_team = teams[i]
            away_team = teams[i + m]
            pairings.append({
                "match_id": f"SW-R1-M{i + 1}",
                "home": home_team,
                "away": away_team,
            })
        return {
            "format": "swiss",
            "round": round_num,
            "total_rounds": total_rounds,
            "pairings": pairings,
            "bye": bye_team,
            "standings": standings,
        }

    # Rounds >= 2: backtracking pairing
    played_set: set[frozenset] = set()
    for t in teams:
        for opp in opponents[t]:
            played_set.add(frozenset([t, opp]))

    # Sort teams by standings order for pairing
    remaining = list(standings_order)

    if n % 2 == 1:
        # Find bye candidate: lowest score without a previous bye
        # Ties -> largest index (which means last in seed order = worst seed)
        no_bye = [t for t in standings_order if not byes[t]]
        if not no_bye:
            no_bye = list(standings_order)  # all had a bye; must allow repeat

        # Candidates sorted: worst score first, largest index (worst seed) first
        candidates = sorted(no_bye, key=lambda t: (scores[t], -seed_idx[t]))
        # candidates[0] = lowest score, largest index (worst seed among ties)

        paired_result = None
        chosen_bye = None
        for cand in candidates:
            rest_teams = [t for t in remaining if t != cand]
            result, _ = _find_best_pairing(rest_teams, scores, played_set)
            if result is not None:
                paired_result = result
                chosen_bye = cand
                break

        if paired_result is None:
            raise AppException(
                "NO_VALID_PAIRING",
                "No valid pairing exists for this round.",
                {"round": round_num},
                409,
            )

        bye_team = chosen_bye
        pairs = paired_result
    else:
        bye_team = None
        result, _ = _find_best_pairing(remaining, scores, played_set)
        if result is None:
            raise AppException(
                "NO_VALID_PAIRING",
                "No valid pairing exists for this round.",
                {"round": round_num},
                409,
            )
        pairs = result

    pairings = []
    for i, (a, b) in enumerate(pairs, 1):
        # home = lower seed index
        if seed_idx[a] <= seed_idx[b]:
            home, away = a, b
        else:
            home, away = b, a
        pairings.append({"match_id": f"SW-R{round_num}-M{i}", "home": home, "away": away})

    return {
        "format": "swiss",
        "round": round_num,
        "total_rounds": total_rounds,
        "pairings": pairings,
        "bye": bye_team,
        "standings": standings,
    }


# ---------------------------------------------------------------------------
# Single Elimination
# ---------------------------------------------------------------------------

def _seed_order(b: int) -> list[int]:
    """Recursive seed order: order(2)=[1,2]; order(2k)=for s in order(k): [s, 2k+1-s]."""
    if b == 2:
        return [1, 2]
    half = b // 2
    prev = _seed_order(half)
    result = []
    for s in prev:
        result.append(s)
        result.append(b + 1 - s)
    return result


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


def generate_single_elim(
    teams: list[str],
    third_place_match: bool = False,
    results: list[dict] | None = None,
) -> dict:
    n = len(teams)
    if n < 2 or n > 128:
        raise _validation_err(["teams"])

    B = _next_pow2(n)
    k = int(math.log2(B))
    seed_list = _seed_order(B)  # length B

    # Build all matches indexed by match_id
    all_matches: dict[str, dict] = {}

    def make_match(mid: str, home_seed: int, away_seed: int, bracket: str = "main") -> dict:
        home_team = teams[home_seed - 1] if home_seed <= n else None
        away_team = teams[away_seed - 1] if away_seed <= n else None
        is_bye = away_seed > n or home_seed > n
        # lower seed is home (already set above based on seed_list order)
        # Actually home = lower seed number
        if home_team is None and away_team is not None:
            is_bye = True
            home_team = away_team
            away_team = None
            home_seed, away_seed = away_seed, home_seed
        elif home_seed > away_seed and home_team is not None and away_team is not None:
            home_team, away_team = away_team, home_team
            home_seed, away_seed = away_seed, home_seed

        rnd = int(mid[1:].split("M")[0]) if mid.startswith("R") else 0
        idx = int(mid[1:].split("M")[1]) if mid.startswith("R") else 0

        winner = home_team if is_bye else None
        loser = None

        # winner_to
        if rnd < k:
            next_match = f"R{rnd + 1}M{math.ceil(idx / 2)}"
            slot = "home" if idx % 2 == 1 else "away"
            winner_to: dict | None = {"match_id": next_match, "slot": slot}
        else:
            winner_to = None

        return {
            "match_id": mid,
            "bracket": bracket,
            "round": rnd,
            "index": idx,
            "home": home_team,
            "away": away_team,
            "home_seed": home_seed,
            "away_seed": away_seed,
            "bye": is_bye,
            "winner": winner,
            "loser": loser,
            "winner_to": winner_to,
            "loser_to": None,
        }

    # Build R1 matches
    round_matches: dict[int, list[dict]] = {}
    for i in range(1, B // 2 + 1):
        s1 = seed_list[2 * i - 2]
        s2 = seed_list[2 * i - 1]
        # lower seed is home
        if s1 <= s2:
            hs, as_ = s1, s2
        else:
            hs, as_ = s2, s1
        mid = f"R1M{i}"
        m = make_match(mid, hs, as_)
        all_matches[mid] = m
        round_matches.setdefault(1, []).append(m)

    # Propagate R1 bye winners immediately
    for m in round_matches[1]:
        if m["bye"] and m["winner"] and m["winner_to"]:
            nm = all_matches.get(m["winner_to"]["match_id"])
            if nm:
                nm[m["winner_to"]["slot"]] = m["winner"]

    # Build rounds 2..k
    for r in range(2, k + 1):
        n_matches = B // (2 ** r)
        for i in range(1, n_matches + 1):
            mid = f"R{r}M{i}"
            # slots might be pre-filled from propagation
            prev1_mid = f"R{r - 1}M{2 * i - 1}"
            prev2_mid = f"R{r - 1}M{2 * i}"
            prev1 = all_matches.get(prev1_mid)
            prev2 = all_matches.get(prev2_mid)

            home_team = None
            away_team = None
            if prev1:
                home_team = prev1["winner"]
            if prev2:
                away_team = prev2["winner"]

            winner_to: dict | None = None
            if r < k:
                winner_to = {"match_id": f"R{r + 1}M{math.ceil(i / 2)}", "slot": "home" if i % 2 == 1 else "away"}

            m_dict = {
                "match_id": mid,
                "bracket": "main",
                "round": r,
                "index": i,
                "home": home_team,
                "away": away_team,
                "home_seed": None,
                "away_seed": None,
                "bye": False,
                "winner": None,
                "loser": None,
                "winner_to": winner_to,
                "loser_to": None,
            }
            all_matches[mid] = m_dict
            round_matches.setdefault(r, []).append(m_dict)

    # Third place match
    if third_place_match and k >= 2:
        sf_round = k - 1
        sf_count = B // (2 ** (k - 1))
        # Semifinal losers (last 2 in SF round)
        sf_idx = [sf_count - 1, sf_count]
        tp_match = {
            "match_id": "TP",
            "bracket": "third_place",
            "round": k,
            "index": 0,
            "home": None,
            "away": None,
            "home_seed": None,
            "away_seed": None,
            "bye": False,
            "winner": None,
            "loser": None,
            "winner_to": None,
            "loser_to": None,
        }
        # Point SF matches' loser_to -> TP
        for sf_i in range(1, sf_count + 1):
            sf_mid = f"R{sf_round}M{sf_i}"
            if sf_mid in all_matches:
                slot = "home" if sf_i % 2 == 1 else "away"
                all_matches[sf_mid]["loser_to"] = {"match_id": "TP", "slot": slot}
        all_matches["TP"] = tp_match

    # Apply results
    if results:
        for res in results:
            mid = res.get("match_id")
            winner = res.get("winner")
            m = all_matches.get(mid)
            if m is None:
                raise _validation_err(["params.results"])
            participants = {m["home"], m["away"]} - {None}
            if winner not in participants:
                raise _validation_err(["params.results"])
            loser = (participants - {winner}).pop() if len(participants) == 2 else None
            m["winner"] = winner
            m["loser"] = loser
            # Propagate winner
            if m["winner_to"]:
                nm = all_matches.get(m["winner_to"]["match_id"])
                if nm:
                    nm[m["winner_to"]["slot"]] = winner
            # Propagate loser to TP if applicable
            if m.get("loser_to") and loser:
                lm = all_matches.get(m["loser_to"]["match_id"])
                if lm:
                    lm[m["loser_to"]["slot"]] = loser

    # Build response rounds
    rounds_out = []
    for r in range(1, k + 1):
        rnd_matches = [all_matches[f"R{r}M{i}"] for i in range(1, B // (2 ** r) + 1) if f"R{r}M{i}" in all_matches]
        rounds_out.append({"round": r, "matches": rnd_matches})

    result: dict[str, Any] = {
        "format": "single_elim",
        "bracket_size": B,
        "rounds": rounds_out,
    }
    if third_place_match and "TP" in all_matches:
        result["third_place_match"] = all_matches["TP"]

    return result


# ---------------------------------------------------------------------------
# Double Elimination
# ---------------------------------------------------------------------------

def generate_double_elim(
    teams: list[str],
    bracket_reset: bool = False,
    results: list[dict] | None = None,
) -> dict:
    n = len(teams)
    if n < 3 or n > 128:
        raise _validation_err(["teams"])

    B = _next_pow2(n)
    k = int(math.log2(B))

    all_matches: dict[str, dict] = {}

    def new_match(mid: str, bracket: str, rnd: int, idx: int) -> dict:
        return {
            "match_id": mid,
            "bracket": bracket,
            "round": rnd,
            "index": idx,
            "home": None,
            "away": None,
            "home_seed": None,
            "away_seed": None,
            "bye": False,
            "winner": None,
            "loser": None,
            "winner_to": None,
            "loser_to": None,
        }

    # ---- Winners bracket R1 (same as single elim) ----
    seed_list = _seed_order(B)
    wr_rounds: dict[int, list[dict]] = {}
    lr_rounds: dict[int, list[dict]] = {}

    for i in range(1, B // 2 + 1):
        s1 = seed_list[2 * i - 2]
        s2 = seed_list[2 * i - 1]
        hs, as_ = (s1, s2) if s1 < s2 else (s2, s1)
        home_team = teams[hs - 1] if hs <= n else None
        away_team = teams[as_ - 1] if as_ <= n else None
        is_bye = away_team is None

        if is_bye:
            winner = home_team
        else:
            winner = None

        mid = f"WR1M{i}"
        m = new_match(mid, "winners", 1, i)
        m["home"] = home_team
        m["away"] = away_team
        m["home_seed"] = hs
        m["away_seed"] = as_
        m["bye"] = is_bye
        m["winner"] = winner
        m["winner_to"] = {"match_id": f"WR2M{math.ceil(i / 2)}", "slot": "home" if i % 2 == 1 else "away"}
        m["loser_to"] = {"match_id": f"LR1M{math.ceil(i / 2)}", "slot": "home" if i % 2 == 1 else "away"}
        all_matches[mid] = m
        wr_rounds.setdefault(1, []).append(m)

    # Propagate WR1 bye winners
    for m in wr_rounds[1]:
        if m["bye"] and m["winner"] and m["winner_to"]:
            wt_mid = m["winner_to"]["match_id"]
            if wt_mid not in all_matches:
                pass  # will be created below

    # ---- Build LR rounds ----
    # For j=1..k-1:
    #   LR(2j-1): B/2^(j+1) matches - WR1 losers meet each other (j=1) or LR(2j-2) winners
    #   LR(2j):   B/2^(j+1) matches - LR(2j-1) winners vs WR(j+1) losers

    for j in range(1, k):
        n_lr_matches = B // (2 ** (j + 1))
        lr_odd = 2 * j - 1   # e.g., 1, 3, 5...
        lr_even = 2 * j       # e.g., 2, 4, 6...

        # LR(2j-1) matches
        for i in range(1, n_lr_matches + 1):
            mid = f"LR{lr_odd}M{i}"
            m = new_match(mid, "losers", lr_odd, i)
            if j == 1:
                # Sources: WR1M(2i-1) loser and WR1M(2i) loser
                m["home"] = None  # filled from WR1 loser propagation
                m["away"] = None
            else:
                # Sources: LR(2j-2)M(2i-1) winner and LR(2j-2)M(2i) winner
                prev_lr = 2 * j - 2
                pm1 = f"LR{prev_lr}M{2*i - 1}"
                pm2 = f"LR{prev_lr}M{2*i}"
                pm1_m = all_matches.get(pm1)
                pm2_m = all_matches.get(pm2)
                m["home"] = pm1_m["winner"] if pm1_m else None
                m["away"] = pm2_m["winner"] if pm2_m else None
                if pm1_m:
                    pm1_m["winner_to"] = {"match_id": mid, "slot": "home"}
                if pm2_m:
                    pm2_m["winner_to"] = {"match_id": mid, "slot": "away"}

            if j < k - 1:
                m["winner_to"] = {"match_id": f"LR{lr_even}M{i}", "slot": "home"}
            else:
                # LB final -> GF1
                m["winner_to"] = {"match_id": "GF1", "slot": "away"}

            all_matches[mid] = m
            lr_rounds.setdefault(lr_odd, []).append(m)

        # LR(2j) matches
        for i in range(1, n_lr_matches + 1):
            mid = f"LR{lr_even}M{i}"
            m = new_match(mid, "losers", lr_even, i)
            # Home: LR(2j-1)M{i} winner
            lr_odd_mid = f"LR{lr_odd}M{i}"
            lr_odd_m = all_matches.get(lr_odd_mid)
            if lr_odd_m:
                m["home"] = lr_odd_m["winner"]
                lr_odd_m["winner_to"] = {"match_id": mid, "slot": "home"}
            # Away: WR(j+1)M{i} loser
            wr_drop_mid = f"WR{j+1}M{i}"
            wr_drop_m = all_matches.get(wr_drop_mid)
            if wr_drop_m:
                m["away"] = wr_drop_m["loser"]
                wr_drop_m["loser_to"] = {"match_id": mid, "slot": "away"}

            if j < k - 1:
                m["winner_to"] = {"match_id": f"LR{2*j+1}M{math.ceil(i/2)}", "slot": "home" if i % 2 == 1 else "away"}
            else:
                # LB final
                m["winner_to"] = {"match_id": "GF1", "slot": "away"}

            all_matches[mid] = m
            lr_rounds.setdefault(lr_even, []).append(m)

    # ---- Build WR rounds 2..k ----
    for r in range(2, k + 1):
        n_wr = B // (2 ** r)
        for i in range(1, n_wr + 1):
            mid = f"WR{r}M{i}"
            m = new_match(mid, "winners", r, i)
            prev1 = all_matches.get(f"WR{r-1}M{2*i-1}")
            prev2 = all_matches.get(f"WR{r-1}M{2*i}")
            m["home"] = prev1["winner"] if prev1 else None
            m["away"] = prev2["winner"] if prev2 else None

            if r < k:
                m["winner_to"] = {"match_id": f"WR{r+1}M{math.ceil(i/2)}", "slot": "home" if i % 2 == 1 else "away"}
                lr_drop = 2 * (r - 1)
                m["loser_to"] = {"match_id": f"LR{lr_drop}M{i}", "slot": "away"}
            else:
                # WR final
                m["winner_to"] = {"match_id": "GF1", "slot": "home"}
                # WR final loser -> LB final as away
                lb_final_round = 2 * (k - 1)
                m["loser_to"] = {"match_id": f"LR{lb_final_round}M1", "slot": "away"}

            if prev1:
                prev1["winner_to"] = {"match_id": mid, "slot": "home"}
            if prev2:
                prev2["winner_to"] = {"match_id": mid, "slot": "away"}

            all_matches[mid] = m
            wr_rounds.setdefault(r, []).append(m)

    # Propagate WR1 losers -> LR1
    for m in wr_rounds.get(1, []):
        lt = m.get("loser_to")
        if lt and m.get("loser"):
            nm = all_matches.get(lt["match_id"])
            if nm:
                nm[lt["slot"]] = m["loser"]

    # ---- Grand Final ----
    gf1 = new_match("GF1", "grand_final", k + 1, 1)
    gf1["winner_to"] = None
    gf1["loser_to"] = None
    # home = WR final winner (populated on result)
    # away = LB final winner
    all_matches["GF1"] = gf1

    gf2 = new_match("GF2", "grand_final", k + 2, 2)
    gf2["conditional"] = True
    gf2["required"] = None
    gf2["winner_to"] = None
    gf2["loser_to"] = None
    all_matches["GF2"] = gf2

    # ---- Apply results ----
    if results:
        for res in results:
            mid = res.get("match_id")
            winner = res.get("winner")
            m = all_matches.get(mid)
            if m is None:
                raise _validation_err(["params.results"])
            participants = {m.get("home"), m.get("away")} - {None}
            if winner not in participants:
                raise _validation_err(["params.results"])
            loser = (participants - {winner}).pop() if len(participants) == 2 else None
            m["winner"] = winner
            m["loser"] = loser
            # Propagate winner
            if m.get("winner_to"):
                nm = all_matches.get(m["winner_to"]["match_id"])
                if nm:
                    nm[m["winner_to"]["slot"]] = winner
                    if m["winner_to"]["match_id"] == "GF1":
                        nm[m["winner_to"]["slot"]] = winner
            # Propagate loser
            if m.get("loser_to") and loser:
                nm = all_matches.get(m["loser_to"]["match_id"])
                if nm:
                    nm[m["loser_to"]["slot"]] = loser

    # Update GF2 required based on GF1 result
    if gf1.get("winner"):
        lb_champ = gf1.get("away")  # LB champion is GF1.away
        gf2["required"] = bracket_reset and (gf1["winner"] == lb_champ)
        if gf2["required"]:
            gf2["home"] = gf1.get("home")
            gf2["away"] = gf1.get("away")

    # ---- Build response ----
    winners_out = []
    for r in range(1, k + 1):
        matches = [all_matches.get(f"WR{r}M{i}") for i in range(1, B // (2**r) + 1)]
        matches = [m for m in matches if m is not None]
        winners_out.append({"round": r, "matches": matches})

    losers_out = []
    lr_total_rounds = 2 * (k - 1)
    for r in range(1, lr_total_rounds + 1):
        j = math.ceil(r / 2)
        n_lr = B // (2 ** (j + 1))
        matches = [all_matches.get(f"LR{r}M{i}") for i in range(1, n_lr + 1)]
        matches = [m for m in matches if m is not None]
        losers_out.append({"round": r, "matches": matches})

    grand_final = [gf1]
    if bracket_reset:
        grand_final.append(gf2)

    return {
        "format": "double_elim",
        "bracket_size": B,
        "bracket_reset": bracket_reset,
        "winners": winners_out,
        "losers": losers_out,
        "grand_final": grand_final,
    }
