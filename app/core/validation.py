"""Strict contract schemas; schema errors always precede domain rule checks."""
from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from app.core.errors import AppException

Id = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]

class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

def validate(model, data):
    try:
        return model.model_validate(data).model_dump(exclude_unset=True)
    except ValidationError as exc:
        fields = sorted({'.'.join(map(str,e['loc'])) or 'body' for e in exc.errors()})
        raise AppException("VALIDATION_ERROR", "Please check the supplied fields.", {"fields": fields}, 400)

class Event(Contract):
    event_id: Id
    match_id: Id
    type: Literal['match_init','match_start','score','discipline','tiebreak_winner','match_end','compensation','match_postpone','match_resume','match_abandon','match_cancel']
    payload: dict

class Fixture(Contract):
    match_id: Id
    home: Id
    away: Id

class Points(Contract):
    win: int = 3
    draw: int = 1
    loss: int = 0

class Qualification(Contract):
    spots: int = Field(ge=1)

class League(Contract):
    league_id: Id
    sport_id: Id
    teams: list[Id] = Field(min_length=2,max_length=40)
    fixtures: list[Fixture]
    qualification: Qualification
    points: Points = Field(default_factory=Points)
    tie_break_order: list[Literal['h2h_points','h2h_diff','overall_diff','scored','fair_play','draw_lots']] | None = None
    lots_seed: int | None = None

class Transfer(Contract):
    request_id: Id
    league_id: Id
    player_id: Id
    type: Literal['transfer','loan','release']
    from_squad_id: Id
    to_squad_id: Id | None = None
    effective_date: str
    loan_end_date: str | None = None
    reason: str
    requested_by: Id

    @field_validator('effective_date','loan_end_date')
    @classmethod
    def dates(cls,value):
        if value is not None:
            if len(value)!=10 or date.fromisoformat(value).isoformat()!=value:
                raise ValueError('Use YYYY-MM-DD')
        return value

class Window(Contract):
    open: str
    close: str

    @field_validator('open','close')
    @classmethod
    def dates(cls,value):
        if len(value)!=10 or date.fromisoformat(value).isoformat()!=value:
            raise ValueError('Use YYYY-MM-DD')
        return value

class RosterLeague(Contract):
    league_id: Id
    tenant_id: Id
    sport_id: Id
    transfer_window: Window
    max_squad_size: int = Field(default=25,ge=1)
    required_positions: dict[str,Annotated[int,Field(ge=0)]] = Field(default_factory=dict)

class Squad(Contract):
    squad_id: Id
    club_id: Id
    tenant_id: Id
    name: str

class Player(Contract):
    player_id: Id
    name: str
    position: str
    squad_id: Id
    role: Literal['captain','vice_captain','starter','substitute'] = 'starter'

class LiveMatch(Contract):
    match_id: Id
    home_squad_id: Id
    away_squad_id: Id

class RosterSetup(Contract):
    league: RosterLeague
    squads: list[Squad]
    players: list[Player]
    matches_in_progress: list[LiveMatch] = Field(default_factory=list)
