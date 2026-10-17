from __future__ import annotations
import html,json,os
from datetime import datetime,date,time
import folium
import streamlit as st
from streamlit_folium import st_folium
from core.engine import Engine
from core.settings import CONFIG,DATA,ROOT
from core.geo import round_location
from core.hours import TZ
from core.i18n import tr
from eval.run_eval import scenarios

st.set_page_config(page_title='QALA · Прогулки по Астане',page_icon='◉',layout='wide',initial_sidebar_state='auto')
st.markdown('''<style>
 .block-container{max-width:1380px;padding-top:2rem;padding-bottom:2rem}
 [data-testid="stSidebar"]{background:#e8eee7;border-right:1px solid #d6e1d8}
 [data-testid="stSidebar"] .block-container{padding-top:2rem}
 h1,h2,h3{letter-spacing:-.035em!important;color:#193d35}
 h1{font-size:clamp(2rem,3.4vw,3.5rem)!important;line-height:1.12!important;font-weight:650!important}
 .eyebrow{font-size:11px;letter-spacing:.19em;font-weight:700;color:#548276;margin-bottom:15px}
 .lede{font-size:16px;line-height:1.6;color:#63766f;max-width:660px;margin-top:12px;margin-bottom:24px}
 .brand{font-size:30px;letter-spacing:.10em;color:#0d766b;font-weight:750;margin-bottom:0}
 .brand-sub{font-size:12px;color:#677b71;margin-bottom:28px}
 .pill{display:inline-block;font-size:11px;border-radius:30px;padding:5px 9px;margin-right:5px;background:#e9f0e8;color:#44634e;border:1px solid #d5e2d7}
 .status{font-size:12px;border-radius:9px;padding:9px 12px;margin:12px 0;background:#e6f3e8;color:#23633d}
 .status.unknown{background:#fff4d8;color:#7c641b}
 .num{display:inline-grid;place-items:center;background:#0d766b;color:white;width:29px;height:29px;border-radius:50%;font-size:14px;margin-right:9px}
 .rec-name{font-size:21px;font-weight:650;color:#193d35;line-height:1.35}
 .rec-meta{font-size:12px;color:#738177;margin:8px 0 12px}
 .rec-body{font-size:14px;line-height:1.65;color:#3a5148;margin:10px 0}
 .section-caption{font-size:12px;letter-spacing:.12em;color:#7c8d81;margin:14px 0}
 [data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:16px!important}
 div.stButton>button{border-radius:10px;font-size:13px;min-height:44px}
 .stChatInput{border-radius:16px}
 .small-note{font-size:11px;line-height:1.6;color:#75877b}
 @media(max-width:800px){.block-container{padding-top:1rem;padding-left:1rem;padding-right:1rem}.rec-name{font-size:19px}}
 </style>''',unsafe_allow_html=True)

@st.cache_resource(show_spinner=False,max_entries=1)
def get_engine(data_revision,index_revision):return Engine()

@st.cache_data(show_spinner=False)
def quality(data_revision):return json.loads((DATA/'quality.json').read_text(encoding='utf-8'))

@st.cache_data(show_spinner=False)
def public_map_context():
    p=DATA/'map_context.geojson'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'type':'FeatureCollection','features':[]}

DEMO=scenarios()[:5]
state=st.session_state
defaults={'preset':'Mega Silk Way','day':date(2026,10,17),'clock':15*60,'lang':'ru','mode':'walk','group':1,'accessible':False,'max_travel':20,'location':None,'last_answer':None,'last_debug':None,'last_query':'','tiles':False}
for k,v in defaults.items():state.setdefault(k,v)

def choose_demo(i):
    c=DEMO[i];at=datetime.fromisoformat(c['now'])
    state.update(preset=c['preset'],day=at.date(),clock=at.hour*60+at.minute,lang=c['language'],mode='walk',group=1,accessible=False,max_travel=20,location=None,pending_query=c['query'])

def preset_changed():state.location=None;state.last_answer=None

with st.sidebar:
    st.markdown('<div class="brand">QALA<span style="color:#ce824d">.</span></div><div class="brand-sub">Ваш час в Астане</div>',unsafe_allow_html=True)
    st.selectbox('📍 Где вы сейчас?',list(CONFIG['presets']),key='preset',on_change=preset_changed)
    if state.location:st.caption('Выбрана точка на карте. Координаты округлены.')
    st.date_input('Дата в Астане',key='day')
    st.select_slider('Время в Астане · UTC+5',options=list(range(0,1440,15)),key='clock',format_func=lambda x:f'{x//60:02d}:{x%60:02d}')
    st.caption('Время можно менять для демо')
    st.selectbox('Передвижение',['walk','transport'],format_func=lambda x:'Пешком' if x=='walk' else 'Транспорт · оценка',key='mode')
    st.slider('Максимум в пути, мин',1,60,key='max_travel')
    col1,col2=st.columns(2)
    with col1:st.selectbox('Язык ответа',['ru','en','kk'],format_func=lambda x:{'ru':'Русский','en':'English','kk':'Қазақша'}[x],key='lang')
    with col2:st.number_input('Человек',1,20,key='group')
    st.toggle('Доступность · wheelchair=yes',key='accessible')
    st.divider()
    st.caption('🔒 Координаты округляются до ~100 м. Живые запросы и локация не записываются на диск.')
    st.toggle('Подложка OpenStreetMap',key='tiles',help='При включении браузер запрашивает внешние тайлы карты: сервер тайлов видит IP и область просмотра. Без подложки карта показывает точки и радиус.')
    st.caption('Без подложки координаты не передаются поставщику карты. При включённом Gemini текст запроса после удаления координат и данные кандидатов отправляются в API.')
    if st.button('Очистить текущий сеанс',width='stretch'):
        for key in ['last_answer','last_debug','location']:state[key]=None
        state.last_query='';st.rerun()

st.markdown('<div class="eyebrow">АСТАНА / ГОРОД В ВАШЕМ ТЕМПЕ</div>',unsafe_allow_html=True)
st.title('Хорошая прогулка начинается рядом.')
st.markdown('<div class="lede">Скажите, чего хочется. Найдём до трёх мест с учётом пути и времени — и покажем, что о них известно.</div>',unsafe_allow_html=True)

if not (DATA/'pois.json').exists():
    st.error('Нет набора POI. Выполните python -m data.collect в папке проекта.');st.stop()

with st.spinner('Загружаю локальный индекс…'):
    try:engine=get_engine((DATA/'pois.json').stat().st_mtime,(DATA/'pois.faiss').stat().st_mtime if (DATA/'pois.faiss').exists() else 0)
    except Exception:
        st.error('Не удалось загрузить индекс. Проверьте установку: python -m pip install -r requirements.txt.');st.stop()
q=quality((DATA/'quality.json').stat().st_mtime)
st.markdown(f'<span class="pill">{q["count"]:,} мест OSM</span><span class="pill">{q["gold_reviewed"]} проверок по источнику</span><span class="pill">{html.escape(engine.retriever.backend)}</span><span class="pill">{q["collected_at"][:10]}</span>',unsafe_allow_html=True)
if engine.retriever.backend=='lexical':st.warning('Семантический индекс недоступен. Включён лексический поиск; восстановите индекс командой python -m core.retrieve --build.')
if os.getenv('LLM_PROVIDER','none')!='gemini':st.caption('Локальный режим: '+('семантический' if engine.retriever.backend=='e5+lexical' else 'лексический')+' поиск и проверяемые шаблонные идеи. Для LLM подключите Gemini в .env.')

st.markdown('<div class="section-caption">ПОПРОБУЙТЕ ОДНИМ НАЖАТИЕМ</div>',unsafe_allow_html=True)
cols=st.columns(5)
for i,(label,col) in enumerate(zip(['🌿 Прогулка у Mega','☕ Кофе и розетка','🧸 С ребёнком','✈️ Перед вылетом','🌙 Ночная Астана'],cols)):
    with col:st.button(label,key=f'demo_{i}',on_click=choose_demo,args=(i,),width='stretch')

now=datetime.combine(state.day,time(state.clock//60,state.clock%60),tzinfo=TZ)
location=state.location or round_location(*CONFIG['presets'][state.preset])
controls=(state.preset,state.day,state.clock,state.lang,state.mode,state.group,state.accessible,state.max_travel,tuple(location),(DATA/'pois.json').stat().st_mtime)
if state.get('answer_controls') and controls!=state.answer_controls and 'pending_query' not in state:
    state.last_answer=None;state.last_debug=None

typed=st.chat_input('Например: «Тихое кафе рядом, есть 45 минут»',max_chars=1500)
request=state.pop('pending_query',None) or typed
if request:
    with st.spinner('Сопоставляю места, путь и часы работы…'):
        try:
            answer,debug=engine.answer(request,location,now,language=state.lang,mode=state.mode,group_size=state.group,accessible=state.accessible,max_travel_min=state.max_travel)
            state.last_answer=answer;state.last_debug=debug;state.last_query=request;state.answer_controls=controls
        except Exception:
            st.error('Не удалось обработать запрос. Попробуйте быстрый сценарий. Если ошибка повторится, перезапустите приложение.');state.last_answer=None

answer=state.last_answer;debug=state.last_debug
left,right=st.columns([1.12,1],gap='large')
with left:
    if answer:
        with st.chat_message('user'):st.write(state.last_query)
        lang=answer.interpretation.language
        if answer.message:st.info(answer.message)
        if answer.clarifying_question and answer.clarifying_question!=answer.message:st.write(answer.clarifying_question)
        if answer.recommendations:
            st.caption(f'{len(answer.recommendations)} варианта · {debug.get("elapsed_ms",0)/1000:.2f} с · '+('маршрут ниже' if answer.route else 'выберите один, время рассчитано с возвращением'))
        for n,r in enumerate(answer.recommendations,1):
            with st.container(border=True):
                st.markdown(f'<div class="rec-name"><span class="num">{n}</span>{html.escape(r.name)}</div>',unsafe_allow_html=True)
                mode_label={'ru':'пешком','en':'walking','kk':'жаяу'}[lang] if answer.interpretation.mode=='walk' else {'ru':'на транспорте','en':'by transport','kk':'көлікпен'}[lang]
                distance_label={'ru':'м по прямой','en':'m straight line','kk':'м түзу қашықтық'}[lang]
                unit='min' if lang=='en' else 'мин'
                st.markdown(f'<div class="rec-meta">{r.distance_m} {distance_label} &nbsp;·&nbsp; ≈ {r.travel_min} {unit} {mode_label}</div>',unsafe_allow_html=True)
                poi_label={'ru':'Данные POI','en':'POI data','kk':'POI деректері'}[lang];idea_label={'ru':'Сгенерированная идея','en':'Generated idea','kk':'Жасалған идея'}[lang]
                st.markdown(f'<span class="pill">📍 {poi_label}</span><span class="pill">💡 {idea_label}</span>',unsafe_allow_html=True)
                why_label={'ru':'Почему','en':'Why','kk':'Неліктен'}[lang];plan_label={'ru':'План','en':'Plan','kk':'Жоспар'}[lang]
                st.markdown(f'<div class="rec-body"><b>{why_label}.</b> {html.escape(r.why)}<br><b>{plan_label} · {r.visit_min} {unit}.</b> {html.escape(r.what_to_do)}</div>',unsafe_allow_html=True)
                confidence={'ru':{'high':'высокая','medium':'средняя','low':'низкая'},'en':{'high':'high','medium':'medium','low':'low'},'kk':{'high':'жоғары','medium':'орташа','low':'төмен'}}[lang][r.open_status.confidence]
                if r.open_status.state=='open':
                    until=({'ru':' до ','en':' until ','kk':' — '}[lang]+datetime.fromisoformat(r.open_status.next_change).strftime('%H:%M')) if r.open_status.next_change else ''
                    status={'ru':'По расписанию OSM открыто','en':'Open according to OSM hours','kk':'OSM кестесі бойынша ашық'}[lang]+until
                else:status={'ru':'Часы не подтверждены','en':'Opening hours unconfirmed','kk':'Жұмыс уақыты расталмаған'}[lang]
                status+=' · '+{'ru':'уверенность ','en':'confidence ','kk':'сенімділік '}[lang]+confidence
                st.markdown(f'<div class="status {"unknown" if r.open_status.state=="unknown" else ""}">{html.escape(status)}</div>',unsafe_allow_html=True)
                with st.expander('Уточнения и источник'):
                    st.write(r.caveats);st.caption(tr(lang,'visit'))
                    st.caption('Использованы: '+', '.join(r.data_used))
                    st.caption('Обновлено: '+r.collected_at[:10]+' · '+r.open_status.basis)
                    st.link_button('Источник OSM',r.source_url)
                    # Explicit click opens an external editor; no reports/coordinates sent automatically.
                    st.link_button('Сообщить о неточности в OSM',r.source_url+'?mlat='+str(r.lat)+'&mlon='+str(r.lon))
        if answer.alternative:
            alt=answer.alternative
            st.warning(f'Ближайшая альтернатива: {alt.name}, около {alt.travel_min} мин в пути. Нужно {alt.relaxed_constraint}. {alt.caveat}')
        if answer.route:
            route=answer.route;names={r.poi_id:r.name for r in answer.recommendations}
            st.subheader(f'Ваш мини-маршрут · {route.total_min} мин')
            for stop in route.stops:st.write(f'{stop.arrival_min:02d}–{stop.departure_min:02d} мин · {names[stop.poi_id]} · переход {stop.travel_min} мин')
            st.caption(f'Возвращение к началу: ещё {route.return_min} мин. Линии схематические, без проверки пешеходных переходов.')
        elif answer.interpretation.route_requested and answer.recommendations:st.info('Объединить эти варианты в маршрут в заданное время не удалось. Выберите один.')
    else:
        st.markdown('### Один свободный час.\nНесколько хороших вариантов.')
        st.write('Выберите сценарий выше или напишите запрос в поле внизу. Точку старта можно изменить нажатием на карту.')
        st.info('Часы и удобства известны не для каждого места. Если данных нет, покажем это прямо в карточке.')
        st.caption('Оценка пути — расстояние по прямой × 1,3. Погода, пробки, входы и реальные переходы пока не учитываются.')

with right:
    st.markdown('### Рядом с вами')
    st.caption(f'{state.preset if not state.location else "Точка на карте"} · {now.strftime("%d.%m · %H:%M")} · UTC+5')
    m=folium.Map(location=location,zoom_start=14,tiles='OpenStreetMap' if state.tiles else None,control_scale=True)
    folium.CircleMarker(location=location,radius=8,color='#fff',weight=3,fill=True,fill_color='#0d766b',fill_opacity=1,tooltip='Вы здесь · примерно').add_to(m)
    radius=state.max_travel*CONFIG['walk_m_per_min']/CONFIG['detour_factor'] if state.mode=='walk' else max(0,state.max_travel-CONFIG['transport_overhead_min'])*CONFIG['transport_m_per_min']/CONFIG['detour_factor']
    folium.Circle(location=location,radius=radius,color='#0d766b',weight=1,fill=True,fill_opacity=.055,dash_array='4,6').add_to(m)
    if not state.tiles:
        if (DATA/'map_context.geojson').exists():
            raw_context=public_map_context()
            context={'type':'FeatureCollection','features':[f for f in raw_context['features'] if any(abs(y-location[0])<.035 and abs(x-location[1])<.06 for x,y in f['geometry']['coordinates'])]}
            folium.GeoJson(context,style_function=lambda f:{'color':'#91bdc7' if f['properties']['kind']=='river' else '#b7c6b7','weight':7 if f['properties']['kind']=='river' else 2,'opacity':.7},tooltip=folium.GeoJsonTooltip(fields=['name'],labels=False)).add_to(m)
        # Context labels are public presets, rendered locally without tile requests.
        for label,point in CONFIG['presets'].items():
            folium.CircleMarker(point,radius=3,color='#8a9f93',tooltip=label).add_to(m)
        boundary=json.loads((DATA/'boundary.geojson').read_text(encoding='utf-8'))
        folium.GeoJson(boundary,style_function=lambda x:{'fillOpacity':0,'color':'#c9d3c9','weight':1}).add_to(m)
    if answer:
        for n,r in enumerate(answer.recommendations,1):
            folium.Marker([r.lat,r.lon],tooltip=html.escape(r.name),icon=folium.DivIcon(html=f'<div style="background:#0d766b;color:white;border:3px solid white;border-radius:50%;width:30px;height:30px;text-align:center;line-height:24px;font-weight:bold">{n}</div>')).add_to(m)
        if answer.route:
            byid={r.poi_id:r for r in answer.recommendations}
            pts=[location]+[(byid[s.poi_id].lat,byid[s.poi_id].lon) for s in answer.route.stops]+[location]
            folium.PolyLine(pts,color='#d48b53',weight=3,dash_array='8,8',tooltip='Схема, не пешеходная навигация').add_to(m)
    clicked=st_folium(m,height=460,width=None,use_container_width=True,returned_objects=['last_clicked'],key='map_'+str(location))
    if clicked and clicked.get('last_clicked'):
        point=round_location(clicked['last_clicked']['lat'],clicked['last_clicked']['lng'])
        if tuple(point)!=tuple(location):state.location=point;state.last_answer=None;st.rerun()
    st.caption('Нажмите на карту, чтобы выбрать старт. Круг показывает приблизительный лимит пути. Подложка по умолчанию выключена для приватности.')
    with st.expander('Как это получилось',expanded=False):
        if not answer:st.write('Здесь появятся ограничения, кандидаты и причины отсева после запроса.')
        else:
            st.write('**Разбор запроса**');st.json(answer.interpretation.model_dump())
            st.write(f'POI в базе: {debug["total_pois"]}. После фильтров: {debug.get("accepted",0)}.')
            if debug.get('cache_hit'):st.info('Ответ из кэша фиксированного демо. Ограничения и часы перепроверены.')
            reason_labels={'travel_limit':'Дальше лимита пути','category':'Не соответствует категории','closed_now':'Закрыто в '+now.strftime('%H:%M'),'closed_on_arrival':'Закроется к прибытию','closes_during_visit':'Закроется до конца визита','night_hours_unconfirmed':'Ночью часы не подтверждены','night_lighting_unconfirmed':'Ночью освещение не подтверждено','time_budget':'Не помещается в бюджет времени','wheelchair_unconfirmed':'Доступность не подтверждена','restricted_access':'Доступ ограничен','disused':'Не используется','socket_unconfirmed':'Розетки не подтверждены','wifi_unconfirmed':'Wi-Fi не подтверждён','quiet_unconfirmed':'Тишина не подтверждена','children':'Не подходит детскому сценарию'}
            st.write('**Причины отсева**');st.json({reason_labels.get(k,k):v for k,v in debug.get('rejected_counts',{}).items()})
            if debug.get('candidates'):st.dataframe([{'место':c['name'],'категория':c['category'],'скор':c['score'],'путь, мин':c['travel_min'],'статус':c['open_status']['state']} for c in debug['candidates']],hide_index=True)
            if debug.get('rejections'):st.dataframe([{'Место':r['name'],'Причина':reason_labels.get(r['reason'],r['reason']),'Путь, мин':r['travel_min']} for r in debug['rejections']],hide_index=True)
            st.caption('Скор = семантика + близость + категория + подтверждённые часы + популярность + проверка источника − штраф за неизвестные часы. Веса в config.yaml.')
            st.write('**Техническая проверка**');st.json(debug.get('generation',{}))
            st.download_button('Скачать JSON этого ответа',answer.model_dump_json(indent=2),file_name='recommendation.json',mime='application/json',help='Скачивается по вашему нажатию. Точных координат пользователя в JSON нет.')

st.divider()
st.caption('QALA · хакатон НИЦ Smart City · © OpenStreetMap contributors, ODbL · OSM — сведения из открытой карты, а не подтверждение организации. Сгенерированные планы не описывают гарантированные услуги.')
