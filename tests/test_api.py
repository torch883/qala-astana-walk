from datetime import datetime, timedelta
import json
import pytest
from fastapi.testclient import TestClient
from api import app, PUBLIC_SCENARIOS
from core.schemas import Answer
from core.settings import CONFIG
from core.geo import round_location
from core.layover import check_plan
from core.rank import filter_candidates
from core.parse import parse_rules
from ui_service import RecommendRequest, resolve_intent

AT='2026-10-18T15:00:00+05:00'

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as client:yield client

def test_default_api_preserves_answer_schema(client):
    response=client.post('/api/recommend',json={'query':'Прогулка','preset':'Байтерек','now':AT})
    assert response.status_code==200
    answer=Answer.model_validate(response.json())
    assert answer.recommendations and answer.route
    assert answer.route.total_min<=answer.interpretation.duration_min
    assert response.headers['cache-control']=='no-store'
    assert 'presentation' not in response.json()

@pytest.mark.parametrize('scenario',PUBLIC_SCENARIOS,ids=lambda s:s['id'])
def test_five_ui_scenarios_are_real_and_feasible(client,scenario):
    req={k:scenario[k] for k in ['query','preset','now','language']}
    req.update(scenario_id=scenario['id'],demo_cache=True)
    response=client.post('/api/recommend?details=true',json=req)
    assert response.status_code==200
    data=response.json();answer=Answer.model_validate(data['answer'])
    assert answer.response_type==scenario['expected']
    if answer.recommendations:
        assert all(r.poi_id in app.state.engine.by_id for r in answer.recommendations)
        assert answer.route and answer.route.total_min<=answer.interpretation.duration_min
        assert set(s.poi_id for s in answer.route.stops)==set(r.poi_id for r in answer.recommendations)
        assert data['presentation']['total_min']==answer.route.total_min
    else:assert not answer.route

def test_deadline_is_a_hard_roundtrip_limit(client):
    response=client.post('/api/recommend?details=true',json={'query':'Погулять','preset':'Байтерек','now':AT,'duration_min':120,'deadline':'2026-10-18T15:20:00+05:00'})
    answer=Answer.model_validate(response.json()['answer'])
    assert answer.interpretation.duration_min<=20
    assert not answer.route or answer.route.total_min<=20
    assert not answer.alternative
    now=datetime.fromisoformat(AT);intent=parse_rules('Погулять 120 минут')
    accepted,_=filter_candidates(app.state.engine.pois,round_location(*CONFIG['presets']['Байтерек']),now,intent,deadline=now+timedelta(minutes=20))
    assert all(2*c.travel_min+c.visit_min<=20 for c in accepted)

def test_layover_transfer_and_return_deadline(client):
    data=client.post('/api/recommend?details=true',json={'query':'Что посмотреть?','preset':'Аэропорт','now':'2026-10-18T10:00:00+05:00',
        'departure_at':'2026-10-18T18:00:00+05:00','airport_transfer_min':60,'deadline':'2026-10-18T14:30:00+05:00'}).json()
    answer=Answer.model_validate(data['answer']);plan=answer.layover
    assert plan and check_plan(plan,answer.route)
    assert plan.transfer_min>=60 and plan.reserve_min>=120
    assert datetime.fromisoformat(plan.leave_city_by)<=datetime.fromisoformat('2026-10-18T14:30:00+05:00')
    assert data['presentation']['deadline']==plan.leave_city_by

def test_short_layover_honestly_refuses(client):
    data=client.post('/api/recommend',json={'query':'Что посмотреть?','preset':'Аэропорт','now':AT,'departure_at':'2026-10-18T17:00:00+05:00'}).json()
    answer=Answer.model_validate(data)
    assert answer.response_type=='refusal' and not answer.recommendations and not answer.alternative

def test_followup_preserves_child_constraint_and_excludes_coffee():
    req=RecommendRequest(query='А можно потише и без кофе?',history=['Хочу кофе с ребёнком'],duration_min=90)
    intent,_=resolve_intent(req,req.query)
    assert 'cafe' not in intent.categories
    assert {'children','quiet'}<=set(intent.constraints)
    assert intent.duration_min==90

def test_feedback_is_anonymous_and_rejects_unknown_places(client):
    poi=app.state.engine.pois[0]['id']
    assert client.post('/api/feedback',json={'poi_id':'invented'}).status_code==404
    data=client.post('/api/feedback',json={'poi_id':poi,'reason':'hours'}).json()
    assert data['accepted'] and data['persisted'] is False
    assert client.post('/api/feedback',json={'poi_id':poi,'location':[51,71]}).status_code==422

def test_invalid_input_is_not_echoed(client):
    text='DO_NOT_ECHO_PRIVATE_TEXT'
    response=client.post('/api/recommend',json={'query':text,'location':[999,71]})
    assert response.status_code==422 and text not in response.text
    response=client.post('/api/recommend',json={'query':text,'group_size':99})
    assert response.status_code==422 and text not in response.text

def test_cache_toggle_does_not_mutate_environment(client,monkeypatch):
    import os
    from core import llm
    monkeypatch.setenv('DEMO_CACHE','0')
    monkeypatch.setenv('LLM_PROVIDER','gemini');monkeypatch.setenv('GEMINI_API_KEY','test-key-not-a-real-credential')
    def forbidden(*a,**k):raise AssertionError('Public cache scenario must not call Gemini')
    monkeypatch.setattr(llm,'structured',forbidden)
    scenario=PUBLIC_SCENARIOS[0]
    req={k:scenario[k] for k in ['query','preset','now','language']}
    req.update(scenario_id=scenario['id'],demo_cache=True)
    response=client.post('/api/recommend?details=true',json=req)
    assert response.status_code==200 and response.json()['debug']['cache_hit']
    assert os.environ['DEMO_CACHE']=='0'

def test_static_shell_and_local_leaflet(client):
    assert client.get('/').status_code==200
    assert client.get('/vendor/leaflet.js').status_code==200
    assert client.get('/api/presets').json()['quality']['count']>500
