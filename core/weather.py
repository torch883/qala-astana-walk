"""Weather context and warm routes. Open-Meteo (CC BY 4.0) gets only the fixed city centre and the selected hour, never the user's location."""
from __future__ import annotations
import json,math
from functools import lru_cache
import numpy as np
import requests
import shapely
from shapely.geometry import Point,shape
from shapely.ops import nearest_points
from shapely.strtree import STRtree
from core.schemas import Weather,WarmRoute
from core.settings import CONFIG,DATA
from core.hours import evaluate,local_time

CITY_CENTRE=(51.13,71.43)
API='https://api.open-meteo.com/v1/forecast'
INDOOR={'cafe','restaurant','museum','gallery','cinema','theatre','library','shopping','bar','nightclub','entertainment','sport'}
OUTDOOR_TAGS={'pitch','track','stadium','miniature_golf','park','garden','playground','picnic_site','artwork','viewpoint'}
STORM={95,96,97,99}

def classify(feels_like_c,wind_ms,gust_ms,precip_mm,code):
    w=CONFIG['weather'];harsh=[];caution=[]
    if feels_like_c<=w['harsh_feels_like_c']:harsh.append('cold')
    elif feels_like_c<=w['caution_feels_like_c']:caution.append('cold')
    if feels_like_c>=w['harsh_heat_c']:harsh.append('heat')
    elif feels_like_c>=w['caution_heat_c']:caution.append('heat')
    if wind_ms>=w['harsh_wind_ms'] or gust_ms>=w['harsh_gust_ms']:harsh.append('wind')
    elif wind_ms>=w['caution_wind_ms']:caution.append('wind')
    if code in STORM:harsh.append('storm')
    if precip_mm>=w['harsh_precip_mm']:harsh.append('precip')
    elif precip_mm>=w['caution_precip_mm']:caution.append('precip')
    return ('harsh' if harsh else 'caution' if caution else 'ok'),harsh or caution

def make(at,temperature_c,feels_like_c,wind_ms,gust_ms=0.0,precip_mm=0.0,code=0,source='manual'):
    level,reasons=classify(feels_like_c,wind_ms,gust_ms,precip_mm,code)
    return Weather(at=local_time(at).replace(minute=0,second=0,microsecond=0).isoformat(),temperature_c=round(temperature_c,1),feels_like_c=round(feels_like_c,1),wind_ms=round(wind_ms,1),gust_ms=round(gust_ms,1),precip_mm=round(precip_mm,1),code=int(code),level=level,reasons=reasons,source=source)

# Scenario presets for demos and the offline eval; shown as "manual" in the UI, never as a forecast.
PRESETS={'frost':dict(temperature_c=-24,feels_like_c=-32,wind_ms=7,gust_ms=11,code=3),
         'blizzard':dict(temperature_c=-14,feels_like_c=-25,wind_ms=15,gust_ms=21,precip_mm=1.2,code=75),
         'rain':dict(temperature_c=11,feels_like_c=8,wind_ms=5,gust_ms=9,precip_mm=0.6,code=61),
         'heat':dict(temperature_c=36,feels_like_c=37,wind_ms=3,gust_ms=6,code=0),
         'mild':dict(temperature_c=18,feels_like_c=18,wind_ms=3,gust_ms=5,code=1)}

def preset(name,at):return make(at,**PRESETS[name])

def fetch(at,timeout=2.0):
    """Forecast for the hour containing `at`; None on any failure, and weather is then not used."""
    at=local_time(at)
    try:
        r=requests.get(API,params={'latitude':CITY_CENTRE[0],'longitude':CITY_CENTRE[1],'hourly':'temperature_2m,apparent_temperature,wind_speed_10m,wind_gusts_10m,precipitation,weather_code','wind_speed_unit':'ms','timezone':CONFIG['timezone'],'start_date':at.date().isoformat(),'end_date':at.date().isoformat()},timeout=timeout)
        r.raise_for_status();h=r.json()['hourly']
        i=h['time'].index(at.strftime('%Y-%m-%dT%H:00'))
        values=[h[k][i] for k in ['temperature_2m','apparent_temperature','wind_speed_10m','wind_gusts_10m','precipitation','weather_code']]
        if any(v is None for v in values):return None
        return make(at,*values,source='open-meteo')
    except (requests.RequestException,ValueError,KeyError,IndexError,TypeError):
        return None

def shelter(p,in_hub=False):
    t=p.get('tags',{})
    if in_hub or t.get('indoor') in {'yes','room','area'} or t.get('location') in {'indoor','underground'}:return 'indoor'
    if t.get('leisure') in OUTDOOR_TAGS or t.get('tourism') in OUTDOOR_TAGS:return 'outdoor'
    if p['category'] in INDOOR:return 'indoor'
    # Monuments without a building tag, parks and playgrounds stay outdoor.
    return 'indoor' if t.get('building') not in (None,'no','roof') else 'outdoor'

# Local equirectangular projection around Astana in metres; error <1% inside the city.
KX,KY=111320*math.cos(math.radians(CITY_CENTRE[0])),110540

def to_metric(geom):return shapely.transform(geom,lambda c:np.column_stack(((c[:,0]-CITY_CENTRE[1])*KX,(c[:,1]-CITY_CENTRE[0])*KY)))

def point_m(lat,lon):return Point((lon-CITY_CENTRE[1])*KX,(lat-CITY_CENTRE[0])*KY)

def walk_minutes(metres):return math.ceil(metres*CONFIG['detour_factor']/CONFIG['walk_m_per_min'])

class Hubs:
    """Public indoor places from OSM (malls, the railway station) used as warm stops."""
    def __init__(self,path=None):
        path=path or DATA/'warm_hubs.geojson'
        features=json.loads(path.read_text(encoding='utf-8'))['features'] if path.exists() else []
        self.props=[f['properties'] for f in features]
        self.geoms=[to_metric(shape(f['geometry'])) for f in features]
        self.tree=STRtree(self.geoms) if self.geoms else None

    def __len__(self):return len(self.geoms)

    def containing(self,lat,lon,buffer_m=25):
        if not self.tree:return None
        pt=point_m(lat,lon)
        for i in self.tree.query(pt.buffer(buffer_m)):
            if self.geoms[int(i)].buffer(buffer_m).covers(pt):return int(i)
        return None

    def _end(self,lat,lon):
        i=self.containing(lat,lon)
        return (self.geoms[i],i) if i is not None else (point_m(lat,lon),None)

    def outdoor_min(self,a,b):
        """Minutes outside on a direct walk; walking inside a hub at either end does not count."""
        (ga,ia),(gb,ib)=self._end(*a),self._end(*b)
        if ia is not None and ia==ib:return 0
        return walk_minutes(ga.distance(gb))

    def open_at(self,i,at):
        s=evaluate(self.props[i].get('opening_hours'),at);confirmed=s.state=='open' and s.confidence=='high'
        # At night a hub with unknown hours is assumed closed; by day it is usable with a caveat.
        night=local_time(at).hour>=22 or local_time(at).hour<6
        return (confirmed if night else s.state!='closed'),confirmed

    def warm_path(self,a,b,at,cap_min,lang='ru'):
        """Best detour through one usable hub so that every outdoor stretch is at most cap_min."""
        if not self.tree:return None
        (ga,ia),(gb,ib)=self._end(*a),self._end(*b)
        best=None
        for i in self.tree.query(ga.buffer(ga.distance(gb)+200)):
            i=int(i)
            if i in {ia,ib}:continue
            usable,confirmed=self.open_at(i,at)
            if not usable:continue
            h=self.geoms[i];leg1,leg2=ga.distance(h),h.distance(gb)
            inside=nearest_points(ga,h)[1].distance(nearest_points(h,gb)[0])
            out1,out2=walk_minutes(leg1),walk_minutes(leg2)
            if max(out1,out2)>cap_min:continue
            key=(max(out1,out2),out1+out2,walk_minutes(leg1+inside+leg2))
            if best is None or key<best[0]:
                p=self.props[i]
                best=(key,WarmRoute(hub_id=p['id'],hub_name=p.get('name_'+lang) or p['name'],hub_lat=p['lat'],hub_lon=p['lon'],hub_source_url=p['source'],outdoor_legs_min=[out1,out2],outdoor_total_min=out1+out2,travel_min=key[2],hub_hours_confirmed=confirmed))
        return best[1] if best else None

@lru_cache(maxsize=1)
def hubs():return Hubs()

class Env:
    """Per-engine weather context: warm hubs and an indoor/outdoor label for every POI (shops inside malls are indoor)."""
    def __init__(self,pois,warm_hubs=None):
        self.hubs=warm_hubs if warm_hubs is not None else hubs()
        self.shelter={p['id']:shelter(p,self.hubs.containing(p['lat'],p['lon']) is not None) for p in pois}

def advice(weather,lang):
    """One short caveat for the current weather, or '' when it does not matter."""
    from core.i18n import tr
    if weather is None or weather.level=='ok':return ''
    parts=[]
    for r in weather.reasons:
        parts.append(tr(lang,'weather_'+r).format(feels=round(weather.feels_like_c),wind=round(max(weather.wind_ms,weather.gust_ms))))
    return ' '.join(parts)
