from __future__ import annotations
import math
from dataclasses import dataclass
from collections import Counter
from core.schemas import Interpretation,OpenStatus
from core.geo import haversine,travel
from core.hours import covers_visit,local_time
from core.settings import CONFIG

MIN_VISIT={'cafe':15,'restaurant':25,'museum':30,'gallery':20,'park':10,'playground':15,'viewpoint':10,'attraction':10,'cinema':90,'theatre':60,'library':20,'shopping':15,'bar':20,'nightclub':30}
PREFERRED={'cafe':25,'restaurant':40,'museum':50,'gallery':30,'park':30,'playground':30,'viewpoint':15,'attraction':20,'cinema':100,'theatre':90,'library':30,'shopping':30,'bar':30,'nightclub':45}
ACTIVITY={'park':'walk','attraction':'look','viewpoint':'look','cafe':'coffee','restaurant':'eat','museum':'browse','gallery':'browse','playground':'play','cinema':'show','theatre':'show','library':'read','shopping':'browse','bar':'browse','nightclub':'browse'}

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

def filter_candidates(pois,location,now,intent:Interpretation):
    accepted=[];rejected=[]
    night=local_time(now).hour>=22 or local_time(now).hour<6
    for p in pois:
        d=round(haversine(*location,p['lat'],p['lon']))
        w,t=travel(d,intent.mode)
        visit=min(PREFERRED.get(p['category'],20),intent.duration_min-2*t)
        reason=''
        if t>intent.max_travel_min:reason='travel_limit'
        elif p['category'] not in intent.categories:reason='category'
        elif p['tags'].get('access') in {'private','no','customers_only'}:reason='restricted_access'
        elif p['tags'].get('disused')=='yes' or p['tags'].get('abandoned')=='yes':reason='disused'
        elif 'accessible' in intent.constraints and p.get('wheelchair')!='yes':reason='wheelchair_unconfirmed'
        elif 'children' in intent.constraints and p['category'] in {'bar','nightclub'}:reason='children'
        elif visit<MIN_VISIT.get(p['category'],10):reason='time_budget'
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
        else:accepted.append(Candidate(p,d,w,t,visit,status))
    return accepted,rejected

def rank(candidates,scores,intent):
    weights=CONFIG['weights']
    for c in candidates:
        pop=c.poi.get('popularity')
        rating=c.poi.get('rating')
        popularity=float(rating)/5 if isinstance(rating,(int,float)) else (float(pop) if isinstance(pop,(int,float)) else 0)
        parts={'semantic':scores.get(c.poi['id'],0)*weights['semantic'],
               'distance':math.exp(-c.travel_min/15)*weights['distance'],
               'category':weights['category'] if c.poi['category'] in intent.categories else 0,
               'open':weights['open'] if c.open_status.state=='open' and c.open_status.confidence=='high' else 0,
               'popularity':max(0,min(1,popularity))*weights['popularity'],
               'gold':weights['gold'] if c.poi.get('gold_reviewed') else 0,
               'unknown':-weights['unknown_penalty'] if c.open_status.state=='unknown' else 0}
        c.score=sum(parts.values());c.score_parts={k:round(v,4) for k,v in parts.items()}
    return sorted(candidates,key=lambda c:(-c.score,c.distance_m,c.poi['id']))

def diversify(candidates,limit=3):
    counts=Counter();selected=[]
    for c in candidates:
        if counts[c.poi['category']]>=2:continue
        selected.append(c);counts[c.poi['category']]+=1
        if len(selected)==limit:break
    return selected

def candidate_pool(candidates,limit=10):
    # Reserve diverse top recommendations before filling the remaining LLM context.
    first=diversify(candidates)
    ids={c.poi['id'] for c in first}
    return (first+[c for c in candidates if c.poi['id'] not in ids])[:limit]
