"""Optional local map context for a tile-free demo, not a routing graph."""
import json
from core.settings import DATA
from data.collect import fetch

def main():
    query='[out:json][timeout:90];(way[highway~"^(primary|secondary|tertiary|pedestrian)$"](51.02,71.38,51.18,71.48);way[waterway=river](51.02,71.38,51.18,71.48););out geom;'
    raw=fetch(query,DATA/'raw/map_context.json')
    features=[]
    for w in raw['elements']:
        pts=[[p['lon'],p['lat']] for p in w.get('geometry',[]) if 'lon' in p]
        if len(pts)>1:features.append({'type':'Feature','properties':{'kind':'river' if w.get('tags',{}).get('waterway') else 'road','name':w.get('tags',{}).get('name','')},'geometry':{'type':'LineString','coordinates':pts}})
    (DATA/'map_context.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Local context lines:',len(features))

if __name__=='__main__':main()
