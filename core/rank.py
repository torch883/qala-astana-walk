from __future__ import annotations
import math
from dataclasses import dataclass
from collections import Counter
from core.schemas import Interpretation,OpenStatus,WarmRoute
from core.geo import haversine,travel
from core.hours import covers_visit,local_time
from core.settings import CONFIG

MIN_VISIT={'cafe':15,'restaurant':25,'museum':30,'gallery':20,'park':10,'playground':15,'viewpoint':10,'attraction':10,'cinema':90,'theatre':60,'library':20,'shopping':15,'bar':20,'nightclub':30,'entertainment':30,'sport':30,'culture':20}
PREFERRED={'cafe':25,'restaurant':40,'museum':50,'gallery':30,'park':30,'playground':30,'viewpoint':15,'attraction':20,'cinema':100,'theatre':90,'library':30,'shopping':30,'bar':30,'nightclub':45,'entertainment':60,'sport':60,'culture':45}
ACTIVITY={'park':'walk','attraction':'look','viewpoint':'look','cafe':'coffee','restaurant':'eat','museum':'browse','gallery':'browse','playground':'play','cinema':'show','theatre':'show','library':'read','shopping':'browse','bar':'browse','nightclub':'browse','entertainment':'fun','sport':'sport','culture':'browse'}

def popularity(p):
    # A real rating wins; without one, a Wikidata/Wikipedia link in OSM marks a notable place.
    rating=p.get('rating');pop=p.get('popularity')
    if isinstance(rating,(int,float)):return max(0,min(1,float(rating)/5))
    if isinstance(pop,(int,float)):return max(0,min(1,float(pop)))
    return 1.0 if p['tags'].get('wikidata') or p['tags'].get('wikipedia') else 0.0

@dataclass
class Candidate:
    poi: dict
    distance_m: int
    walk_min: int
    travel_min: int
    visit_min: int
    open_status: OpenStatus
    score: float=0
    score_parts: dict | None=None
    shelter: str | None=None
    outdoor_min: int | None=None
    warm: WarmRoute | None=None

def weather_check(p,location,now,intent,env,t):
    """Harsh weather: outdoor places are excluded; a walk keeps every stretch outside short, through a mall if needed."""
    if env.shelter[p['id']]=='outdoor':return 'weather_outdoor',t,None,None
    if intent.mode!='walk':return '',t,None,None
    cap=CONFIG['weather']['harsh_outdoor_leg_min'];target=(p['lat'],p['lon'])
    outdoor=env.hubs.outdoor_min(location,target)
    if outdoor<=cap:return '',t,outdoor,None
    warm=env.hubs.warm_path(location,target,now,cap,intent.language)
    if not warm:return 'weather_exposure',t,outdoor,None
    return '',max(t,warm.travel_min),warm.outdoor_total_min,warm

def filter_candidates(pois,location,now,intent:Interpretation,weather=None,env=None,deadline=None):
    accepted=[];rejected=[]
    night=local_time(now).hour>=22 or local_time(now).hour<6
    harsh=weather is not None and weather.level=='harsh' and env is not None
    budget=intent.duration_min
    if deadline is not None:budget=min(budget,int((local_time(deadline)-local_time(now)).total_seconds()//60))
    for p in pois:
        d=round(haversine(*location,p['lat'],p['lon']))
        w,t=travel(d,intent.mode);outdoor=warm=None
        reason=''
        if t>intent.max_travel_min:reason='travel_limit'
        elif p['category'] not in intent.categories:reason='category'
        elif p['tags'].get('access') in {'private','no','customers_only'}:reason='restricted_access'
        elif p['tags'].get('disused')=='yes' or p['tags'].get('abandoned')=='yes':reason='disused'
        elif 'accessible' in intent.constraints and p.get('wheelchair')!='yes':reason='wheelchair_unconfirmed'
        elif 'children' in intent.constraints and (p['category'] in {'bar','nightclub'} or p['tags'].get('leisure')=='sauna'):reason='children'
        elif harsh:
            reason,t,outdoor,warm=weather_check(p,location,now,intent,env,t)
            if warm:w=t
            if not reason and t>intent.max_travel_min:reason='travel_limit'
        visit=min(PREFERRED.get(p['category'],20),budget-2*t)
        if not reason and visit<MIN_VISIT.get(p['category'],10):reason='time_budget'
        for feature in ['socket','wifi','quiet']:
            confirmed=p.get(feature) in {'yes','wlan'} or p['tags'].get(feature)=='yes'
            if not reason and 'require_'+feature in intent.constraints and not confirmed:reason=feature+'_unconfirmed'
        if reason:
            rejected.append({'poi_id':p['id'],'name':p['name'],'reason':reason,'distance_m':d,'travel_min':t})
            continue
        ok,status,hours_reason=covers_visit(p.get('opening_hours'),now,t,max(5,visit))
        if not reason and not ok:reason=hours_reason
        if not reason and night:
            if status.state!='open' or status.confidence!='high':reason='night_hours_unconfirmed'
            elif p['category'] in {'park','viewpoint','attraction','playground'} and p['tags'].get('lit')!='yes':reason='night_lighting_unconfirmed'
        if reason:
            rejected.append({'poi_id':p['id'],'name':p['name'],'reason':reason,'distance_m':d,'travel_min':t})
        else:accepted.append(Candidate(p,d,w,t,visit,status,shelter=env.shelter.get(p['id']) if env and weather else None,outdoor_min=outdoor,warm=warm))
    return accepted,rejected

def rank(candidates,scores,intent,weather=None):
    weights=CONFIG['weights']
    # Outdoor places drop in cold, wind, rain or heat; in harsh weather they are already filtered out.
    bad_weather=weather is not None and weather.level!='ok'
    # No category term: filter_candidates already admits only requested categories.
    for c in candidates:
        parts={'semantic':scores.get(c.poi['id'],0)*weights['semantic'],
               'distance':math.exp(-c.travel_min/15)*weights['distance'],
               'open':weights['open'] if c.open_status.state=='open' and c.open_status.confidence=='high' else 0,
               'popularity':popularity(c.poi)*weights['popularity'],
               # A tourist with little time is better served by notable sights than by an unnamed square.
               'tourist':popularity(c.poi)*weights['tourist_notability'] if 'tourist' in intent.constraints else 0,
               'gold':weights['gold'] if c.poi.get('gold_reviewed') else 0,
               'unknown':-weights['unknown_penalty'] if c.open_status.state=='unknown' else 0,
               'weather':-CONFIG['weather']['outdoor_penalty'] if bad_weather and c.shelter=='outdoor' else 0}
        c.score=sum(parts.values());c.score_parts={k:round(v,4) for k,v in parts.items()}
    return sorted(candidates,key=lambda c:(-c.score,c.distance_m,c.poi['id']))

def diversify(candidates,limit=3):
    counts=Counter();selected=[]
    for c in candidates:
        if counts[c.poi['category']]>=2:continue
        # Two identical «unnamed in OSM» labels are hard to tell apart; keep one, leave room for named places.
        if c.poi.get('name_generated') and counts['_generated']>=1:continue
        selected.append(c);counts[c.poi['category']]+=1;counts['_generated']+=bool(c.poi.get('name_generated'))
        if len(selected)==limit:break
    return selected

def candidate_pool(candidates,limit=10):
    # Reserve diverse top recommendations before filling the remaining LLM context.
    first=diversify(candidates)
    ids={c.poi['id'] for c in first}
    return (first+[c for c in candidates if c.poi['id'] not in ids])[:limit]
