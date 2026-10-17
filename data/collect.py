"""Reproducible OSM collection. Never substitutes invented POIs on network failure."""
from __future__ import annotations
import argparse
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
import pandas as pd
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import polygonize, unary_union
from core.settings import DATA

ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter']
BOUNDARY_QUERY = '[out:json][timeout:90];rel[boundary=administrative]["ISO3166-2"="KZ-71"];out geom;'
AMENITIES = 'cafe|restaurant|fast_food|food_court|bar|pub|nightclub|theatre|cinema|library|arts_centre|planetarium'

def fetch(query: str, cache: Path, refresh=False):
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding='utf-8'))
    errors = []
    for endpoint in ENDPOINTS:
        try:
            response = requests.post(endpoint, data={'data': query}, headers={'User-Agent':'AstanaWalkHackathon/1.0 (OSM educational prototype)'}, timeout=(15, 110))
            if response.status_code in {400,403,406,500}:
                response=requests.get(endpoint,params={'data':query},headers={'User-Agent':'AstanaWalkHackathon/1.0'},timeout=(15,110))
            response.raise_for_status()
            result = response.json()
            if result.get('remark') or not result.get('elements'):
                raise ValueError(result.get('remark', 'empty response'))
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            return result
        except (requests.RequestException, ValueError) as exc:
            errors.append(f'{endpoint}: {type(exc).__name__}')
            print(errors[-1], flush=True)
    raise RuntimeError('Overpass unavailable; existing dataset was not overwritten. ' + '; '.join(errors))

def boundary_from_relation(element):
    outers, inners = [], []
    for member in element.get('members', []):
        if member.get('type') != 'way' or len(member.get('geometry', [])) < 2:
            continue
        line = LineString([(v['lon'],v['lat']) for v in member['geometry']])
        (inners if member.get('role') == 'inner' else outers).append(line)
    poly = unary_union(list(polygonize(unary_union(outers))))
    if inners:
        poly = poly.difference(unary_union(list(polygonize(unary_union(inners)))))
    if poly.is_empty or not poly.is_valid:
        raise ValueError('No valid administrative polygon; refusing bbox-only collection')
    return poly

def category(tags):
    a, t, l, s = (tags.get(k, '') for k in ('amenity','tourism','leisure','shop'))
    if a in {'cafe','restaurant','bar','nightclub','theatre','cinema','library'}: return a
    if a in {'fast_food','food_court','pub'}: return {'pub':'bar'}.get(a,'restaurant')
    if t in {'museum','gallery','viewpoint','attraction'}: return t
    if l in {'park','garden','nature_reserve'}: return 'park'
    if l in {'playground','amusement_arcade','indoor_play'}: return 'playground'
    if s: return 'shopping'
    if tags.get('historic') or tags.get('man_made')=='tower': return 'attraction'
    if tags.get('building')=='museum': return 'museum'
    if a=='planetarium': return 'museum'
    if a=='arts_centre': return 'leisure'
    if l: return 'leisure'
    if t: return 'tourism'
    return 'unknown'

CATEGORY_TEXT = {
    'cafe':'Кафе / coffee / кофе', 'restaurant':'Ресторан / restaurant / мейрамхана',
    'museum':'Музей / museum / мұражай', 'gallery':'Галерея / gallery',
    'park':'Парк / park / саябақ', 'playground':'Детская площадка или игровое пространство / playground / балалар',
    'viewpoint':'Смотровая точка / viewpoint', 'attraction':'Достопримечательность / landmark',
    'theatre':'Театр / theatre', 'cinema':'Кинотеатр / cinema', 'library':'Библиотека / library / кітапхана',
    'shopping':'Магазин или торговый центр / shopping', 'bar':'Бар / bar', 'nightclub':'Ночной клуб / nightclub',
    'leisure':'Досуг / leisure', 'tourism':'Туристический объект / tourism', 'unknown':'unknown'}

def clean(elements, boundary, collected_at):
    rows, seen = [], set()
    counts = {'raw':len(elements),'unnamed':0,'outside':0,'duplicates':0}
    for e in elements:
        tags = e.get('tags', {})
        name = tags.get('name:ru') or tags.get('name') or tags.get('name:kk') or tags.get('name:en')
        if not name or not name.strip(): counts['unnamed'] += 1; continue
        pt = e.get('center', e)
        lat, lon = pt.get('lat'), pt.get('lon')
        if lat is None or lon is None or not boundary.covers(Point(lon,lat)):
            counts['outside'] += 1; continue
        cat = category(tags)
        # Same named object represented as both a way and a node within 60 m.
        normalized = re.sub(r'[^\w]', '', name.casefold())
        duplicate = next((r for r in rows if r['_normalized']==normalized and r['category']==cat and math.hypot((r['lat']-lat)*111000,(r['lon']-lon)*70000)<60),None)
        ident = f"{e['type']}/{e['id']}"
        if ident in seen or duplicate:
            counts['duplicates'] += 1
            if duplicate:
                duplicate['duplicate_osm_ids'].append(ident)
                for key,value in tags.items(): duplicate['tags'].setdefault(key,value)
                for key, aliases in {'opening_hours':['opening_hours'],'phone':['contact:phone','phone'],'website':['contact:website','website']}.items():
                    if not duplicate.get(key): duplicate[key]=next((tags[k] for k in aliases if tags.get(k)),None)
            continue
        seen.add(ident)
        rows.append(dict(id=ident, name=name.strip(), name_ru=tags.get('name:ru'), name_kk=tags.get('name:kk'), name_en=tags.get('name:en'), lat=lat, lon=lon, category=cat, tags=tags, description=tags.get('description:ru') or tags.get('description') or '', search_tags=[cat, CATEGORY_TEXT[cat]], opening_hours=tags.get('opening_hours'), phone=tags.get('contact:phone') or tags.get('phone'), website=tags.get('contact:website') or tags.get('website'), rating=None, popularity=None, wheelchair=tags.get('wheelchair','unknown'), socket=tags.get('socket','unknown'), wifi=tags.get('internet_access','unknown'), source=f'https://www.openstreetmap.org/{ident}', collected_at=collected_at, duplicate_osm_ids=[], gold_reviewed=False, _normalized=normalized))
    for r in rows: r.pop('_normalized')
    return rows, counts

def save(rows):
    DATA.mkdir(exist_ok=True)
    (DATA/'pois.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    # Serialize nested sparse tag dictionaries explicitly for a stable parquet schema.
    df = pd.DataFrame([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in p.items()} for p in rows])
    df.to_parquet(DATA/'pois.parquet',index=False)

def quality_report(rows, counts):
    n=len(rows)
    coverage={k:round(100*sum(bool(p.get(k)) and p.get(k)!='unknown' for p in rows)/max(n,1),1) for k in ['category','search_tags','opening_hours','phone','website','wheelchair','description','rating','popularity']}
    report={'collected_at':rows[0]['collected_at'] if rows else None,'count':n,'counts':counts,'coverage_pct':coverage,'categories':pd.Series([r['category'] for r in rows]).value_counts().to_dict(),'gold_reviewed':sum(r.get('gold_reviewed',False) for r in rows)}
    (DATA/'quality.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Качество данных',f'\nСобрано: {report["collected_at"]}. Источник: OpenStreetMap / Overpass, ODbL.',f'\nОбъектов: **{n}**. Проверено по исходным тегам: **{report["gold_reviewed"]}**.', '\nПоле | Покрытие, %','--- | ---']+[f'{k} | {v}' for k,v in coverage.items()]
    lines+=['\nКатегории: '+json.dumps(report['categories'],ensure_ascii=False),'\nОтсев: '+json.dumps(counts,ensure_ascii=False),'\nТеги search_tags — нормализованная таксономия, не LLM-обогащение. Наличие категории не означает полноту описания. Часы из OSM не являются подтверждением работы организации. Рейтинги не выдуманы: отсутствуют, если OSM их не предоставляет.']
    (DATA/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    raw=fetch(BOUNDARY_QUERY,DATA/'raw/boundary.json',args.refresh)
    rel=raw['elements'][0]; boundary=boundary_from_relation(rel)
    (DATA/'boundary.geojson').write_text(json.dumps({'type':'Feature','properties':{'osm_relation_id':rel['id'],'name':rel.get('tags',{}).get('name'),'source':f"https://www.openstreetmap.org/relation/{rel['id']}"},'geometry':mapping(boundary)},ensure_ascii=False),encoding='utf-8')
    query=f'[out:json][timeout:90];rel({rel["id"]});map_to_area->.city;(nwr(area.city)[amenity~"^({AMENITIES})$"];nwr(area.city)[tourism];nwr(area.city)[leisure];nwr(area.city)[shop];);out center tags;'
    rawpois=fetch(query,DATA/'raw/pois.json',args.refresh)
    stamp=datetime.fromtimestamp((DATA/'raw/pois.json').stat().st_mtime,timezone.utc).isoformat()
    extra_query=f'[out:json][timeout:90];rel({rel["id"]});map_to_area->.city;(nwr(area.city)[historic];nwr(area.city)[man_made=tower];nwr(area.city)[building=museum];);out center tags;'
    extras=fetch(extra_query,DATA/'raw/extra.json',args.refresh)
    rows,counts=clean(rawpois['elements']+extras['elements'],boundary,stamp)
    if (DATA/'gold_review.yaml').exists():
        from data.review import apply_reviews
        before=len(rows);rows=apply_reviews(rows);counts['curated_duplicates']=before-len(rows)
    if len(rows)<500: print(f'WARNING: only {len(rows)} named POIs; target is 500',flush=True)
    save(rows)
    print(json.dumps(quality_report(rows,counts),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
