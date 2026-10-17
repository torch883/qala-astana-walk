"""Warm hubs: outlines of public indoor places (malls, the railway station) from OSM. Reproducible from data/raw/warm_hubs.json."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from shapely.geometry import Polygon,mapping,shape
from data.collect import fetch
from core.settings import DATA
from core.weather import to_metric

MIN_AREA_M2=2000

def mall_way_ids():
    # Malls already collected in the POI snapshot; outlines are fetched by id to keep the Overpass query light.
    elements=json.loads((DATA/'raw/pois.json').read_text(encoding='utf-8'))['elements']
    return sorted(e['id'] for e in elements if e['type']=='way' and e.get('tags',{}).get('shop')=='mall')

def build(refresh=False):
    boundary=shape(json.loads((DATA/'boundary.geojson').read_text(encoding='utf-8'))['geometry'])
    w,s,e,n=boundary.bounds
    query=f'[out:json][timeout:60];(way(id:{",".join(map(str,mall_way_ids()))});way[building=train_station]({s},{w},{n},{e}););out geom tags;'
    raw=fetch(query,DATA/'raw/warm_hubs.json',refresh=refresh)
    collected_at=datetime.now(timezone.utc).isoformat();features=[];skipped={'unnamed':0,'light_rail':0,'open_ring':0,'outside':0,'small':0}
    for el in raw['elements']:
        tags=el.get('tags',{});pts=[(v['lon'],v['lat']) for v in el.get('geometry',[])]
        if not tags.get('name'):skipped['unnamed']+=1;continue
        # LRT stations are small and their opening to through-walkers is not verified; only the railway station stays.
        if tags.get('station')=='light_rail' or tags.get('light_rail')=='yes':skipped['light_rail']+=1;continue
        if len(pts)<4 or pts[0]!=pts[-1]:skipped['open_ring']+=1;continue
        poly=Polygon(pts).buffer(0)
        if not boundary.covers(poly.centroid):skipped['outside']+=1;continue
        area=to_metric(poly).area
        if area<MIN_AREA_M2:skipped['small']+=1;continue
        c=poly.representative_point()
        features.append({'type':'Feature','geometry':mapping(poly),'properties':{'id':f'way/{el["id"]}','name':tags['name'],'name_ru':tags.get('name:ru') or tags['name'],'name_en':tags.get('name:en') or tags['name'],'name_kk':tags.get('name:kk') or tags['name'],'kind':'mall' if tags.get('shop')=='mall' else 'station','lat':round(c.y,6),'lon':round(c.x,6),'area_m2':round(area),'opening_hours':tags.get('opening_hours'),'source':f'https://www.openstreetmap.org/way/{el["id"]}','collected_at':collected_at}})
    features.sort(key=lambda f:f['properties']['id'])
    (DATA/'warm_hubs.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False),encoding='utf-8')
    print(f'Warm hubs: {len(features)} kept; skipped {skipped}')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--refresh',action='store_true');args=ap.parse_args()
    build(refresh=args.refresh)
