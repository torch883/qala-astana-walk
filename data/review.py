"""Apply explicit reviewed edits; retain raw OSM data and audit trail."""
import csv,json,yaml
from core.settings import DATA
from data.collect import save,quality_report

def apply_reviews(rows):
    cfg=yaml.safe_load((DATA/'gold_review.yaml').read_text(encoding='utf-8'))
    by_id={p['id']:p for p in rows}
    for old,new in cfg['remove_duplicates'].items():
        if old in by_id and new in by_id:
            by_id[new]['duplicate_osm_ids'].append(old)
            for key,value in by_id[old]['tags'].items():by_id[new]['tags'].setdefault(key,value)
            for field in ['name_ru','name_kk','name_en','phone','website','wheelchair']:
                if by_id[new].get(field) in {None,'unknown'} and by_id[old].get(field) not in {None,'unknown'}:by_id[new][field]=by_id[old][field]
            del by_id[old]
    audit=[]
    for ident,(zone,note) in cfg['reviews'].items():
        if ident not in by_id:continue
        p=by_id[ident]
        p.update(gold_reviewed=True,review_zone=zone,review_description=note,review_method='assistant_osm_source_review',review_date='2026-10-17')
        edits=cfg.get('overrides',{}).get(ident,{})
        before={k:p.get(k) for k in edits}
        p.update(edits)
        audit.append({'id':ident,'name':p['name'],'zone':zone,'category':p['category'],'source':p['source'],'note':note,'edits':json.dumps({'before':before,'after':edits},ensure_ascii=False)})
    with (DATA/'gold_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(audit[0]) if audit else ['id']);w.writeheader();w.writerows(audit)
    return list(by_id.values())

def main():
    rows=apply_reviews(json.loads((DATA/'pois.json').read_text(encoding='utf-8')))
    save(rows)
    old=json.loads((DATA/'quality.json').read_text(encoding='utf-8'));quality_report(rows,old['counts'])
    print('Source-reviewed POIs:',sum(p.get('gold_reviewed',False) for p in rows))

if __name__=='__main__':main()
