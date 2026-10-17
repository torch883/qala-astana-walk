from itertools import permutations
from datetime import timedelta
from core.geo import haversine,travel
from core.hours import covers_visit
from core.schemas import Route,RouteStop

def build_route(recs,pois,location,now,intent):
    if len(recs)<2:return None
    options=[]
    for order in permutations(recs):
        elapsed=0;prev=location;stops=[];valid=True
        for r in order:
            p=pois[r.poi_id]
            _,leg=travel(round(haversine(*prev,p['lat'],p['lon'])),intent.mode)
            ok,_,_=covers_visit(p.get('opening_hours'),now+timedelta(minutes=elapsed),leg,r.visit_min)
            if not ok or leg>intent.max_travel_min:valid=False;break
            stops.append(RouteStop(poi_id=r.poi_id,travel_min=leg,visit_min=r.visit_min,arrival_min=elapsed+leg,departure_min=elapsed+leg+r.visit_min))
            elapsed+=leg+r.visit_min;prev=(p['lat'],p['lon'])
        _,back=travel(round(haversine(*prev,*location)),intent.mode)
        if valid and elapsed+back<=intent.duration_min:
            options.append(Route(stops=stops,total_min=elapsed+back,return_min=back,basis='straight_line_x1.3_estimate_including_return'))
    return min(options,key=lambda r:r.total_min) if options else None
