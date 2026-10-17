from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Language = Literal['ru','en','kk']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

class Interpretation(Strict):
    intent: str = 'discover'
    duration_min: int = Field(default=60,ge=5,le=480)
    mode: Literal['walk','transport'] = 'walk'
    max_travel_min: int = Field(default=20,ge=1,le=90)
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    language: Language = 'ru'
    group_size: int = Field(default=1,ge=1,le=20)
    flight_in_min: int | None = Field(default=None,ge=1,le=1440)
    # «Астана за пересадку»: layover length, or the departure clock time when only that is given.
    layover_min: int | None = Field(default=None,ge=1,le=1440)
    departure_clock: str | None = Field(default=None,pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    route_requested: bool = False
    parser: Literal['rules','gemini'] = 'rules'

class Weather(Strict):
    at: str
    temperature_c: float
    feels_like_c: float
    wind_ms: float
    gust_ms: float = 0
    precip_mm: float = 0
    code: int = 0
    level: Literal['ok','caution','harsh']
    reasons: list[Literal['cold','heat','wind','precip','storm']] = Field(default_factory=list)
    source: Literal['open-meteo','manual']

class WarmRoute(Strict):
    hub_id: str
    hub_name: str
    hub_lat: float
    hub_lon: float
    hub_source_url: str
    outdoor_legs_min: list[int] = Field(min_length=2,max_length=2)
    outdoor_total_min: int = Field(ge=0)
    travel_min: int = Field(ge=0)
    hub_hours_confirmed: bool
    basis: str = 'straight_line_x1.3_via_osm_building_outline'

class LayoverPlan(Strict):
    anchor: str
    anchor_lat: float
    anchor_lon: float
    layover_min: int
    exit_min: int
    transfer_min: int
    reserve_min: int
    city_min: int
    arrive_city: str
    leave_city_by: str
    back_at_airport_by: str
    departure: str
    basis: str = 'taxi_estimate_straight_line_x1.3_with_traffic_buffer'

class OpenStatus(Strict):
    state: Literal['open','closed','unknown']
    confidence: Literal['high','medium','low']
    basis: str
    next_change: str | None = None

class Recommendation(Strict):
    poi_id: str
    name: str
    category: str
    distance_m: int = Field(ge=0)
    walk_min: int = Field(ge=0)
    travel_min: int = Field(ge=0)
    why: str = Field(min_length=1,max_length=700)
    visit_min: int = Field(ge=5,le=240)
    what_to_do: str = Field(min_length=1,max_length=500)
    open_status: OpenStatus
    source: Literal['poi_data'] = 'poi_data'
    idea_source: Literal['generated_idea'] = 'generated_idea'
    field_sources: dict[str,str] = Field(default_factory=lambda:{'name':'poi_data','open_status':'poi_data','distance_m':'calculated','travel_min':'calculated','visit_min':'generated_idea','what_to_do':'generated_idea','why':'generated_idea'})
    source_url: str
    collected_at: str
    data_used: list[str] = Field(min_length=1)
    caveats: str
    lat: float
    lon: float
    shelter: Literal['indoor','outdoor'] | None = None
    outdoor_min: int | None = Field(default=None,ge=0)
    warm_route: WarmRoute | None = None

class RouteStop(Strict):
    poi_id: str
    travel_min: int
    visit_min: int
    arrival_min: int
    departure_min: int

class Route(Strict):
    stops: list[RouteStop]
    total_min: int
    return_min: int
    basis: str

class Alternative(Strict):
    poi_id: str
    name: str
    relaxed_constraint: str
    travel_min: int
    source_url: str
    caveat: str

class Answer(Strict):
    interpretation: Interpretation
    recommendations: list[Recommendation] = Field(default_factory=list,max_length=3)
    route: Route | None = None
    clarifying_question: str | None = None
    message: str = ''
    alternative: Alternative | None = None
    response_type: Literal['recommendations','clarification','refusal'] = 'recommendations'
    generation_backend: str = 'template'
    retrieval_backend: str = 'lexical'
    weather: Weather | None = None
    layover: LayoverPlan | None = None

class Choice(Strict):
    poi_id: str
    reason: Literal['nearby','category','children','tourist','coffee','night','accessible','group','weather']
    activity: Literal['walk','look','coffee','eat','play','browse','show','read','fun','sport']
    visit_min: int = Field(ge=5,le=120)

class Choices(Strict):
    choices: list[Choice] = Field(min_length=1,max_length=3)
