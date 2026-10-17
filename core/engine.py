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
from core.i18n import tr
from core.route import build_route
from core.settings import CONFIG

class Engine:
    def __init__(self,pois=None,backend=None):
        self.retriever=Retriever(pois=pois,backend=backend)
        self.pois=self.retriever.pois

    def answer(self,query,location,now=None,language=None,mode=None,group_size=1,accessible=False,max_travel_min=None,use_cache=True):
        start=perf_counter();now=local_time(now or datetime.now().astimezone())
        intent_parser=parse_rules if use_cache and os.getenv('DEMO_CACHE','0')=='1' else parse
        intent=intent_parser(query,language=language,mode=mode,group_size=group_size,accessible=accessible,max_travel_min=max_travel_min)
        debug={'total_pois':len(self.pois),'retrieval_backend':self.retriever.backend,'retrieval_warning':self.retriever.warning,'parser':intent.parser}
        def stop(key,kind='refusal'):
            debug['elapsed_ms']=round((perf_counter()-start)*1000,1)
            return Answer(interpretation=intent,recommendations=[],response_type=kind,message=tr(intent.language,key),clarifying_question=tr(intent.language,key) if kind=='clarification' else None,retrieval_backend=self.retriever.backend),debug
        if harmful(query):return stop('harm')
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
        if use_cache:
            from core.cache import load_demo
            cached=load_demo(query,location,now,intent,self.pois)
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
        accepted,rejected=filter_candidates(self.pois,location,now,intent)
        debug.update({'accepted':len(accepted),'rejected_counts':dict(Counter(r['reason'] for r in rejected)),'rejections':sorted(rejected,key=lambda r:r['distance_m'])[:30]})
        if not accepted:
            answer,_=stop('none')
            # Explicitly labeled alternatives never enter the recommendations list.
            relaxed=intent.model_copy(deep=True);relaxed.max_travel_min=90;relaxed.duration_min=480
            possible,_=filter_candidates(self.pois,location,now,relaxed)
            constraint={'ru':'увеличить лимит пути/общего времени','en':'increase the travel/time budget','kk':'жол не жалпы уақыт шегін ұлғайту'}[intent.language]
            if not possible and any('require_'+x in intent.constraints for x in ['socket','wifi','quiet']):
                relaxed.constraints=[c for c in intent.constraints if c not in {'require_socket','require_wifi','require_quiet'}]
                possible,_=filter_candidates(self.pois,location,now,relaxed)
                constraint={'ru':'допустить неподтверждённые розетки/Wi-Fi/тишину и при необходимости увеличить время','en':'allow unverified outlets/Wi-Fi/quietness and a longer time budget if needed','kk':'расталмаған розетка/Wi-Fi/тыныштыққа және қажет болса ұзақ уақытқа келісу'}[intent.language]
            if possible:
                c=min(possible,key=lambda c:c.distance_m)
                answer.alternative=Alternative(poi_id=c.poi['id'],name=safe_text(c.poi.get('name_'+intent.language) or c.poi['name']),travel_min=c.travel_min,source_url=c.poi['source'],relaxed_constraint=constraint,caveat=tr(intent.language,'unknown_alt')+(' '+tr(intent.language,'unknown_hours') if c.open_status.state=='unknown' else ''))
            return answer,debug
        scores=self.retriever.scores(query,intent.categories)
        ranked=rank(accepted,scores,intent);pool=candidate_pool(ranked)
        debug['candidates']=[{'poi_id':c.poi['id'],'name':safe_text(c.poi['name']),'category':c.poi['category'],'score':round(c.score,4),'score_parts':c.score_parts,'distance_m':c.distance_m,'travel_min':c.travel_min,'open_status':c.open_status.model_dump()} for c in pool]
        answer,gen_debug=generate(pool,intent,night=now.hour>=22 or now.hour<6)
        answer.retrieval_backend=self.retriever.backend
        if intent.route_requested:answer.route=build_route(answer.recommendations,{p['id']:p for p in self.pois},location,now,intent)
        debug['generation']=gen_debug
        debug['elapsed_ms']=round((perf_counter()-start)*1000,1)
        return answer,debug
