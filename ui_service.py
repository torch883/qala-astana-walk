"""Presentation adapter. Requests/history live only for the duration of an HTTP request."""
from datetime import datetime, timedelta
from itertools import combinations
import math, re, os
from typing import Annotated, Literal
from pydantic import Field
from core.schemas import Strict, Answer, Route, RouteStop
from core.settings import CONFIG
from core.hours import local_time
from core.geo import round_location, haversine
from core.parse import parse, parse_rules, requested_duration
from core.route import build_route, leg_min
from core import weather as wx, llm
from core.security import safe_text


class RecommendRequest(Strict):
    query: str = Field(default='', max_length=1500)
    location: tuple[float, float] | None = None
    preset: str | None = None
    now: datetime | None = None
    duration_min: int = Field(default=60, ge=5, le=480)
    language: Literal['ru', 'en', 'kk'] = 'ru'
    mode: Literal['walk', 'transport'] = 'walk'
    group_size: int = Field(default=1, ge=1, le=20)
    accessible: bool = False
    max_travel_min: int = Field(default=20, ge=1, le=90)
    history: list[Annotated[str, Field(max_length=1500)]] = Field(default_factory=list, max_length=6)
    demo_cache: bool = Field(default_factory=lambda:os.getenv('DEMO_CACHE','0')=='1')
    scenario_id: str | None = None
    weather: Literal['off', 'live', 'mild', 'frost', 'blizzard', 'rain', 'heat'] = 'off'
    deadline: datetime | None = None  # Must be back at the starting point by this instant.
    departure_at: datetime | None = None
    airport_transfer_min: Literal[30, 45, 60] = 45


class UIResponse(Strict):
    answer: Answer
    presentation: dict
    debug: dict


COPY = {
 'ru': {'walk':'Немного города, без спешки', 'quiet':'Тише, ближе, в своём темпе', 'coffee':'Время на кофе и паузу', 'child':'Маленькое городское приключение', 'night':'Город после заката', 'layover':'Астана между рейсами', 'indoor':'Тепло, даже когда город замёрз', 'refusal':'Оставим время на главное', 'clarification':'Один вопрос — и в путь', 'late':'До указанного срока уже не хватает времени на прогулку с возвращением.', 'weather_fail':'Прогноз недоступен. Погода не учтена.', 'default':'Прогулка по городу', 'excluded':'Исключены по уточнению: '},
 'en': {'walk':'A little city, at your pace', 'quiet':'A quieter way to spend an hour', 'coffee':'A moment for coffee', 'child':'A small city adventure', 'night':'The city after sunset', 'layover':'Astana between flights', 'indoor':'A warmer way around the city', 'refusal':'Keep time for what matters', 'clarification':'One question before we go', 'late':'There is not enough time left to go out and return by this deadline.', 'weather_fail':'Forecast unavailable. Weather was not considered.', 'default':'A city walk', 'excluded':'Excluded by your follow-up: '},
 'kk': {'walk':'Қаланы асықпай аралайық', 'quiet':'Тыныштықта, өз ырғағыңызбен', 'coffee':'Кофеге арналған үзіліс', 'child':'Қаладағы шағын шытырман', 'night':'Күн батқаннан кейінгі қала', 'layover':'Рейстер арасындағы Астана', 'indoor':'Суық күндегі жылы бағыт', 'refusal':'Маңызды іске уақыт қалдырайық', 'clarification':'Жолға шығар алдында бір сұрақ', 'late':'Белгіленген уақытқа дейін серуендеп, қайтуға уақыт жеткіліксіз.', 'weather_fail':'Ауа райы болжамы қолжетімсіз. Ол есепке алынбады.', 'default':'Қалада серуендеу', 'excluded':'Сұрауыңыз бойынша алынып тасталды: '}}

EXCLUSIONS = [
 (r'(?:без|не надо|не хочу|without|no)\s+(?:коф\w*|кафе|coffee|cafes?)|кофесіз', {'cafe'}),
 (r'(?:без|without|no)\s+(?:музе\w*|museums?)|мұражайсыз', {'museum'}),
 (r'(?:без|without|no)\s+(?:бар\w*|алкогол\w*|bars?|alcohol)|алкогольсіз', {'bar','nightclub'}),
 (r'(?:без|without|no)\s+(?:парк\w*|parks?)', {'park'})]


def resolve_intent(req, query):
    history=[safe_text(t,500) for t in req.history]
    text='\n'.join(history+[query])[-4000:]
    parser=parse_rules if req.demo_cache else parse
    intent=parser(text,language=req.language,mode=req.mode,group_size=req.group_size,
                  accessible=req.accessible,max_travel_min=req.max_travel_min)
    current=parse_rules(query,language=req.language)
    # An explicit new category replaces old categories; constraints such as children persist.
    explicit=not any('прогулки выбраны' in a or 'preferred for a walk' in a or 'Серуенге' in a for a in current.assumptions)
    if history and explicit:intent.categories=current.categories
    excluded=set()
    for pattern,categories in EXCLUSIONS:
        if re.search(pattern,text,re.I):excluded.update(categories)
    intent.categories=[c for c in intent.categories if c not in excluded]
    if not intent.categories:intent.categories=['park','attraction','viewpoint','gallery','museum']
    intent.categories=[c for c in intent.categories if c not in excluded]
    # «потише» is a conversational comparative missed by the original keyword parser.
    if re.search(r'потише|quieter|тынышырақ',text,re.I):
        intent.constraints=list(dict.fromkeys(intent.constraints+['quiet']))
        intent.tags=list(dict.fromkeys(intent.tags+['quiet']))
    if excluded:intent.assumptions.append(COPY[req.language]['excluded']+', '.join(sorted(excluded)))
    explicit_minutes=requested_duration(query) is not None
    intent.duration_min=min(req.duration_min,current.duration_min) if explicit_minutes and current.intent!='layover' else req.duration_min
    # A selected UI budget supersedes the parser's 60-minute default assumption.
    default_budget={'ru':'Бюджет времени:','en':'Time budget:','kk':'Уақыт қоры:'}[req.language]
    intent.assumptions=[a for a in intent.assumptions if not a.startswith(default_budget)]
    intent.route_requested=True
    return intent,text


def fit_route(answer,engine,origin,now):
    """Choose a feasible subset, never join three independent options into a fictitious route."""
    if not answer.recommendations or origin is None:return
    if answer.layover:
        origin=(answer.layover.anchor_lat,answer.layover.anchor_lon)
        now=datetime.fromisoformat(answer.layover.arrive_city)
    if answer.route:return
    recs=answer.recommendations
    for count in range(min(3,len(recs)),1,-1):
        for subset in combinations(recs,count):
            route=build_route(subset,engine.by_id,origin,now,answer.interpretation,answer.weather,engine.env)
            if route:
                answer.recommendations=list(subset);answer.route=route;return
    for r in recs:
        back=leg_min((r.lat,r.lon),origin,now+timedelta(minutes=r.travel_min+r.visit_min),answer.interpretation,answer.weather,engine.env)
        if back is None or r.travel_min+r.visit_min+back>answer.interpretation.duration_min:continue
        answer.recommendations=[r]
        answer.route=Route(stops=[RouteStop(poi_id=r.poi_id,travel_min=r.travel_min,visit_min=r.visit_min,
                             arrival_min=r.travel_min,departure_min=r.travel_min+r.visit_min)],
                           total_min=r.travel_min+r.visit_min+back,return_min=back,
                           basis='straight_line_x1.3_estimate_including_return')
        return
    answer.recommendations=[];answer.route=None;answer.response_type='refusal'
    answer.message=COPY[answer.interpretation.language]['late']


class RouteTitle(Strict):
    title: str = Field(min_length=4,max_length=65)


def presentation(answer,origin,now,req):
    lang=req.language;words=COPY[lang];i=answer.interpretation
    if answer.response_type!='recommendations':key=answer.response_type
    elif answer.layover:key='layover'
    elif answer.weather and answer.weather.level=='harsh':key='indoor'
    elif 'children' in i.constraints:key='child'
    elif 'night' in i.constraints or now.hour>=22 or now.hour<6:key='night'
    elif 'quiet' in i.constraints:key='quiet'
    elif i.categories==['cafe']:key='coffee'
    else:key='walk'
    title=words[key];title_source='template'
    if answer.generation_backend=='gemini' and llm.enabled() and not req.demo_cache:
        try:
            generated=llm.structured('Write a short, warm route headline in the requested language. No numbers, factual claims, place names, instructions or invented amenities. Category and mood only.',
                                     {'language':lang,'categories':i.categories,'moods':i.tags},RouteTitle)
            if not re.search(r'\d|https?://',generated.title):title=safe_text(generated.title,65);title_source='generated_idea'
        except (llm.LLMUnavailable,ValueError):pass
    if answer.layover:origin=(answer.layover.anchor_lat,answer.layover.anchor_lon)
    by_id={r.poi_id:r for r in answer.recommendations}
    ordered=[by_id[s.poi_id] for s in answer.route.stops] if answer.route else answer.recommendations
    path=[origin]+[(r.lat,r.lon) for r in ordered]+[origin] if origin and ordered else []
    distance=round(sum(haversine(*a,*b) for a,b in zip(path,path[1:]))*CONFIG['detour_factor'])
    deadline=answer.layover.leave_city_by if answer.layover else (req.deadline.isoformat() if req.deadline else None)
    return {'title':title,'title_source':title_source,'origin':origin,'distance_m':distance,
            'total_min':answer.route.total_min if answer.route else 0,'stops_count':len(ordered),
            'deadline':deadline,'now':now.isoformat(),'radius_m':round(i.max_travel_min*80/1.3),
            'distance_basis':'straight_line_x1.3','return_min':answer.route.return_min if answer.route else 0}


def recommend(req,engine,scenarios):
    now=local_time(req.now or datetime.now().astimezone());query=req.query or COPY[req.language]['default']
    origin=req.location if req.location is not None else CONFIG['presets'].get(req.preset)
    if origin is not None:origin=round_location(*origin)
    wx_value=wx.fetch(now) if req.weather=='live' else wx.preset(req.weather,now) if req.weather in wx.PRESETS else None
    intent,text=resolve_intent(req,query)
    scenario=next((c for c in scenarios if c['id']==req.scenario_id),None)
    exact_demo=bool(scenario and not req.history and query==scenario['query'] and origin==round_location(*CONFIG['presets'][scenario['preset']])
                    and now==datetime.fromisoformat(scenario['now']) and req.duration_min==60 and req.group_size==1 and not req.accessible
                    and req.language==scenario['language'] and req.mode=='walk' and req.max_travel_min==20 and req.deadline is None and req.departure_at is None)
    if req.departure_at:
        minutes=math.floor((local_time(req.departure_at)-now).total_seconds()/60)
        if minutes<1 or minutes>1440:
            answer=Answer(interpretation=intent,response_type='refusal',message=COPY[req.language]['late'])
            return UIResponse(answer=answer,presentation=presentation(answer,origin,now,req),debug={'reason':'departure_deadline'})
        intent.intent='layover';intent.layover_min=minutes;intent.departure_clock=None;intent.flight_in_min=None
        intent.constraints=list(dict.fromkeys(intent.constraints+['tourist']))
    answer,debug=engine.answer(query if exact_demo else text,origin,now,language=req.language,mode=req.mode,group_size=req.group_size,
        accessible=req.accessible,max_travel_min=req.max_travel_min,weather=wx_value,parsed_intent=None if exact_demo else intent,
        deadline=req.deadline,cache_enabled=req.demo_cache,transfer_floor=req.airport_transfer_min if req.departure_at else 0)
    fit_route(answer,engine,origin,now)
    if req.deadline is not None or req.departure_at is not None:answer.alternative=None
    if req.weather=='live' and wx_value is None:debug['weather_warning']=COPY[req.language]['weather_fail']
    debug['history_turns']=len(req.history)
    debug['data_used']=['rounded_location','time','preferences']+(['weather'] if wx_value else [])
    return UIResponse(answer=answer,presentation=presentation(answer,origin,now,req),debug=debug)
