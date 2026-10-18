"""Role-scoped administration used by the mobile management screens."""
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field, field_validator
from app.core.auth import authorize, current_user
from app.core.errors import AppException
from app.core.validation import Contract, Id
from app.domain.models import db_state

router = APIRouter(prefix='/api/v1/mobile')

class ProductInput(Contract):
    product_id: Id
    club_id: Id
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=500)
    category: Literal['apparel','accessories','digital']
    variant_id: Id
    size: str = Field(default='One size',max_length=40)
    color: str = Field(default='Standard',max_length=40)
    price_minor: int = Field(ge=1)
    stock: int = Field(ge=0)

def club_access(user,cid):
    club=db_state.clubs.get(cid)
    if not club:
        raise AppException('CLUB_NOT_FOUND','Club not found.',{},404)
    authorize(user,['club_manager'],tenant=club['tenant_id'],club=cid)
    return club

@router.post('/products',status_code=201)
def create_product(data: ProductInput,user=Depends(current_user)):
    club=club_access(user,data.club_id)
    if data.product_id in db_state.products or data.variant_id in db_state.variants:
        raise AppException('PRODUCT_EXISTS','This product or variant already exists.',{},409)
    db_state.products[data.product_id]={'product_id':data.product_id,'club_id':data.club_id,'tenant_id':club['tenant_id'],
        'name':data.name.strip(),'description':data.description,'category':data.category}
    db_state.variants[data.variant_id]={'variant_id':data.variant_id,'product_id':data.product_id,'price_minor':data.price_minor,
        'currency':'PKR','size':data.size,'color':data.color,'scheduled_prices':[]}
    db_state.stock[data.variant_id]=data.stock
    db_state.reserved[data.variant_id]=0
    return {'product_id':data.product_id,'variant_id':data.variant_id,'status':'created'}

class PriceChange(Contract):
    price_minor: int = Field(ge=1)
    effective_at: str

    @field_validator('effective_at')
    @classmethod
    def utc(cls,value):
        datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ')
        if len(value)!=20:raise ValueError('Use a UTC timestamp with seconds')
        return value

@router.post('/variants/{vid}/prices')
def schedule_price(vid:str,data:PriceChange,user=Depends(current_user)):
    variant=db_state.variants.get(vid)
    if not variant:raise AppException('VARIANT_NOT_FOUND','Variant not found.',{},404)
    product=db_state.products[variant['product_id']]
    club_access(user,product['club_id'])
    if any(x['effective_at']==data.effective_at for x in variant['scheduled_prices']):
        raise AppException('PRICE_EXISTS','A price is already scheduled for this time.',{},409)
    variant['scheduled_prices'].append(data.model_dump())
    return {'status':'scheduled',**data.model_dump()}

class PlayerRole(Contract):
    role: Literal['captain','vice_captain','starter','substitute']
    reason: str = Field(min_length=1,max_length=300)

@router.post('/players/{pid}/role')
def assign_role(pid:str,data:PlayerRole,user=Depends(current_user)):
    player=db_state.roster_players.get(pid)
    if not player:raise AppException('PLAYER_NOT_FOUND','Player not found.',{},404)
    squad=db_state.roster_squads.get(player['squad_id'])
    if not squad:raise AppException('SQUAD_NOT_FOUND','Player has no active squad.',{},404)
    club_access(user,squad['club_id'])
    player['role']=data.role
    entry={'audit_id':f'au-{len(db_state.roster_audit)+1:04d}','action':'role_assignment','player_id':pid,'league_id':player['league_id'],
        'from_squad_id':player['squad_id'],'to_squad_id':player['squad_id'],'effective_date':datetime.utcnow().date().isoformat(),
        'state':'active','who':user['sub'],'when':datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),'why':data.reason,'role':data.role}
    db_state.roster_audit.append(entry)
    return entry

class ProfileInput(Contract):
    name: str = Field(min_length=1,max_length=100)

@router.post('/profile')
def update_profile(data:ProfileInput,user=Depends(current_user)):
    db_state.users[user['email']]['name']=data.name.strip()
    pid=user.get('player_id')
    if pid in db_state.roster_players:db_state.roster_players[pid]['name']=data.name.strip()
    return {'status':'updated','name':data.name.strip()}

class TenantInput(Contract):
    tenant_id: Id
    name: str = Field(min_length=1,max_length=100)
    logo: str = Field(min_length=1,max_length=4)
    color: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')

@router.post('/tenants',status_code=201)
def create_tenant(data:TenantInput,user=Depends(current_user)):
    authorize(user,['super_admin'])
    if data.tenant_id in db_state.tenants:raise AppException('TENANT_EXISTS','This tenant already exists.',{},409)
    db_state.tenants[data.tenant_id]=data.model_dump()
    return {'status':'created','tenant':data.model_dump()}
