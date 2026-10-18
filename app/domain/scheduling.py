"""Venue, team, shared-player and rest-window checks for manual rescheduling."""
from datetime import datetime, timedelta
from app.core.errors import AppException
from app.domain.models import db_state

def timestamp(value):
    try:
        if not isinstance(value,str) or len(value)!=20:
            raise ValueError()
        return datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ')
    except (ValueError,TypeError):
        raise AppException('VALIDATION_ERROR','Use UTC times such as 2026-10-18T09:00:00Z.',{'fields':['start','end']},400)

def reschedule(mid,data):
    if not isinstance(data,dict):
        raise AppException('VALIDATION_ERROR','Invalid schedule.',{'fields':['body']},400)
    start,end=timestamp(data.get('start')),timestamp(data.get('end'))
    rest=data.get('min_rest_minutes',30)
    if end<=start or type(rest) is not int or rest<0:
        raise AppException('VALIDATION_ERROR','End must follow start and rest cannot be negative.',{'fields':['end','min_rest_minutes']},400)
    venue=db_state.venues.get(data.get('venue_id'))
    if not venue:
        raise AppException('VENUE_NOT_FOUND','Venue not found.',{},404)
    match=db_state.matches[mid]
    teams={match['home_team_id'],match['away_team_id']}
    players={p['player_id'] for p in db_state.roster_players.values() if p.get('squad_id') in teams}
    conflicts=[]
    windows=venue.get('availability',[])
    if windows and not any(timestamp(w['start'])<=start and end<=timestamp(w['end']) for w in windows):
        conflicts.append({'type':'venue_unavailable','venue_id':venue['venue_id']})
    for other_id,schedule in db_state.schedules.items():
        if other_id==mid:continue
        other=db_state.matches.get(other_id)
        if not other:continue
        os,oe=timestamp(schedule['start']),timestamp(schedule['end'])
        other_teams={other['home_team_id'],other['away_team_id']}
        overlap=start<oe and os<end
        if overlap and venue['venue_id']==schedule['venue_id']:
            conflicts.append({'type':'venue_double_booking','venue_id':venue['venue_id'],'match_id':other_id})
        shared=teams&other_teams
        if shared and overlap:
            conflicts.append({'type':'team_overlap','team_ids':sorted(shared),'match_id':other_id})
        rest_window=timedelta(minutes=max(rest,schedule.get('min_rest_minutes',0)))
        if shared and not overlap and start<oe+rest_window and os<end+rest_window:
            conflicts.append({'type':'minimum_rest','team_ids':sorted(shared),'match_id':other_id})
        other_players={p['player_id'] for p in db_state.roster_players.values() if p.get('squad_id') in other_teams}
        shared_players=players&other_players
        if overlap and shared_players:
            conflicts.append({'type':'player_overlap','player_ids':sorted(shared_players),'match_id':other_id})
    if conflicts:
        raise AppException('SCHEDULE_CONFLICT','This time conflicts with another fixture or venue availability.',{'conflicts':conflicts},409)
    result={'match_id':mid,'venue_id':venue['venue_id'],'start':data['start'],'end':data['end'],'min_rest_minutes':rest}
    db_state.schedules[mid]=result
    return result
