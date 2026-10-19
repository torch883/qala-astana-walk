import test from 'node:test';
import assert from 'node:assert/strict';
import {cleanSaved,readSaved,SAVED_KEY} from '../web/saved.mjs';

const recommendation={poi_id:'node/123',name:'Парк',category:'park',collected_at:'2026-10-17',
  source_url:'https://www.openstreetmap.org/node/123',distance_m:400,walk_min:6,
  why:'Тихо с ребёнком',data_used:['location'],open_status:{state:'open'},lat:51.1,lon:71.2};

test('bookmarks retain only public facts; no request, stale hours or generated title',()=>{
  const [item]=cleanSaved([{kind:'route',title:'Маршрут с ребёнком',location:[51,71],query:'secret',recommendations:[recommendation]}]);
  assert.equal(item.title,'Парк');
  assert.deepEqual(Object.keys(item.recommendations[0]).sort(),['category','collected_at','name','poi_id','source_url']);
  for(const privateField of ['location','query','why','distance_m','walk_min','open_status','data_used']){
    assert.ok(!JSON.stringify(item).includes(privateField));
  }
});

test('legacy records migrate without removing valid bookmarked places',()=>{
  let raw=JSON.stringify([{kind:'place',recommendations:[recommendation]},null,{}, {recommendations:[null]}]);
  const storage={getItem:key=>{assert.equal(key,SAVED_KEY);return raw;},setItem:(_,v)=>raw=v};
  const items=readSaved(storage);
  assert.equal(items.length,1);assert.equal(items[0].id,'node/123');
  assert.deepEqual(JSON.parse(raw),items);
  assert.deepEqual(readSaved(storage),items);
});

test('corrupt or unavailable storage cannot break page startup',()=>{
  for(const raw of ['oops','null','{}','[null,{}, {"recommendations":[null]}]']){
    assert.deepEqual(readSaved({getItem:()=>raw}),[]);
  }
  assert.deepEqual(readSaved({getItem:()=>{throw Error('disabled');}}),[]);
});

test('untrusted links, malformed IDs and duplicate records are removed',()=>{
  const item={kind:'place',recommendations:[{...recommendation,source_url:'javascript:alert(1)'}]};
  const result=cleanSaved([item,item,{kind:'place',recommendations:[{...recommendation,poi_id:'fake'}]}]);
  assert.equal(result.length,1);
  assert.equal(result[0].recommendations[0].source_url,'https://www.openstreetmap.org/node/123');
});

test('full storage still permits reading sanitized existing bookmarks',()=>{
  const raw=JSON.stringify([{kind:'place',recommendations:[recommendation]}]);
  const items=readSaved({getItem:()=>raw,setItem:()=>{throw Error('full');}});
  assert.equal(items.length,1);
  assert.ok(!('open_status' in items[0].recommendations[0]));
});
