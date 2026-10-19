// A saved bookmark contains public POI facts only, never a past recommendation.
export const SAVED_KEY='qala:saved:v1';
const text=(value,limit)=>typeof value==='string'?value.slice(0,limit):'';

export function cleanSaved(items){
  if(!Array.isArray(items))return [];
  const cleaned=[],seen=new Set();
  for(const item of items.slice(0,30)){
    if(!item||!Array.isArray(item.recommendations))continue;
    const recommendations=item.recommendations.slice(0,3).flatMap(r=>{
      if(!r||!/^((node|way|relation)\/\d+)$/.test(r.poi_id)||!text(r.name,200).trim())return [];
      return [{poi_id:r.poi_id,name:text(r.name,200),category:text(r.category,40),
        source_url:'https://www.openstreetmap.org/'+r.poi_id,
        collected_at:text(r.collected_at,40)}];
    });
    if(!recommendations.length)continue;
    const kind=item.kind==='place'?'place':'route';
    const recs=kind==='place'?recommendations.slice(0,1):recommendations;
    const id=kind==='place'?recs[0].poi_id:'route:'+recs.map(r=>r.poi_id).join('|');
    if(seen.has(id))continue;
    seen.add(id);
    cleaned.push({id,kind,title:recs.map(r=>r.name).join(' → '),recommendations:recs});
  }
  return cleaned;
}

export function readSaved(storage){
  try{
    const raw=storage.getItem(SAVED_KEY),items=cleanSaved(JSON.parse(raw||'[]'));
    // Migrate old bookmarks: discard origin-dependent fields and outdated opening status.
    if(raw&&raw!==JSON.stringify(items)){
      try{storage.setItem(SAVED_KEY,JSON.stringify(items));}catch{/* Reading still works if storage is full. */}
    }
    return items;
  }catch{return [];}
}
