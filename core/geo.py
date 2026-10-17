from __future__ import annotations
import json
import math
from functools import lru_cache
from shapely.geometry import Point,shape
from core.settings import DATA, CONFIG

def haversine(lat1,lon1,lat2,lon2):
    a,b=math.radians(lat1),math.radians(lat2)
    dlat,dlon=b-a,math.radians(lon2-lon1)
    h=math.sin(dlat/2)**2+math.cos(a)*math.cos(b)*math.sin(dlon/2)**2
    return 6371008.8*2*math.asin(min(1,math.sqrt(h)))

def round_location(lat,lon):
    if not math.isfinite(lat) or not math.isfinite(lon) or not(-90<=lat<=90 and -180<=lon<=180):
        raise ValueError('invalid_coordinates')
    # At 51N: ~111 x 140 m grid. Only rounded coordinates enter the engine.
    return round(lat,3), round(lon*500)/500

def travel(distance_m,mode='walk'):
    walk=math.ceil(distance_m*CONFIG['detour_factor']/CONFIG['walk_m_per_min'])
    moving=walk if mode=='walk' else math.ceil(distance_m*CONFIG['detour_factor']/CONFIG['transport_m_per_min'])+CONFIG['transport_overhead_min']
    return walk,moving

@lru_cache(maxsize=1)
def city_boundary():
    return shape(json.loads((DATA/'boundary.geojson').read_text(encoding='utf-8'))['geometry'])

def in_city(location):
    return city_boundary().covers(Point(location[1],location[0]))
