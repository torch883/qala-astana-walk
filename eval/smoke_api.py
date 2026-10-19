"""Exercise a running demo with public scenarios; never stores user requests."""
import argparse
import json
from datetime import datetime, timezone
from time import perf_counter

import requests
from core.schemas import Answer
from core.layover import check_plan
from core.settings import ROOT
from eval.run_eval import scenarios, check
from core.retrieve import load_pois


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    args=parser.parse_args();url=args.url.rstrip('/')
    health=requests.get(url+'/api/health',timeout=10)
    health.raise_for_status();assert health.json()['ready']
    pois=load_pois();ids={p['id'] for p in pois};results=[]

    def run(name,body,expected,case=None):
        started=perf_counter()
        response=requests.post(url+'/api/recommend?details=true',json=body,timeout=20)
        elapsed=round((perf_counter()-started)*1000,1)
        response.raise_for_status();assert response.headers['Cache-Control']=='no-store'
        data=response.json();answer=Answer.model_validate(data['answer'])
        assert answer.response_type==expected,(name,answer.response_type)
        assert all(r.poi_id in ids for r in answer.recommendations)
        assert len(answer.recommendations)<=3
        if answer.recommendations:
            assert answer.route and answer.route.total_min<=answer.interpretation.duration_min
            assert {s.poi_id for s in answer.route.stops}=={r.poi_id for r in answer.recommendations}
            assert all(r.source=='poi_data' and r.idea_source=='generated_idea' for r in answer.recommendations)
        if answer.layover:assert check_plan(answer.layover,answer.route)
        if case:assert not check(case,answer,pois),check(case,answer,pois)
        assert elapsed<5000,(name,'response_over_5s',elapsed)
        results.append({'id':name,'passed':True,'ms':elapsed,'response_type':answer.response_type,
            'places':[r.name for r in answer.recommendations],'route_min':answer.route.total_min if answer.route else None})
        print(f'{name:25} PASS {elapsed:7.1f} ms',flush=True)
        return data

    for case in scenarios()[:5]:
        body={k:case[k] for k in ['query','preset','now','language']}
        body['demo_cache']=False
        run(case['id'],body,case['expected'],case)
    base={'preset':'Байтерек','now':'2026-10-19T15:00:00+05:00','demo_cache':False}
    half=run('half_hour',{**base,'query':'Есть полчаса на прогулку'},'recommendations')
    assert half['answer']['interpretation']['duration_min']==30
    frost=run('weather_frost',{**base,'query':'Хочу прогуляться','weather':'frost'},'recommendations')
    assert frost['answer']['weather']['level']=='harsh'
    assert all(r['shelter']=='indoor' for r in frost['answer']['recommendations'])
    layover={'query':'Что посмотреть в городе?','preset':'Аэропорт','now':'2026-10-19T10:00:00+05:00',
             'departure_at':'2026-10-19T18:00:00+05:00','airport_transfer_min':45,'demo_cache':False}
    run('layover_8_hours',layover,'recommendations')
    run('layover_2_hours',{**layover,'departure_at':'2026-10-19T12:00:00+05:00'},'refusal')
    run('missing_location',{'query':'Хочу погулять','demo_cache':False},'clarification')
    run('outside_city',{**base,'location':[43.238,76.945],'query':'Прогулка'},'refusal')
    run('required_socket',{**base,'query':'Кофе только с розеткой'},'refusal')
    report={'run_at':datetime.now(timezone.utc).isoformat(),'health':health.json(),
            'passed':len(results),'cases':results,'note':'Local HTTP, warmed engine, public fixed scenarios; not a load test.'}
    (ROOT/'eval/api_smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(results)}/{len(results)} passed')


if __name__=='__main__':main()
