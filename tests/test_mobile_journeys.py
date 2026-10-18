"""The actual login, role, sync and payment journeys used by the APK."""
import base64
import io
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models import db_state

@pytest.fixture
def client():
    db_state.seed_baseline()
    with TestClient(app) as client:
        yield client

def auth(client, role):
    r = client.post('/api/v1/mobile/login', json={'email':role+'@nascon.test','password':'Nascon@26'})
    assert r.status_code == 200, r.text
    return {'Authorization':'Bearer '+r.json()['token']}

@pytest.mark.parametrize('role',['admin','organizer','manager','player','viewer'])
def test_each_demo_account_has_real_snapshot(client,role):
    headers=auth(client,role)
    r=client.get('/api/v1/mobile/snapshot',headers=headers)
    assert r.status_code==200,r.text
    assert r.json()['user']['email']==role+'@nascon.test'
    assert r.json()['matches'] and r.json()['clubs'] and r.json()['products']
    assert 'password_hash' not in r.text

def test_login_wrong_password_and_unauthenticated_snapshot(client):
    assert client.post('/api/v1/mobile/login',json={'email':'admin@nascon.test','password':'wrong'}).status_code==401
    assert client.get('/api/v1/mobile/snapshot').status_code==401

@pytest.mark.parametrize('role,expected',[('admin',201),('organizer',201),('manager',403),('player',403),('viewer',403)])
def test_actual_scoring_role_boundaries(client,role,expected):
    payload={'event_id':'role-score','match_id':'demo-match-1','type':'score','payload':{'team_id':'squad-alpha-1','event_type':'goal'}}
    assert client.post('/api/v1/mobile/events',json=payload,headers=auth(client,role)).status_code==expected

@pytest.mark.parametrize('token,error',[('tok_declined','PAYMENT_DECLINED'),('tok_capture_fail','PAYMENT_CAPTURE_FAILED')])
def test_failed_payment_releases_stock_and_success_can_follow(client,token,error):
    headers=auth(client,'viewer')
    payload={'order_id':'failure','items':[{'variant_id':'var-jersey-001-M','quantity':1}],'payment':{'token':token}}
    failed=client.post('/api/v1/mobile/checkout',headers=headers,json=payload)
    assert failed.status_code==402 and failed.json()['error']['code']==error
    inventory=client.get('/audit/v1/inventory/var-jersey-001-M').json()
    assert inventory['stock']==1 and inventory['reserved']==0
    payload['order_id']='success';payload['payment']['token']='tok_success'
    paid=client.post('/api/v1/mobile/checkout',headers=headers,json=payload)
    assert paid.status_code==201,paid.text
    assert paid.json()['total_minor']==450000
    pdf=base64.b64decode(paid.json()['receipt']['pdf_base64'])
    assert pdf.startswith(b'%PDF-') and b'%%EOF' in pdf
    snapshot=client.get('/api/v1/mobile/snapshot',headers=headers).json()
    assert len(snapshot['payment_attempts'])==2
    refund=client.post('/api/v1/mobile/orders/success/transition',headers=headers,json={'status':'refunded'})
    assert refund.status_code==200
    assert client.get('/audit/v1/inventory/var-jersey-001-M').json()['stock']==1
    assert client.post('/api/v1/mobile/orders/success/transition',headers=headers,json={'status':'refunded'}).status_code==409

def test_viewer_cannot_bypass_permissions_through_sync(client):
    a={'action_id':'bypass','type':'score_event','queued_at':'2026-10-17T11:00:00Z','base_version':1,
       'payload':{'event_id':'bypass','match_id':'demo-match-1','type':'score','payload':{'team_id':'squad-alpha-1','event_type':'goal'}}}
    assert client.post('/api/v1/mobile/offline-sync',headers=auth(client,'viewer'),json={'device_id':'phone','actions':[a]}).status_code==403
    assert len(db_state.events['demo-match-1'])==1

def test_concurrent_identical_order_is_charged_only_once(client):
    from app.domain.store import checkout
    payload={'order_id':'same','customer_id':'customer','items':[{'variant_id':'var-jersey-001-L','quantity':1}],'payment':{'token':'tok_success'}}
    with ThreadPoolExecutor(max_workers=20) as pool:
        responses=list(pool.map(lambda _:checkout(payload),range(20)))
    assert sum(status==201 for status,_ in responses)==1
    assert sum(status==200 for status,_ in responses)==19
    assert db_state.stock['var-jersey-001-L']==4
    assert db_state.reserved['var-jersey-001-L']==0

def test_schedule_detects_conflicts_without_overwriting(client):
    headers=auth(client,'admin')
    db_state.matches['other']={**db_state.matches['demo-match-1'],'match_id':'other'}
    db_state.events['other']=[]
    conflicting={**db_state.schedules['demo-match-1']}
    r=client.post('/api/v1/mobile/matches/other/schedule',headers=headers,json=conflicting)
    assert r.status_code==409,r.text
    assert 'venue_double_booking' in {c['type'] for c in r.json()['error']['details']['conflicts']}
    assert 'other' not in db_state.schedules

@pytest.mark.parametrize('path,payload',[
 ('events',{}),('events',{'event_id':[],'match_id':'m','type':'score','payload':{}}),
 ('leagues',{}),('roster/setup',{}),('roster/transfer',{}),
])
def test_invalid_inputs_never_become_500(client,path,payload):
    response=client.post('/audit/v1/'+path,json=payload)
    assert response.status_code==400,response.text

@pytest.mark.parametrize('fmt',['round_robin','swiss','single_elim','double_elim'])
def test_admin_can_create_each_fixture_format(client,fmt):
    r=client.post('/api/v1/mobile/leagues',headers=auth(client,'admin'),json={'league_id':'new-'+fmt,'name':'Test cup','sport_id':'football','teams':['a','b','c','d'],'format':fmt})
    assert r.status_code==201,r.text
    snapshot=client.get('/api/v1/mobile/snapshot',headers=auth(client,'admin')).json()
    assert any(l['league_id']=='new-'+fmt for l in snapshot['leagues'])

@pytest.mark.parametrize('count',range(2,41))
def test_round_robin_complete_and_balanced_for_every_allowed_size(count):
    from app.domain.fixtures import generate_round_robin
    from collections import Counter
    teams=['__bye__']+[f't{i}' for i in range(1,count)]
    rounds=generate_round_robin(teams,legs=2)['rounds']
    pairs=Counter()
    for leg in (1,2):
        home,away=Counter(),Counter()
        for rd in rounds:
            occupied=[]
            for match in rd['matches']:
                if match['leg']!=leg:continue
                home[match['home']]+=1;away[match['away']]+=1
                occupied.extend([match['home'],match['away']])
                pairs[match['home'],match['away']]+=1
            assert len(occupied)==len(set(occupied))
        assert sum(home.values())==count*(count-1)//2
        assert all(abs(home[t]-away[t])<=1 for t in teams)
    assert all(pairs[a,b]==1 for a in teams for b in teams if a!=b)

def test_scheduled_price_is_the_price_actually_charged(client):
    db_state.variants['var-jersey-001-M']['scheduled_prices']=[{'effective_at':'2020-01-01T00:00:00Z','price_minor':500000}]
    headers=auth(client,'viewer')
    r=client.post('/api/v1/mobile/checkout',headers=headers,json={'order_id':'changed-price','items':[{'variant_id':'var-jersey-001-M','quantity':1}],'payment':{'token':'tok_success'}})
    assert r.status_code==201,r.text
    assert r.json()['total_minor']==500000
    assert r.json()['receipt']['payload']['items'][0]['unit_price_minor']==500000

@pytest.mark.parametrize('role,expected',[('admin',201),('manager',201),('organizer',403),('player',403),('viewer',403)])
def test_product_creation_role_boundary(client,role,expected):
    payload={'product_id':'new-product','variant_id':'new-variant','club_id':'club-alpha-1','name':'Club scarf','category':'accessories','price_minor':120000,'stock':2}
    response=client.post('/api/v1/mobile/products',headers=auth(client,role),json=payload)
    assert response.status_code==expected,response.text

def test_manager_cannot_create_product_in_foreign_club(client):
    payload={'product_id':'foreign-product','variant_id':'foreign-variant','club_id':'club-alpha-2','name':'Club scarf','category':'accessories','price_minor':120000,'stock':2}
    assert client.post('/api/v1/mobile/products',headers=auth(client,'manager'),json=payload).status_code==403

def test_fulfilment_events_and_foreign_order_boundary(client):
    headers=auth(client,'viewer')
    result=client.post('/api/v1/mobile/checkout',headers=headers,json={'order_id':'fulfil','items':[{'variant_id':'var-jersey-001-L','quantity':1}],'payment':{'token':'tok_success'}})
    assert result.status_code==201
    manager=auth(client,'manager')
    for state in ['packed','shipped','delivered']:
        r=client.post('/api/v1/mobile/orders/fulfil/transition',headers=manager,json={'status':state})
        assert r.status_code==200,r.text
    assert [e['status'] for e in db_state.order_events]==['paid','packed','shipped','delivered']
    assert client.post('/api/v1/mobile/orders/fulfil/transition',headers=manager,json={'status':'packed'}).status_code==409

def test_player_role_assignment_is_audited_and_scoped(client):
    payload={'role':'vice_captain','reason':'Team selection'}
    assert client.post('/api/v1/mobile/players/player-alpha-2/role',headers=auth(client,'manager'),json=payload).status_code==403
    result=client.post('/api/v1/mobile/players/player-alpha-1/role',headers=auth(client,'manager'),json=payload)
    assert result.status_code==200
    assert db_state.roster_players['player-alpha-1']['role']=='vice_captain'
    assert result.json()['who']=='mgr-1' and result.json()['why']=='Team selection'

def test_live_match_keeps_old_player_eligibility_until_match_end(client):
    manager=auth(client,'manager')
    r=client.post('/api/v1/mobile/roster',headers=manager,json={'request_id':'live-move','league_id':'league-alpha-1','player_id':'player-alpha-1','type':'transfer','from_squad_id':'squad-alpha-1','to_squad_id':'squad-alpha-2','effective_date':'2026-10-18','reason':'Next fixture','requested_by':'ignored'})
    assert r.status_code==201,r.text
    assert r.json()['state']=='deferred_until_match_end'
    player=db_state.roster_players['player-alpha-1']
    assert player['squad_id']=='squad-alpha-2'
    assert player['match_eligibility']['demo-match-1']['squad_id']=='squad-alpha-1'
    ended=client.post('/api/v1/mobile/events',headers=auth(client,'organizer'),json={'event_id':'eligibility-end','match_id':'demo-match-1','type':'match_end','payload':{}})
    assert ended.status_code==201,ended.text
    assert 'demo-match-1' not in player['match_eligibility']
    assert db_state.roster_audit[-1]['state']=='deferred_until_match_end'
