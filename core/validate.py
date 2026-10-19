from collections import Counter
import re
from core.schemas import Answer
from core.security import safe_text
from core.settings import CONFIG

def validate_weather(r,c,intent,weather):
    if r.shelter!=c.shelter or r.warm_route!=c.warm or r.outdoor_min!=c.outdoor_min:raise ValueError('weather_mismatch')
    if weather is None or weather.level!='harsh':return
    if r.shelter!='indoor':raise ValueError('weather_outdoor')
    if intent.mode=='walk':
        cap=CONFIG['weather']['harsh_outdoor_leg_min']
        legs=r.warm_route.outdoor_legs_min if r.warm_route else [r.outdoor_min]
        if any(x is None or x>cap for x in legs):raise ValueError('weather_exposure')
        if r.warm_route and r.travel_min<r.warm_route.travel_min:raise ValueError('weather_travel')

def validate_answer(answer:Answer,candidates,intent,weather=None):
    if answer.response_type!='recommendations':
        if answer.recommendations:raise ValueError('non_recommendation_has_pois')
        return True
    recs=answer.recommendations
    if not 1<=len(recs)<=3:raise ValueError('count')
    pool={c.poi['id']:c for c in candidates}
    if len({r.poi_id for r in recs})!=len(recs):raise ValueError('duplicate')
    counts=Counter()
    for r in recs:
        if r.poi_id not in pool:raise ValueError('unknown_id')
        c=pool[r.poi_id];p=c.poi
        counts[p['category']]+=1
        if r.distance_m!=c.distance_m or r.walk_min!=c.walk_min or r.travel_min!=c.travel_min:raise ValueError('distance_mismatch')
        if r.name!=safe_text(p.get('name_'+intent.language) or p['name'],200):raise ValueError('name_mismatch')
        if r.open_status!=c.open_status or r.open_status.state=='closed':raise ValueError('hours_mismatch')
        if r.open_status.state=='open' and r.open_status.confidence!='high':raise ValueError('unconfirmed_open')
        if r.open_status.state=='unknown' and not r.caveats:raise ValueError('missing_caveat')
        if r.open_status.state!='open' or r.open_status.confidence!='high':
            if re.search(r'открыт[оаы]?\s+сейчас|сейчас\s+открыт|open\s+now|қазір\s+ашық',r.why+' '+r.what_to_do,re.I):raise ValueError('unsupported_open_claim')
        if r.travel_min>intent.max_travel_min or 2*r.travel_min+r.visit_min>intent.duration_min:raise ValueError('budget')
        if r.source_url!=p['source'] or r.source!='poi_data' or r.idea_source!='generated_idea':raise ValueError('source')
        for field,expected in {'visit_min':'generated_idea','what_to_do':'generated_idea','distance_m':'calculated','open_status':'poi_data'}.items():
            if r.field_sources.get(field)!=expected:raise ValueError('field_source')
        if r.lat!=p['lat'] or r.lon!=p['lon'] or r.category!=p['category']:raise ValueError('fact_mismatch')
        if not all([r.why,r.what_to_do,r.data_used]):raise ValueError('missing_fields')
        validate_weather(r,c,intent,weather)
    if max(counts.values())>2:raise ValueError('diversity')
    return True
