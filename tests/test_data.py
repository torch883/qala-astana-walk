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

def test_taxonomy_does_not_call_all_arts_centres_museums():
    assert category({'amenity':'arts_centre'})=='leisure'
    assert category({'tourism':'museum'})=='museum'
    assert category({'historic':'monument'})=='attraction'
