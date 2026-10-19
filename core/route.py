from itertools import permutations
from datetime import timedelta
from core.geo import haversine,travel
from core.hours import covers_visit
from core.schemas import Route,RouteStop
from core.settings import CONFIG

def leg_min(a,b,at,intent,weather=None,env=None):
    """Minutes for one leg; in harsh weather a walk needs short outdoor stretches, else None (leg not allowed)."""
    _,t=travel(round(haversine(*a,*b)),intent.mode)
    if weather is None or weather.level!='harsh' or env is None or intent.mode!='walk':return t
    cap=CONFIG['weather']['harsh_outdoor_leg_min']
    if env.hubs.outdoor_min(a,b)<=cap:return t
    warm=env.hubs.warm_path(a,b,at,cap,intent.language)
    return max(t,warm.travel_min) if warm else None

def build_route(recs,pois,location,now,intent,weather=None,env=None):
    if len(recs)<2:return None
    options=[]
    for order in permutations(recs):
        elapsed=0;prev=location;stops=[];valid=True
        for r in order:
            p=pois[r.poi_id]
            leg=leg_min(prev,(p['lat'],p['lon']),now+timedelta(minutes=elapsed),intent,weather,env)
            if leg is None:valid=False;break
            ok,_,_=covers_visit(p.get('opening_hours'),now+timedelta(minutes=elapsed),leg,r.visit_min)
            if not ok or leg>intent.max_travel_min:valid=False;break
            stops.append(RouteStop(poi_id=r.poi_id,travel_min=leg,visit_min=r.visit_min,arrival_min=elapsed+leg,departure_min=elapsed+leg+r.visit_min))
            elapsed+=leg+r.visit_min;prev=(p['lat'],p['lon'])
        back=leg_min(prev,location,now+timedelta(minutes=elapsed),intent,weather,env) if valid else None
        if valid and back is not None and elapsed+back<=intent.duration_min:
            options.append(Route(stops=stops,total_min=elapsed+back,return_min=back,basis='straight_line_x1.3_estimate_including_return'))
    return min(options,key=lambda r:r.total_min) if options else None
