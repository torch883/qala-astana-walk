import json
from core.settings import DATA
from core.engine import Engine
from core.retrieve import fingerprint
from core.cache import signature,data_fingerprint
from core.geo import round_location
from core.settings import CONFIG
from datetime import datetime
from eval.run_eval import scenarios,run_case

def main():
    engine=Engine();responses={}
    for case in scenarios()[:5]:
        a,_=run_case(case,engine)
        key=signature(case['query'],round_location(*CONFIG['presets'][case['preset']]),datetime.fromisoformat(case['now']),a.interpretation)
        responses[key]=a.model_dump()
    (DATA/'demo_cache.json').write_text(json.dumps({'fingerprint':data_fingerprint(engine.pois),'responses':responses,'notice':'Only five public demo scenarios. Not user history.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved',len(responses),'public demo responses')

if __name__=='__main__':main()
