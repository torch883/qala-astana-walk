from __future__ import annotations
from collections import Counter
from datetime import datetime
from time import perf_counter
import os
from core.schemas import Answer,Alternative
from core.parse import parse,parse_rules
from core.geo import round_location,in_city,travel,haversine
from core.hours import local_time
from core.security import harmful,safe_text
from core.rank import filter_candidates,rank,candidate_pool
from core.retrieve import Retriever
from core.generate import generate
from core.i18n import tr,place
from core.route import build_route
from core.settings import CONFIG
from core.weather import Env,advice
from core import layover as lay

class Engine:
    def __init__(self,pois=None,backend=None):
        self.retriever=Retriever(pois=pois,backend=backend)
        self.pois=self.retriever.pois
        self.by_id={p['id']:p for p in self.pois}
        # Warm hubs and indoor/outdoor labels are computed once; they matter only when weather is passed in.
        self.env=Env(self.pois)

    def answer(self,query,location,now=None,language=None,mode=None,group_size=1,accessible=False,max_travel_min=None,use_cache=True,weather=None,parsed_intent=None,deadline=None,cache_enabled=None,transfer_floor=0):
        start=perf_counter();now=local_time(now or datetime.now().astimezone())
        cache_on=os.getenv('DEMO_CACHE','0')=='1' if cache_enabled is None else cache_enabled
        intent_parser=parse_rules if use_cache and cache_on else parse
        intent=parsed_intent.model_copy(deep=True) if parsed_intent is not None else intent_parser(query,language=language,mode=mode,group_size=group_size,accessible=accessible,max_travel_min=max_travel_min)
        debug={'total_pois':len(self.pois),'retrieval_backend':self.retriever.backend,'retrieval_warning':self.retriever.warning,'parser':intent.parser,'weather':weather.model_dump() if weather else None}
        def stop(key,kind='refusal',**values):
            debug['elapsed_ms']=round((perf_counter()-start)*1000,1)
            text=tr(intent.language,key).format(**values) if values else tr(intent.language,key)
            return Answer(interpretation=intent,recommendations=[],response_type=kind,message=text,clarifying_question=text if kind=='clarification' else None,retrieval_backend=self.retriever.backend,weather=weather),debug
        if harmful(query):return stop('harm')
        if deadline is not None:deadline=local_time(deadline)
        if intent.intent=='layover':return self.layover(query,intent,location,now,weather,debug,stop,start,transfer_floor,deadline)
        if location is None:return stop('location','clarification')
        try:location=round_location(*location)
        except (ValueError,TypeError):return stop('invalid','clarification')
        if not in_city(location):return stop('outside')
        if intent.flight_in_min is not None:
            airport=CONFIG['presets']['Аэропорт']
            _,to_airport=travel(round(haversine(*location,*airport)),'transport')
            remaining=intent.flight_in_min-CONFIG['airport_reserve_min']-to_airport
            if remaining<20:return stop('flight')
            intent.duration_min=min(intent.duration_min,remaining)
        # Exact pre-recorded public demo scenarios only, never persistent user-query caching.
        # The cache was recorded without weather, so it is skipped whenever weather changes the ranking.
        if use_cache and (weather is None or weather.level=='ok'):
            from core.cache import load_demo
            cached=load_demo(query,location,now,intent,self.pois,enabled=cache_on) if deadline is None else None
            if cached:
                answer=cached
                # Fresh filters + validator protect against stale cache and edited opening hours.
                accepted,rejected=filter_candidates(self.pois,location,now,intent)
                from core.validate import validate_answer
                try:
                    validate_answer(answer,accepted,intent)
                    debug.update({'cache_hit':True,'accepted':len(accepted),'rejected_counts':dict(Counter(r['reason'] for r in rejected)),'elapsed_ms':round((perf_counter()-start)*1000,1)})
                    return answer,debug
                except ValueError:pass
        if deadline is not None:
            remaining=int((deadline-now).total_seconds()//60)
            if remaining<5:return stop('none')
            intent.duration_min=min(intent.duration_min,remaining)
        answer,_=self.recommend(query,intent,location,now,weather,debug,stop,deadline=deadline)
        debug['elapsed_ms']=round((perf_counter()-start)*1000,1)
        return answer,debug

    def recommend(self,query,intent,location,now,weather,debug,stop,alternatives=True,deadline=None):
        accepted,rejected=filter_candidates(self.pois,location,now,intent,weather,self.env,deadline=deadline)
        debug.update({'accepted':len(accepted),'rejected_counts':dict(Counter(r['reason'] for r in rejected)),'rejections':sorted(rejected,key=lambda r:(r['reason'] in {'category','travel_limit'},r['distance_m']))[:30]})
        if not accepted:
            # Harsh weather explains an empty answer better than a generic «nothing found».
            if weather is not None and weather.level=='harsh' and any(r['reason'].startswith('weather_') for r in rejected):
                return stop('weather_none',advice=advice(weather,intent.language))
            answer,_=stop('none')
            if not alternatives:return answer,debug
            # Explicitly labeled alternatives never enter the recommendations list.
            relaxed=intent.model_copy(deep=True);relaxed.max_travel_min=90;relaxed.duration_min=480
            possible,_=filter_candidates(self.pois,location,now,relaxed,weather,self.env)
            constraint={'ru':'увеличить лимит пути/общего времени','en':'increase the travel/time budget','kk':'жол не жалпы уақыт шегін ұлғайту'}[intent.language]
            if not possible and any('require_'+x in intent.constraints for x in ['socket','wifi','quiet']):
                relaxed.constraints=[c for c in intent.constraints if c not in {'require_socket','require_wifi','require_quiet'}]
                possible,_=filter_candidates(self.pois,location,now,relaxed,weather,self.env)
                constraint={'ru':'допустить неподтверждённые розетки/Wi-Fi/тишину и при необходимости увеличить время','en':'allow unverified outlets/Wi-Fi/quietness and a longer time budget if needed','kk':'расталмаған розетка/Wi-Fi/тыныштыққа және қажет болса ұзақ уақытқа келісу'}[intent.language]
            if possible:
                c=min(possible,key=lambda c:c.distance_m)
                answer.alternative=Alternative(poi_id=c.poi['id'],name=safe_text(c.poi.get('name_'+intent.language) or c.poi['name']),travel_min=c.travel_min,source_url=c.poi['source'],relaxed_constraint=constraint,caveat=tr(intent.language,'unknown_alt')+(' '+tr(intent.language,'unknown_hours') if c.open_status.state=='unknown' else ''))
            return answer,debug
        scores=self.retriever.scores(query,intent.categories)
        ranked=rank(accepted,scores,intent,weather);pool=candidate_pool(ranked)
        debug['candidates']=[{'poi_id':c.poi['id'],'name':safe_text(c.poi['name']),'category':c.poi['category'],'score':round(c.score,4),'score_parts':c.score_parts,'distance_m':c.distance_m,'travel_min':c.travel_min,'open_status':c.open_status.model_dump(),'shelter':c.shelter,'outdoor_min':c.outdoor_min,'warm_hub':c.warm.hub_name if c.warm else None} for c in pool]
        answer,gen_debug=generate(pool,intent,night=now.hour>=22 or now.hour<6,weather=weather)
        answer.retrieval_backend=self.retriever.backend
        if intent.route_requested:answer.route=build_route(answer.recommendations,self.by_id,location,now,intent,weather,self.env)
        debug['generation']=gen_debug
        return answer,debug

    def layover(self,query,intent,location,now,weather,debug,stop,start,transfer_floor=0,deadline=None):
        """«Астана за пересадку»: try each drop-off point inside a window derived backwards from the departure."""
        total=lay.layover_minutes(intent,now)
        if total is None:return stop('layover_need_time','clarification')
        c=CONFIG['layover'];plans=lay.windows(total,now,transfer_floor,deadline)
        if not plans:return stop('layover_short',layover=total,min=c['min_city_min'],exit=c['exit_min'],reserve=c['return_reserve_min'])
        best=None
        for order,plan in enumerate(plans):
            sub=intent.model_copy(deep=True);sub.duration_min=max(5,min(480,plan.city_min));sub.mode='walk';sub.route_requested=True
            found,found_debug=self.recommend(query,sub,(plan.anchor_lat,plan.anchor_lon),datetime.fromisoformat(plan.arrive_city),weather,{},stop,alternatives=False,deadline=datetime.fromisoformat(plan.leave_city_by))
            if not found.recommendations:continue
            # More places first, then a complete mini-route, then the configured order of drop-off points.
            key=(-len(found.recommendations),found.route is None,order)
            if best is None or key<best[0]:best=(key,plan,found,found_debug)
        debug['layover_windows']=[p.model_dump() for p in plans]
        if best is None:return stop('layover_none')
        _,plan,answer,found_debug=best
        lay.check_plan(plan,answer.route)
        debug.update(found_debug)
        lang=intent.language;hhmm=lambda s:datetime.fromisoformat(s).strftime('%H:%M')
        notes=[tr(lang,'layover_visa'),tr(lang,'layover_transfer')]
        if location is not None and haversine(*location,*lay.airport())>3000:notes.insert(0,tr(lang,'layover_assume'))
        answer.layover=plan
        answer.message=tr(lang,'layover_plan').format(arrive=hhmm(plan.arrive_city),anchor=place(lang,plan.anchor),leave=hhmm(plan.leave_city_by),back=hhmm(plan.back_at_airport_by),reserve=plan.reserve_min,departure=hhmm(plan.departure))+' '+' '.join(notes)
        debug['elapsed_ms']=round((perf_counter()-start)*1000,1)
        return answer,debug
