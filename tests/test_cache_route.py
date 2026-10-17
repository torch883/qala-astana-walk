from datetime import datetime
import json
from core.engine import Engine
from core.settings import CONFIG,DATA
from core.cache import signature,load_demo
from core.geo import round_location
from core.parse import parse_rules
from core.retrieve import load_pois,fingerprint
from core.validate import validate_answer
from eval.run_eval import scenarios,run_case

def test_no_user_history_written(tmp_path,monkeypatch):
    import core.cache as cache
    monkeypatch.setattr(cache,'DATA',tmp_path)
    monkeypatch.setenv('DEMO_CACHE','1')
    p=load_pois();i=parse_rules('Мой частный запрос о прогулке')
    assert load_demo('Мой частный запрос о прогулке',(51.1,71.4),datetime(2026,10,17),i,p) is None
    assert list(tmp_path.iterdir())==[]

def test_cache_stale_or_changed_constraints_are_rejected(tmp_path,monkeypatch):
    import core.cache as cache
    monkeypatch.setattr(cache,'DATA',tmp_path);monkeypatch.setenv('DEMO_CACHE','1')
    pois=load_pois();intent=parse_rules('Кофе');now=datetime.fromisoformat('2026-10-17T14:00:00+05:00')
    key=signature('Кофе',(51.128,71.430),now,intent)
    (tmp_path/'demo_cache.json').write_text(json.dumps({'fingerprint':'stale','responses':{key:{}}}),encoding='utf-8')
    assert cache.load_demo('Кофе',(51.128,71.430),now,intent,pois) is None
    assert key!=signature('Кофе',(51.128,71.430),now,intent.model_copy(update={'group_size':4}))

def test_route_fits_all_legs_and_return():
    engine=Engine(backend='lexical');case=next(c for c in scenarios() if c['id']=='route_three')
    answer,_=run_case(case,engine)
    assert answer.route and len(answer.route.stops)==3
    r=answer.route
    assert r.total_min==sum(s.travel_min+s.visit_min for s in r.stops)+r.return_min
    assert r.total_min<=answer.interpretation.duration_min

def test_demo_cache_avoids_llm_even_if_api_is_down(monkeypatch):
    import core.llm as llm
    monkeypatch.setenv('DEMO_CACHE','1')
    monkeypatch.setenv('LLM_PROVIDER','gemini')
    monkeypatch.setenv('GEMINI_API_KEY','test-key-not-a-real-credential')
    def forbidden(*args,**kwargs):raise AssertionError('A fixed demo must not call the API')
    monkeypatch.setattr(llm,'structured',forbidden)
    engine=Engine(backend='lexical')
    for c in scenarios()[:5]:
        a,d=engine.answer(c['query'],CONFIG['presets'][c['preset']],datetime.fromisoformat(c['now']),language=c['language'],mode='walk',max_travel_min=20)
        assert a.response_type==c['expected']
        assert d.get('cache_hit') or c['id']=='airport_flight'
