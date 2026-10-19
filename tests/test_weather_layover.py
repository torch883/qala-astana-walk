import json
from datetime import datetime,timedelta
import pytest
from core import weather as wx
from core.engine import Engine
from core.layover import windows,check_plan,layover_minutes,transfer_min,airport
from core.parse import parse_rules
from core.retrieve import load_pois
from core.settings import CONFIG

AT=datetime.fromisoformat('2026-01-15T15:00:00+05:00')

@pytest.fixture(scope='module')
def engine():return Engine(load_pois(),backend='lexical')

def test_classify_levels():
    assert wx.make(AT,-24,-32,7).level=='harsh' and wx.make(AT,-24,-32,7).reasons==['cold']
    assert wx.make(AT,-5,-12,4).level=='caution'
    assert wx.make(AT,18,18,3).level=='ok'
    assert 'wind' in wx.make(AT,5,2,13).reasons and wx.make(AT,5,2,13).level=='harsh'
    assert wx.make(AT,20,20,2,code=95).reasons==['storm']

def test_fetch_sends_only_city_centre(monkeypatch):
    seen={}
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'hourly':{'time':['2026-01-15T15:00'],'temperature_2m':[-24],'apparent_temperature':[-32],'wind_speed_10m':[7],'wind_gusts_10m':[11],'precipitation':[0],'weather_code':[3]}}
    def fake_get(url,params,timeout):seen.update(params);return Response()
    monkeypatch.setattr(wx.requests,'get',fake_get)
    w=wx.fetch(AT)
    assert w.source=='open-meteo' and w.level=='harsh' and w.feels_like_c==-32
    # The user's location never reaches the weather service.
    assert (seen['latitude'],seen['longitude'])==wx.CITY_CENTRE

def test_fetch_failure_means_no_weather(monkeypatch):
    def broken(*a,**k):raise wx.requests.ConnectionError()
    monkeypatch.setattr(wx.requests,'get',broken)
    assert wx.fetch(AT) is None

def test_warm_path_through_synthetic_hub(tmp_path):
    # A 100 m square hub halfway between two points 1.6 km apart.
    lat,lon=51.13,71.43;dlat=50/wx.KY;dlon=50/wx.KX
    ring=[[lon-dlon,lat-dlat],[lon+dlon,lat-dlat],[lon+dlon,lat+dlat],[lon-dlon,lat+dlat],[lon-dlon,lat-dlat]]
    path=tmp_path/'hubs.geojson'
    path.write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Polygon','coordinates':[ring]},'properties':{'id':'way/1','name':'Тест','lat':lat,'lon':lon,'source':'https://www.openstreetmap.org/way/1','opening_hours':'Mo-Su 10:00-22:00'}}]}),encoding='utf-8')
    hubs=wx.Hubs(path);a=(lat-800/wx.KY,lon);b=(lat+800/wx.KY,lon)
    # Each leg is 750 m outside: 750 x 1.3 / 80 = 12.2 -> 13 min.
    assert hubs.outdoor_min(a,b)>20
    assert hubs.warm_path(a,b,AT,12) is None
    w=hubs.warm_path(a,b,AT,14)
    assert w and w.hub_name=='Тест' and w.outdoor_legs_min==[13,13] and w.hub_hours_confirmed
    # Closed at night: no warm detour.
    assert hubs.warm_path(a,b,AT.replace(hour=23),14) is None
    assert hubs.outdoor_min((lat,lon),(lat+10/wx.KY,lon))==0

def test_shelter_labels():
    assert wx.shelter({'category':'park','tags':{'leisure':'park'}})=='outdoor'
    assert wx.shelter({'category':'cafe','tags':{}})=='indoor'
    assert wx.shelter({'category':'attraction','tags':{'building':'yes'}})=='indoor'
    assert wx.shelter({'category':'playground','tags':{'leisure':'playground'}},in_hub=True)=='indoor'

def test_harsh_weather_keeps_only_indoor_and_short_stretches(engine):
    a,_=engine.answer('Хочу прогуляться 60 минут',CONFIG['presets']['Байтерек'],AT,language='ru',use_cache=False,weather=wx.preset('frost',AT))
    cap=CONFIG['weather']['harsh_outdoor_leg_min']
    assert a.recommendations and a.weather.level=='harsh'
    for r in a.recommendations:
        assert r.shelter=='indoor'
        legs=r.warm_route.outdoor_legs_min if r.warm_route else [r.outdoor_min]
        assert max(legs)<=cap
        assert 'ощущается как -32' in r.caveats

def test_harsh_weather_park_request_explains_refusal(engine):
    a,_=engine.answer('Хочу в парк на 60 минут',CONFIG['presets']['Байтерек'],AT,language='ru',use_cache=False,weather=wx.preset('frost',AT))
    assert a.response_type=='refusal' and not a.recommendations and '°C' in a.message

def test_parse_layover():
    i=parse_rules('У меня пересадка 8 часов, что посмотреть?')
    assert i.intent=='layover' and i.layover_min==480 and i.flight_in_min is None and 'tourist' in i.constraints
    assert parse_rules('Транзит, вылет в 22:30.').departure_clock=='22:30'
    assert parse_rules('8-hour layover in Astana').layover_min==480
    assert parse_rules('У меня пересадка').layover_min is None
    # A walk before a flight from the city is still the old refusal path, not a layover.
    assert parse_rules('2 часа перед вылетом').intent=='discover'

def test_layover_windows_are_planned_backwards():
    now=datetime.fromisoformat('2026-10-17T10:00:00+05:00');c=CONFIG['layover']
    plans=windows(480,now)
    assert plans
    for p in plans:
        assert check_plan(p)
        assert datetime.fromisoformat(p.departure)-datetime.fromisoformat(p.back_at_airport_by)==timedelta(minutes=c['return_reserve_min'])
    assert windows(240,now)==[]
    assert transfer_min(airport(),airport())==c['transfer_overhead_min']

def test_departure_clock_wins_and_wraps_midnight():
    now=datetime.fromisoformat('2026-10-17T23:00:00+05:00')
    assert layover_minutes(parse_rules('Пересадка 3 часа, вылет в 07:30'),now)==510

def test_check_plan_rejects_a_broken_reserve():
    p=windows(480,datetime.fromisoformat('2026-10-17T10:00:00+05:00'))[0]
    bad=p.model_copy(update={'back_at_airport_by':p.departure})
    with pytest.raises(ValueError,match='layover_reserve'):check_plan(bad)

def test_layover_answer_fits_the_window(engine):
    now=datetime.fromisoformat('2026-10-17T10:00:00+05:00')
    a,_=engine.answer('У меня пересадка 8 часов, что посмотреть?',CONFIG['presets']['Аэропорт'],now,use_cache=False)
    assert a.layover and a.recommendations and check_plan(a.layover,a.route)
    assert datetime.fromisoformat(a.layover.leave_city_by).strftime('%H:%M') in a.message
    for r in a.recommendations:assert 2*r.travel_min+r.visit_min<=a.layover.city_min
    short,_=engine.answer('Пересадка 4 часа',CONFIG['presets']['Аэропорт'],now,use_cache=False)
    assert short.response_type=='refusal' and '120' in short.message
    ask,_=engine.answer('У меня пересадка, куда сходить?',CONFIG['presets']['Аэропорт'],now,use_cache=False)
    assert ask.response_type=='clarification' and ask.clarifying_question.count('?')==1
