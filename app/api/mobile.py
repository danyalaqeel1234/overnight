"""Authenticated application routes sharing the audit contract's domain services."""
import asyncio
import base64
import json
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from app.core.auth import authenticate_header, authorize, current_user, login, profile
from app.core.errors import AppException
from app.domain.models import db_state
from app.domain.scoring import add_event, project_match
from app.domain.standings import _compute_standings as compute_standings
from app.domain.store import checkout, effective_price
from app.domain.roster import transfer_player, get_history
from app.api.offline_sync import OfflineSyncRequest, _engine

router = APIRouter(prefix="/api/v1/mobile")


async def body(request):
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, TypeError):
        raise AppException("VALIDATION_ERROR", "Please check the form fields.", {"fields": []}, 400)


def league_access(user, lid, edit=False):
    league = db_state.leagues.get(lid)
    if not league:
        raise AppException("LEAGUE_NOT_FOUND", "League not found.", {}, 404)
    authorize(user, ["league_organizer"] if edit else None, tenant=league.get("tenant_id"), league=lid if edit else None)
    return league


def match_access(user, mid, edit=False):
    match = db_state.matches.get(mid)
    if not match:
        raise AppException("MATCH_NOT_FOUND", "Match not found.", {}, 404)
    league_access(user, match.get("league_id"), edit)
    return match


def roster_access(user, payload):
    squad = db_state.roster_squads.get(payload.get("from_squad_id"))
    if not squad:
        raise AppException("SQUAD_NOT_FOUND", "Squad not found.", {}, 404)
    authorize(user, ["club_manager"], tenant=squad["tenant_id"], club=squad["club_id"])


@router.post("/login")
async def login_route(request: Request):
    data = await body(request)
    return login(data.get("email"), data.get("password"))


@router.get("/me")
def me(user=Depends(current_user)):
    return user


def snapshot(user):
    tenant = user.get("tenant_id", "tenant-alpha")
    leagues = [l for l in db_state.leagues.values() if l.get("tenant_id") == tenant]
    lids = {l["league_id"] for l in leagues}
    matches = []
    for mid, m in db_state.matches.items():
        if m.get("league_id") in lids:
            lineup=[]
            for player in db_state.roster_players.values():
                eligible=player.get('match_eligibility',{}).get(mid)
                sid=eligible['squad_id'] if eligible else player.get('squad_id')
                if sid in (m['home_team_id'],m['away_team_id']):
                    lineup.append({'player_id':player['player_id'],'name':player['name'],'squad_id':sid,'role':eligible['role'] if eligible else player['role']})
            matches.append({**project_match(mid), "schedule": db_state.schedules.get(mid),
                            "pinned_product_id": m.get("pinned_product_id"), 'lineup':lineup})
    clubs = [c for c in db_state.clubs.values() if c["tenant_id"] == tenant]
    squads = [s for s in db_state.roster_squads.values() if s["tenant_id"] == tenant]
    sids = {s["squad_id"] for s in squads}
    players = []
    for p in db_state.roster_players.values():
        if p["league_id"] in lids:
            history = [h for h in db_state.roster_audit if h['player_id'] == p['player_id']]
            players.append({**p, "version": len(history), "history": history})
    products = []
    for product in db_state.products.values():
        if product["tenant_id"] == tenant:
            variants = []
            for v in db_state.variants.values():
                if v["product_id"] == product["product_id"]:
                    price = effective_price(v)
                    variants.append({**v, "price_minor": price, "stock": db_state.stock.get(v["variant_id"], 0)})
            products.append({**product, "variants": variants})
    return {"user": user, "tenant": db_state.tenants[tenant], "leagues": leagues, "matches": matches,
            "standings": [compute_standings(l["league_id"]) for l in leagues], "clubs": clubs,
            "squads": squads, "players": players, "products": products, "sports": list(db_state.sports.values()),
            "orders": [o for o in db_state.orders.values() if o.get("customer_id", o.get("receipt", {}).get("payload", {}).get("customer_id")) == user["sub"]],
            "managed_orders": [o for o in db_state.orders.values() if user['role'] in ('super_admin','club_manager') and all(
                user['role']=='super_admin' or db_state.products[db_state.variants[i['variant_id']]['product_id']].get('club_id')==user.get('club_id') for i in o['items'])],
            "payment_attempts": [p for p in db_state.payment_attempts if p["customer_id"] == user["sub"]],
            "venues": [v for v in db_state.venues.values() if v["tenant_id"] == tenant]}


@router.get("/snapshot")
def get_snapshot(user=Depends(current_user)):
    # Reconcile due loans inside the durable HTTP transaction, never in a
    # websocket read that could acknowledge uncommitted mutations.
    for player in list(db_state.roster_players.values()):
        if player.get('registration_type') == 'loan':
            get_history(player['player_id'])
    return snapshot(user)


@router.post("/events")
async def mobile_event(request: Request, user=Depends(current_user)):
    data = await body(request)
    match_access(user, data.get("match_id"), True)
    status, result = add_event(data)
    return JSONResponse(result, status_code=status)


@router.post("/roster")
async def mobile_roster(request: Request, user=Depends(current_user)):
    data = await body(request)
    roster_access(user, data)
    data["requested_by"] = user["sub"]
    status, result = transfer_player(data)
    return JSONResponse(result, status_code=status)


@router.post("/offline-sync")
def mobile_sync(req: OfflineSyncRequest, user=Depends(current_user)):
    for action in req.actions:
        if action.type == "score_event":
            match_access(user, action.payload.get("match_id"), True)
        else:
            roster_access(user, action.payload)
            action.payload["requested_by"] = user["sub"]
    return _engine.process_sync(req)


@router.post("/checkout")
async def mobile_checkout(request: Request, user=Depends(current_user)):
    data = await body(request)
    data["customer_id"] = user["sub"]
    for item in data.get("items", []) if isinstance(data.get("items"), list) else []:
        if isinstance(item, dict):
            variant = db_state.variants.get(item.get("variant_id"))
            if variant:
                authorize(user, tenant=db_state.products[variant["product_id"]]["tenant_id"])
    status, result = checkout(data)
    return JSONResponse(result, status_code=status)


@router.get("/orders/{oid}/receipt")
def receipt(oid: str, user=Depends(current_user)):
    order = db_state.orders.get(oid)
    if not order:
        raise AppException("ORDER_NOT_FOUND", "Order not found.", {}, 404)
    if user["role"] != "super_admin" and order["receipt"]["payload"]["customer_id"] != user["sub"]:
        raise AppException("FORBIDDEN", "This receipt belongs to another account.", {}, 403)
    return Response(base64.b64decode(order["receipt"]["pdf_base64"]), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="receipt-{oid}.pdf"'})


@router.post("/orders/{oid}/transition")
async def order_transition(oid: str, request: Request, user=Depends(current_user)):
    data = await body(request)
    order = db_state.orders.get(oid)
    if not order:
        raise AppException("ORDER_NOT_FOUND", "Order not found.", {}, 404)
    target = data.get("status")
    owner = order["receipt"]["payload"]["customer_id"] == user["sub"]
    if not (owner and target in ("cancelled", "refunded")):
        for item in order['items']:
            product=db_state.products[db_state.variants[item['variant_id']]['product_id']]
            if not product.get('club_id') and user['role']!='super_admin':
                raise AppException('FORBIDDEN','This order is not assigned to your club.',{},403)
            authorize(user, ['club_manager'], tenant=product['tenant_id'], club=product.get('club_id'))
    transitions = {"paid": ["packed", "cancelled", "refunded"], "packed": ["shipped", "cancelled", "refunded"],
                   "shipped": ["delivered", "refunded"], "delivered": ["refunded"]}
    if target not in transitions.get(order["status"], []):
        raise AppException("ILLEGAL_TRANSITION", "That order status change is not allowed.", {}, 409)
    if target in ("cancelled", "refunded"):
        for item in order["items"]:
            db_state.stock[item["variant_id"]] += item["quantity"]
        order["payment"]["state"] = "refunded"
    order["status"] = target
    db_state.order_events.append({"event_id": str(uuid.uuid4()), "order_id": oid, "status": target})
    return order


@router.post("/players")
async def add_player(request: Request, user=Depends(current_user)):
    data = await body(request)
    sid = data.get("squad_id")
    squad = db_state.roster_squads.get(sid)
    roster_access(user, {"from_squad_id": sid})
    required = [k for k in ("player_id", "name", "position") if not isinstance(data.get(k), str) or not data[k].strip()]
    if required:
        raise AppException("VALIDATION_ERROR", "Player ID, name and position are required.", {"fields": required}, 400)
    if data["player_id"] in db_state.roster_players:
        raise AppException("PLAYER_EXISTS", "This player is already registered.", {}, 409)
    lid = squad["league_id"]
    if sum(p.get("squad_id") == sid for p in db_state.roster_players.values()) >= db_state.roster_leagues[lid]["max_squad_size"]:
        raise AppException("SQUAD_FULL", "The squad is full.", {}, 409)
    player = {"player_id": data["player_id"], "name": data["name"], "position": data["position"], "squad_id": sid,
              "initial_squad_id": sid, "league_id": lid, "role": "substitute", "registration_type": "initial", "parent_squad_id": None, "loan_end_date": None}
    db_state.roster_players[player["player_id"]] = player
    db_state.roster_audit.append({"audit_id": f"au-{len(db_state.roster_audit)+1:04d}", "action": "register", "player_id": player["player_id"],
                                  "league_id": lid, "from_squad_id": None, "to_squad_id": sid, "effective_date": datetime.utcnow().date().isoformat(),
                                  "state": "active", "who": user["sub"], "when": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "why": "Player registration"})
    return JSONResponse(player, status_code=201)


@router.post('/sports')
async def create_sport(request: Request, user=Depends(current_user)):
    authorize(user, ['super_admin'])
    from app.domain.sports import validate_and_normalise
    config = validate_and_normalise(await body(request))
    sid = config['sport_id']
    if sid in db_state.sports:
        raise AppException('SPORT_EXISTS','This sport already exists.',{},409)
    db_state.sports[sid] = config
    return JSONResponse({'sport_id':sid,'status':'created','config':config},status_code=201)


@router.post('/leagues')
async def create_mobile_league(request: Request, user=Depends(current_user)):
    authorize(user, ['super_admin'])
    from app.domain.fixtures import generate_round_robin, generate_swiss, generate_single_elim, generate_double_elim
    from app.domain.leagues import create_league
    data = await body(request)
    teams = data.get('teams')
    if not isinstance(teams,list) or not all(isinstance(t,str) for t in teams) or len(set(teams))!=len(teams):
        raise AppException('VALIDATION_ERROR','Provide unique team IDs.',{'fields':['teams']},400)
    fmt = data.get('format','round_robin')
    if fmt == 'round_robin':
        bracket = generate_round_robin(teams)
        matches = [m for r in bracket['rounds'] for m in r['matches']]
    elif fmt == 'swiss':
        bracket = generate_swiss(teams,None,1,[])
        matches = bracket['pairings']
    elif fmt == 'single_elim':
        bracket = generate_single_elim(teams)
        matches = [m for r in bracket['rounds'] for m in r['matches'] if m['home'] and m['away']]
    elif fmt == 'double_elim':
        bracket = generate_double_elim(teams,bracket_reset=True)
        matches = [m for r in bracket['winners'] for m in r['matches'] if m['home'] and m['away']]
    else:
        raise AppException('VALIDATION_ERROR','Choose a supported format.',{'fields':['format']},400)
    lid = data.get('league_id')
    fixtures = [{'match_id':str(lid)+':'+m['match_id'],'home':m['home'],'away':m['away']} for m in matches]
    result = create_league({'league_id':lid,'sport_id':data.get('sport_id'),'teams':teams,'fixtures':fixtures,'qualification':{'spots':1}})
    db_state.leagues[lid].update({'name':data.get('name') or lid,'season':data.get('season','2026'),'tenant_id':user['tenant_id'],
                                'format':fmt,'bracket':bracket,'divisions':data.get('divisions',[]),'promotion':data.get('promotion',{}),'relegation':data.get('relegation',{})})
    return JSONResponse(result,status_code=201)


@router.post('/matches/{mid}/schedule')
async def schedule_match(mid: str, request: Request, user=Depends(current_user)):
    match_access(user,mid,True)
    from app.domain.scheduling import reschedule
    data = await body(request)
    venue = db_state.venues.get(data.get('venue_id'))
    if venue: authorize(user,tenant=venue['tenant_id'])
    return reschedule(mid,data)


@router.post('/matches/{mid}/pin')
async def pin_product(mid: str, request: Request, user=Depends(current_user)):
    match_access(user,mid,True)
    data = await body(request)
    product = db_state.products.get(data.get('product_id'))
    if not product:
        raise AppException('PRODUCT_NOT_FOUND','Product not found.',{},404)
    authorize(user,tenant=product['tenant_id'])
    db_state.matches[mid]['pinned_product_id'] = product['product_id']
    return {'status':'pinned'}


@router.websocket("/live")
async def live(ws: WebSocket):
    await ws.accept()
    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=5)
        user = authenticate_header("Bearer " + hello.get("token", ""))
        previous = None
        while True:
            from app.core.storage import acquire, transaction_lock
            async with acquire(transaction_lock):
                # Never publish an intermediate state while an HTTP transaction
                # is still mutating or waiting for its PostgreSQL commit.
                fresh = snapshot(user)
                encoded = json.dumps(fresh, sort_keys=True)
            if encoded != previous:
                await ws.send_json({"type": "snapshot", "data": fresh})
                previous = encoded
            await asyncio.sleep(1)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except AppException:
        await ws.close(code=4401)
