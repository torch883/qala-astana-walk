import pytest
from shapely.geometry import box
from data.collect import clean,category

def test_clean_dedup_and_boundary():
    raw=[{'type':'node','id':1,'lat':51.1,'lon':71.4,'tags':{'name':'Cafe','amenity':'cafe'}},
         {'type':'way','id':2,'center':{'lat':51.1001,'lon':71.4001},'tags':{'name':'Cafe','amenity':'cafe','opening_hours':'24/7'}},
         {'type':'node','id':3,'lat':43,'lon':76,'tags':{'name':'Other','amenity':'cafe'}},
         {'type':'node','id':4,'lat':51.1,'lon':71.4,'tags':{'amenity':'cafe'}}]
    rows,stats=clean(raw,box(71,51,72,52),'2026-10-17')
    assert len(rows)==1 and rows[0]['opening_hours']=='24/7'
    assert stats['unnamed']==1 and stats['outside']==1 and stats['duplicates']==1
    assert rows[0]['duplicate_osm_ids']==['way/2']

def test_unnamed_parks_and_playgrounds_get_honest_labels():
    raw=[{'type':'way','id':5,'center':{'lat':51.1,'lon':71.4},'tags':{'leisure':'playground'}},
         {'type':'way','id':6,'center':{'lat':51.1001,'lon':71.4001},'tags':{'leisure':'playground'}},
         {'type':'way','id':7,'center':{'lat':51.2,'lon':71.5},'tags':{'leisure':'park','addr:street':'улица Мереке'}},
         {'type':'node','id':8,'lat':51.1,'lon':71.4,'tags':{'leisure':'pitch'}}]
    rows,stats=clean(raw,box(71,51,72,52),'2026-10-17')
    # Two neighbouring unnamed playgrounds are distinct places, not name duplicates.
    assert [r['id'] for r in rows]==['way/5','way/6','way/7']
    assert rows[0]['name']=='Детская площадка (без названия в OSM)' and rows[0]['name_en']=='Playground (unnamed in OSM)'
    assert rows[0]['name_generated'] and rows[0]['category']=='playground'
    assert rows[2]['name_ru']=='Парк (без названия в OSM) · улица Мереке'
    assert stats['unnamed']==1 and stats['unnamed_labeled']==3 and stats['duplicates']==0

def test_taxonomy_does_not_call_all_arts_centres_museums():
    assert category({'amenity':'arts_centre'})=='culture'
    assert category({'tourism':'museum'})=='museum'
    assert category({'historic':'monument'})=='attraction'

@pytest.mark.parametrize('tags,expected',[
    ({'tourism':'aquarium','leisure':'water_park'},'entertainment'),({'tourism':'theme_park'},'entertainment'),
    ({'leisure':'bowling_alley'},'entertainment'),({'tourism':'artwork'},'attraction'),({'tourism':'picnic_site'},'park'),
    ({'leisure':'sports_centre'},'sport'),({'leisure':'sauna'},'sport'),({'tourism':'hotel'},'tourism')])
def test_tourism_and_leisure_reach_searchable_categories(tags,expected):assert category(tags)==expected
