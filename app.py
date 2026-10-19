from __future__ import annotations
import html,json,math,os
from datetime import datetime,date,time
import folium
import streamlit as st
from branca.element import MacroElement
from jinja2 import Template
from streamlit_folium import st_folium
from core.engine import Engine
from core.settings import CONFIG,DATA,ROOT
from core.geo import round_location
from core.hours import TZ
from core.i18n import TEXT,tr,place
from core.weather import fetch as fetch_weather,preset as weather_preset
from eval.run_eval import scenarios

state=st.session_state
state.setdefault('lang','ru')
# Read once per run: format_func callbacks may run outside the script context, where session state is unavailable.
ui_lang=state.lang
def tl(lang,key,**values):
    text=tr(lang,'ui_'+key)
    return text.format(**values) if values else text
# Interface labels follow the selected language; answer cards follow the answer's own language.
def t(key,**values):return tl(ui_lang,key,**values)

st.set_page_config(page_title=t('page_title'),page_icon='◉',layout='wide',initial_sidebar_state='auto')
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
 .legend{font-size:12px;line-height:2;color:#738177;margin:4px 0 2px}
 .deadline{font-size:18px;font-weight:650;color:#193d35;background:#fbeee2;border-left:4px solid #ce824d;border-radius:10px;padding:12px 14px;margin:4px 0 12px}
 .lay-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 12px}
 .lay-grid div{background:#fff;border:1px solid #dfe7df;border-radius:12px;padding:8px 10px}
 .lay-grid small{display:block;font-size:12px;color:#738177;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .lay-grid b{font-size:22px;font-weight:650;color:#193d35}
 .warn{font-size:13px;line-height:1.5;color:#7c641b;margin:3px 0}
 [data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:16px!important}
 div.stButton>button{border-radius:10px;font-size:13px;min-height:44px}
 /* Demo buttons sit in a fixed grid, so a rerun never moves them under the finger. */
 .st-key-demos{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));gap:.6rem}
 .st-key-demos>div{width:auto!important;min-width:0}
 .st-key-demos button{width:100%;height:100%;min-height:48px;line-height:1.2}
 .st-key-ctx_row{flex-wrap:nowrap!important;overflow-x:auto;scrollbar-width:none;gap:.5rem!important}
 .st-key-ctx_row>div{flex:0 0 auto}
 .st-key-ctx_row button{min-height:36px;font-size:13px;padding:4px 10px;white-space:nowrap}
 .st-key-ctx_row button [data-testid="stIconMaterial"]{display:none}
 .st-key-answer{scroll-margin-top:4.5rem}
 .st-key-qala_viewport,.st-key-qala_scroll{display:none!important}
 .stChatInput{border-radius:16px}
 .small-note{font-size:11px;line-height:1.6;color:#75877b}
 @media(min-width:800px){
  .st-key-ctx_row{display:none!important}
  [data-testid="stColumn"]:has(.st-key-map_col){position:sticky;top:1rem;align-self:flex-start}
 }
 @media(max-width:799.98px){
  .block-container{padding-top:3.5rem;padding-left:1rem;padding-right:1rem}
  h1{font-size:1.9rem!important}
  .lede{font-size:15px;margin-bottom:12px}
  .rec-name{font-size:19px}
  .st-key-demos{grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem}
  .st-key-demos button{font-size:12.5px;padding:6px 8px}
  .lay-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
 }
 </style>''',unsafe_allow_html=True)

# Viewport bridge: reports whether the page is narrower than 800 px and, on phones, scrolls to a fresh answer.
VIEWPORT_JS='''
export default function({data, setStateValue}) {
  const narrow = () => window.innerWidth < 800;
  if (data.mode === 'scroll') {
    if (data.token && narrow() && window.__qalaScrolled !== data.token) {
      window.__qalaScrolled = data.token;
      let tries = 0;
      const go = () => {
        const el = document.querySelector('.st-key-answer');
        // Smooth scrolling never runs in a hidden tab, so jump instead there.
        if (el) el.scrollIntoView({behavior: document.visibilityState === 'visible' ? 'smooth' : 'auto', block: 'start'});
        else if (tries++ < 30) setTimeout(go, 100);
      };
      setTimeout(go, 50);
    }
    return;
  }
  let last = data.narrow;
  const report = () => { const n = narrow(); if (n !== last) { last = n; setStateValue('narrow', n); } };
  report();
  window.addEventListener('resize', report);
  return () => window.removeEventListener('resize', report);
}'''
try:viewport_component=st.components.v2.component('qala_viewport',js=VIEWPORT_JS)
except Exception:viewport_component=None
def viewport(**kwargs):
    if viewport_component is None:return None
    try:return viewport_component(**kwargs)
    except Exception:return None

def phone_user_agent():
    try:ua=st.context.headers.get('User-Agent') or ''
    except Exception:ua=''
    return any(k in ua for k in ('Mobi','Android','iPhone'))

# code_revision changes when Streamlit re-imports core/ after an edit; a stale engine would mix old and new model classes.
@st.cache_resource(show_spinner=False,max_entries=1)
def get_engine(data_revision,index_revision,code_revision):return Engine()

@st.cache_data(show_spinner=False)
def quality(data_revision):return json.loads((DATA/'quality.json').read_text(encoding='utf-8'))

@st.cache_data(show_spinner=False)
def public_map_context():
    p=DATA/'map_context.geojson'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'type':'FeatureCollection','features':[]}

@st.cache_data(show_spinner=False,ttl=1800)
def forecast(hour_iso):return fetch_weather(datetime.fromisoformat(hour_iso))

@st.cache_data(show_spinner=False)
def hub_shapes():return json.loads((DATA/'warm_hubs.geojson').read_text(encoding='utf-8')) if (DATA/'warm_hubs.geojson').exists() else {'type':'FeatureCollection','features':[]}

class FitView(MacroElement):
    """Fit the map to the given bounds, and again once the iframe gets its real width: phones lay it out late."""
    _template=Template('''{% macro script(this,kwargs) %}
(function(m){var b=L.latLngBounds({{ this.bounds|tojson }}),o={padding:[28,28],maxZoom:16},c=m.getContainer(),w=0;
function fit(){if(!c.clientWidth)return;w=c.clientWidth;m.invalidateSize();m.fitBounds(b,o);}
if(window.ResizeObserver)new ResizeObserver(function(){if(c.clientWidth!==w)fit();}).observe(c);
fit();})({{ this._parent.get_name() }});
{% endmacro %}''')
    def __init__(self,bounds):
        super().__init__();self._name='FitView';self.bounds=bounds

DEMO_IDS=['mega_walk','coffee_socket','child','airport_flight','unusual_night','layover_long','frost_walk']
DEMO={c['id']:c for c in scenarios()}
WEATHER_KEYS=['auto','off','frost','blizzard','rain','heat','mild']
WEATHER_DEFAULT=os.getenv('WEATHER','auto') if os.getenv('WEATHER','auto') in WEATHER_KEYS else 'auto'
LANGS={'ru':'Русский','en':'English','kk':'Қазақша'}
CLOCK=list(range(0,1440,15))
hhmm=lambda x:f'{x//60:02d}:{x%60:02d}'
# Start at the current Astana time on the slider's 15-minute grid; demo buttons set their own time.
started=datetime.now(TZ)
defaults={'preset':'Mega Silk Way','day':started.date(),'clock':(started.hour*60+started.minute)//15*15,'lang':'ru','mode':'walk','group':1,'accessible':False,'max_travel':20,'location':None,'last_answer':None,'last_debug':None,'last_query':'','tiles':False,'weather':WEATHER_DEFAULT,'narrow':phone_user_agent(),'answer_seq':0}
for k,v in defaults.items():state.setdefault(k,v)

def choose_demo(i):
    c=DEMO[DEMO_IDS[i]];at=datetime.fromisoformat(c['now'])
    state.update(preset=c['preset'],day=at.date(),clock=at.hour*60+at.minute,lang=c['language'],mode='walk',group=1,accessible=False,max_travel=20,location=None,weather=c.get('weather',WEATHER_DEFAULT),pending_query=c['query'])

def preset_changed():state.location=None;state.last_answer=None

# The phone-only context row edits the same settings as the sidebar through mirrored widget keys.
MIRRORED=['preset','day','clock','weather','lang']
def mirror(key):
    state[key]=state['m_'+key]
    if key=='preset':preset_changed()

def count_options(lang,n):
    forms=tl(lang,'option_forms').split('|')
    if lang=='ru':i=0 if n%10==1 and n%100!=11 else 1 if 2<=n%10<=4 and not 12<=n%100<=14 else 2
    elif lang=='en':i=0 if n==1 else 1
    else:i=0
    return f'{n} {forms[i]}'

res=viewport(key='qala_viewport',data={'mode':'width','narrow':state.narrow},on_narrow_change=lambda:None)
if res is not None and res.get('narrow') is not None:state.narrow=bool(res['narrow'])

with st.sidebar:
    st.markdown(f'<div class="brand">QALA<span style="color:#ce824d">.</span></div><div class="brand-sub">{t("brand_sub")}</div>',unsafe_allow_html=True)
    st.selectbox(t('where'),list(CONFIG['presets']),format_func=lambda x:place(ui_lang,x),key='preset',on_change=preset_changed)
    if state.location:st.caption(t('map_point_chosen'))
    st.date_input(t('date'),key='day')
    st.select_slider(t('time'),options=CLOCK,key='clock',format_func=hhmm)
    st.selectbox(t('mode'),['walk','transport'],format_func=lambda x:t('mode_'+x),key='mode')
    st.slider(t('max_travel'),1,60,key='max_travel')
    col1,col2=st.columns(2)
    with col1:st.selectbox(t('lang'),list(LANGS),format_func=LANGS.get,key='lang')
    with col2:st.number_input(t('group'),1,20,key='group')
    st.toggle(t('accessible'),key='accessible',help=t('accessible_help'))
    st.selectbox(t('weather'),WEATHER_KEYS,format_func=lambda x:t('weather_'+x),key='weather',help=t('weather_help'))
    st.divider()
    st.caption(t('privacy'))
    st.toggle(t('tiles'),key='tiles',help=t('tiles_help'))
    st.caption(t('llm_note'))
    if st.button(t('clear'),width='stretch'):
        for key in ['last_answer','last_debug','location']:state[key]=None
        state.last_query='';st.rerun()

# Everything above the demo buttons is static, so their position does not change between reruns.
st.markdown(f'<div class="eyebrow">{t("eyebrow")}</div>',unsafe_allow_html=True)
st.title(t('title'))
st.markdown(f'<div class="lede">{t("lede")}</div>',unsafe_allow_html=True)
st.markdown(f'<div class="section-caption">{t("try")}</div>',unsafe_allow_html=True)
with st.container(key='demos'):
    for i,demo_id in enumerate(DEMO_IDS):st.button(t('demo_'+demo_id),key=f'demo_{i}',on_click=choose_demo,args=(i,),width='stretch')

if not (DATA/'pois.json').exists():
    st.error(t('error_no_pois'));st.stop()

now=datetime.combine(state.day,time(state.clock//60,state.clock%60),tzinfo=TZ)
location=state.location or round_location(*CONFIG['presets'][state.preset])
# Weather for the selected hour: a live forecast, an explicit demo scenario, or nothing.
weather=forecast(now.replace(minute=0).isoformat()) if state.weather=='auto' else (weather_preset(state.weather,now) if state.weather!='off' else None)

with st.container(horizontal=True,key='ctx_row',gap='small'):
    for k in MIRRORED:state['m_'+k]=state[k]
    with st.popover('📍 '+(t('map_point') if state.location else place(ui_lang,state.preset))):
        st.selectbox(t('where'),list(CONFIG['presets']),format_func=lambda x:place(ui_lang,x),key='m_preset',on_change=mirror,args=('preset',))
        st.caption(t('map_hint'))
    with st.popover('🕒 '+now.strftime('%H:%M' if state.day==started.date() else '%d.%m %H:%M')):
        st.date_input(t('date'),key='m_day',on_change=mirror,args=('day',))
        st.select_slider(t('time'),options=CLOCK,key='m_clock',format_func=hhmm,on_change=mirror,args=('clock',))
    with st.popover('🌡 '+(f'{weather.temperature_c:+.0f} °C'+(' · '+t('weather_scenario_short') if weather.source!='open-meteo' else '') if weather else '—')):
        st.selectbox(t('weather'),WEATHER_KEYS,format_func=lambda x:t('weather_'+x),key='m_weather',on_change=mirror,args=('weather',))
        st.caption(t('weather_help'))
    with st.popover('🌐 '+ui_lang.upper()):
        st.selectbox(t('lang'),list(LANGS),format_func=LANGS.get,key='m_lang',on_change=mirror,args=('lang',))

with st.container():
    # Inside a container the chat input stays inline. At the top level Streamlit pins it to the bottom
    # and keeps the whole page scrolled down, which hid the title and the demo buttons.
    typed=st.chat_input(t('placeholder'),max_chars=1500)

if weather:
    source='<a href="https://open-meteo.com/" target="_blank">Weather data by Open-Meteo.com</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">CC BY 4.0</a>' if weather.source=='open-meteo' else t('weather_scenario')
    st.markdown(f'<div class="status {"unknown" if weather.level!="ok" else ""}">{t("weather_line",temp=f"{weather.temperature_c:+.0f}",feels=f"{weather.feels_like_c:+.0f}",wind=f"{weather.wind_ms:.0f}",level=t("weather_"+weather.level),source=source)}</div>',unsafe_allow_html=True)
elif state.weather=='auto':st.caption(t('weather_unavailable'))

with st.spinner(t('spinner_index')):
    try:engine=get_engine((DATA/'pois.json').stat().st_mtime,(DATA/'pois.faiss').stat().st_mtime if (DATA/'pois.faiss').exists() else 0,id(Engine))
    except Exception:
        st.error(t('error_index'));st.stop()
q=quality((DATA/'quality.json').stat().st_mtime)
backend=engine.retriever.backend
if backend=='lexical':st.caption('⚠ '+t('lexical_warning'))

controls=(state.preset,state.day,state.clock,state.lang,state.mode,state.group,state.accessible,state.max_travel,state.weather,tuple(location),(DATA/'pois.json').stat().st_mtime)
if state.get('answer_controls') and controls!=state.answer_controls and 'pending_query' not in state:
    state.last_answer=None;state.last_debug=None

request=state.pop('pending_query',None) or typed
if request:
    with st.spinner(t('spinner_answer')):
        try:
            answer,debug=engine.answer(request,location,now,language=state.lang,mode=state.mode,group_size=state.group,accessible=state.accessible,max_travel_min=state.max_travel,weather=weather)
            state.last_answer=answer;state.last_debug=debug;state.last_query=request;state.answer_controls=controls;state.answer_seq+=1
        except Exception:
            st.error(t('error_answer'));state.last_answer=None

answer=state.last_answer;debug=state.last_debug
left,right=st.columns([1.12,1],gap='large')
with left,st.container(key='answer'):
    if answer:
        with st.chat_message('user',avatar=':material/person:'):st.write(state.last_query)
        lang=answer.interpretation.language;unit=tl(lang,'min')
        if answer.layover:
            L=answer.layover;clock=lambda s:datetime.fromisoformat(s).strftime('%H:%M')
            st.markdown('#### 🛫 '+html.escape(tl(lang,'layover_title',anchor=place(lang,L.anchor))))
            st.markdown(f'<div class="deadline">{tl(lang,"layover_leave",time=clock(L.leave_city_by))}</div>',unsafe_allow_html=True)
            cells=''.join(f'<div><small>{tl(lang,k)}</small><b>{clock(v)}</b></div>' for k,v in [('lay_city',L.arrive_city),('lay_leave',L.leave_city_by),('lay_airport',L.back_at_airport_by),('lay_departure',L.departure)])
            st.markdown(f'<div class="lay-grid">{cells}</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="warn">⚠ {tl(lang,"layover_visa")}</div><div class="warn">⚠ {tl(lang,"layover_taxi")}</div>',unsafe_allow_html=True)
            notes=[tl(lang,'layover_window',exit=L.exit_min,transfer=L.transfer_min,reserve=L.reserve_min,city=L.city_min)]
            if tr(lang,'layover_assume') in answer.message:notes.insert(0,tr(lang,'layover_assume'))
            st.caption(' '.join(notes))
        elif answer.message:st.info(answer.message)
        if answer.clarifying_question and answer.clarifying_question!=answer.message:st.write(answer.clarifying_question)
        if answer.recommendations:
            st.caption(count_options(lang,len(answer.recommendations))+' · '+tl(lang,'route_below' if answer.route else 'pick_one'))
            st.markdown(f'<div class="legend"><span class="pill">📍 {tl(lang,"poi_data")}</span>{tl(lang,"poi_hint")} &nbsp; <span class="pill">💡 {tl(lang,"idea")}</span>{tl(lang,"idea_hint")}</div>',unsafe_allow_html=True)
        for n,r in enumerate(answer.recommendations,1):
            with st.container(border=True):
                st.markdown(f'<div class="rec-name"><span class="num">{n}</span>{html.escape(r.name)}</div>',unsafe_allow_html=True)
                mode_label=tl(lang,'walking' if answer.interpretation.mode=='walk' else 'by_transport')
                distance_label=tl(lang,'m_straight')+(tl(lang,'from_dropoff') if answer.layover else '')
                st.markdown(f'<div class="rec-meta">{r.distance_m} {distance_label} &nbsp;·&nbsp; ≈ {r.travel_min} {unit} {mode_label}</div>',unsafe_allow_html=True)
                if r.shelter:st.markdown(f'<span class="pill">{tl(lang,r.shelter)}</span>',unsafe_allow_html=True)
                if r.warm_route:
                    w=r.warm_route;a,b=w.outdoor_legs_min
                    st.markdown('<div class="status">'+tl(lang,'warm_route',a=a,b=b,hub=html.escape(w.hub_name),total=w.outdoor_total_min,unit=unit)+'</div>',unsafe_allow_html=True)
                elif r.outdoor_min is not None:st.caption(tl(lang,'outside_min',m=r.outdoor_min))
                st.markdown(f'<div class="rec-body"><b>{tl(lang,"why")}.</b> {html.escape(r.why)}<br><b>{tl(lang,"plan")} · {r.visit_min} {unit}.</b> {html.escape(r.what_to_do)}</div>',unsafe_allow_html=True)
                if r.open_status.state=='open':
                    until=(tl(lang,'until')+datetime.fromisoformat(r.open_status.next_change).strftime('%H:%M')) if r.open_status.next_change else ''
                    status=tl(lang,'open_osm')+until
                else:status=tl(lang,'hours_unconfirmed')
                status+=' · '+tl(lang,'confidence',level=tl(lang,'conf_'+r.open_status.confidence))
                st.markdown(f'<div class="status {"unknown" if r.open_status.state=="unknown" else ""}">{html.escape(status)}</div>',unsafe_allow_html=True)
                with st.expander(tl(lang,'details')):
                    st.write(r.caveats);st.caption(tr(lang,'visit'))
                    st.caption(tl(lang,'used')+', '.join(r.data_used))
                    st.caption(tl(lang,'updated')+r.collected_at[:10]+' · '+r.open_status.basis)
                    st.link_button(tl(lang,'osm_source'),r.source_url)
                    # Explicit click opens an external editor; no reports/coordinates sent automatically.
                    st.link_button(tl(lang,'report_osm'),r.source_url+'?mlat='+str(r.lat)+'&mlon='+str(r.lon))
        if answer.alternative:
            alt=answer.alternative
            st.warning(tl(lang,'alternative',name=alt.name,min=alt.travel_min,constraint=alt.relaxed_constraint,caveat=alt.caveat))
        if answer.route:
            route=answer.route;names={r.poi_id:r.name for r in answer.recommendations}
            st.subheader(tl(lang,'route_title',min=route.total_min))
            for stop in route.stops:st.write(tl(lang,'route_stop',a=f'{stop.arrival_min:02d}',d=f'{stop.departure_min:02d}',name=names[stop.poi_id],t=stop.travel_min))
            st.caption(tl(lang,'route_return',m=route.return_min))
        elif answer.interpretation.route_requested and answer.recommendations:st.info(tl(lang,'route_failed'))
    else:
        st.markdown(t('empty_title'))
        st.write(t('empty_text'))
        st.info(t('empty_info'))
        st.caption(t('empty_caption'))

with right,st.container(key='map_col'):
    st.markdown('### '+t('nearby'))
    st.caption(f'{place(ui_lang,state.preset) if not state.location else t("map_point")} · {now.strftime("%d.%m · %H:%M")} · UTC+5')
    radius=state.max_travel*CONFIG['walk_m_per_min']/CONFIG['detour_factor'] if state.mode=='walk' else max(0,state.max_travel-CONFIG['transport_overhead_min'])*CONFIG['transport_m_per_min']/CONFIG['detour_factor']
    # Without an answer the view shows the whole travel-limit circle; with one, every point of the answer.
    dlat=max(radius,300)/111320;dlon=dlat/math.cos(math.radians(location[0]))
    view=[(location[0]-dlat,location[1]-dlon),(location[0]+dlat,location[1]+dlon)]
    has_points=bool(answer and (answer.recommendations or answer.layover))
    if has_points:
        # A layover walk starts at the drop-off point, not at the airport.
        origin=(answer.layover.anchor_lat,answer.layover.anchor_lon) if answer.layover else location
        view=[origin]+[(r.lat,r.lon) for r in answer.recommendations]+[(r.warm_route.hub_lat,r.warm_route.hub_lon) for r in answer.recommendations if r.warm_route]
        if answer.layover:view.append(tuple(CONFIG['presets']['Аэропорт']))
    south,north=min(p[0] for p in view),max(p[0] for p in view);west,east=min(p[1] for p in view),max(p[1] for p in view)
    m=folium.Map(location=location,zoom_start=14,tiles='OpenStreetMap' if state.tiles else None,control_scale=True)
    folium.CircleMarker(location=location,radius=8,color='#fff',weight=3,fill=True,fill_color='#0d766b',fill_opacity=1,tooltip=t('you_here')).add_to(m)
    if not (answer and answer.layover):folium.Circle(location=location,radius=radius,color='#0d766b',weight=1,fill=True,fill_opacity=.055,dash_array='4,6').add_to(m)
    if not state.tiles:
        if (DATA/'map_context.geojson').exists():
            raw_context=public_map_context()
            context={'type':'FeatureCollection','features':[f for f in raw_context['features'] if any(south-.02<y<north+.02 and west-.035<x<east+.035 for x,y in f['geometry']['coordinates'])]}
            folium.GeoJson(context,style_function=lambda f:{'color':'#91bdc7' if f['properties']['kind']=='river' else '#b7c6b7','weight':7 if f['properties']['kind']=='river' else 2,'opacity':.7},tooltip=folium.GeoJsonTooltip(fields=['name'],labels=False)).add_to(m)
        # Context labels are public presets, rendered locally without tile requests.
        for label,point in CONFIG['presets'].items():
            folium.CircleMarker(point,radius=3,color='#8a9f93',tooltip=place(ui_lang,label)).add_to(m)
        boundary=json.loads((DATA/'boundary.geojson').read_text(encoding='utf-8'))
        folium.GeoJson(boundary,style_function=lambda x:{'fillOpacity':0,'color':'#c9d3c9','weight':1}).add_to(m)
    if has_points:
        if answer.layover:
            airport=CONFIG['presets']['Аэропорт']
            folium.PolyLine([airport,origin],color='#7a8d9c',weight=2,dash_array='2,8',tooltip=t('taxi_tooltip',m=answer.layover.transfer_min)).add_to(m)
            folium.Marker(origin,tooltip=html.escape(t('dropoff',name=place(ui_lang,answer.layover.anchor))),icon=folium.DivIcon(html='<div style="font-size:22px">🛬</div>')).add_to(m)
        used={r.warm_route.hub_id for r in answer.recommendations if r.warm_route}
        if used:
            folium.GeoJson({'type':'FeatureCollection','features':[f for f in hub_shapes()['features'] if f['properties']['id'] in used]},style_function=lambda f:{'color':'#ce824d','fillColor':'#ce824d','fillOpacity':.25,'weight':1},tooltip=folium.GeoJsonTooltip(fields=['name'],labels=False)).add_to(m)
        for n,r in enumerate(answer.recommendations,1):
            folium.Marker([r.lat,r.lon],tooltip=html.escape(r.name),icon=folium.DivIcon(html=f'<div style="background:#0d766b;color:white;border:3px solid white;border-radius:50%;width:30px;height:30px;text-align:center;line-height:24px;font-weight:bold">{n}</div>')).add_to(m)
            if r.warm_route and not answer.route:
                folium.PolyLine([origin,(r.warm_route.hub_lat,r.warm_route.hub_lon),(r.lat,r.lon)],color='#ce824d',weight=3,dash_array='6,6',tooltip=html.escape(t('warm_tooltip',hub=r.warm_route.hub_name))).add_to(m)
        if answer.route:
            byid={r.poi_id:r for r in answer.recommendations}
            pts=[origin]+[(byid[s.poi_id].lat,byid[s.poi_id].lon) for s in answer.route.stops]+[origin]
            folium.PolyLine(pts,color='#d48b53',weight=3,dash_array='8,8',tooltip=t('route_tooltip')).add_to(m)
    m.add_child(FitView([[south,west],[north,east]]))
    height=300 if state.narrow else 460
    clicked=st_folium(m,height=height,width=None,use_container_width=True,returned_objects=['last_clicked'],key=f'map_{location}_{height}')
    if clicked and clicked.get('last_clicked'):
        point=round_location(clicked['last_clicked']['lat'],clicked['last_clicked']['lng'])
        if tuple(point)!=tuple(location):state.location=point;state.last_answer=None;st.rerun()
    st.caption(t('map_caption'))

with st.expander(t('how'),expanded=False):
    st.write('**'+t('data_mode')+'**')
    st.caption(t('data_line',count=f'{q["count"]:,}'.replace(',',' '),gold=q['gold_reviewed'],backend=backend,date=q['collected_at'][:10]))
    if os.getenv('LLM_PROVIDER','none')!='gemini':st.caption(t('local_mode',kind=t('semantic' if backend=='e5+lexical' else 'lexical')))
    if backend=='lexical':st.caption(t('rebuild_index'))
    st.caption(t('demo_time'))
    if not answer:st.write(t('how_empty'))
    else:
        st.caption(t('elapsed',s=f'{debug.get("elapsed_ms",0)/1000:.2f}'))
        if answer.layover and answer.message:st.write('**'+t('layover_full')+'**');st.write(answer.message)
        st.write('**'+t('parse')+'**');st.json(answer.interpretation.model_dump())
        st.write(t('pois_total',total=debug['total_pois'],accepted=debug.get('accepted',0)))
        if debug.get('cache_hit'):st.info(t('cache_hit'))
        reason=lambda k:t('reason_'+k,time=now.strftime('%H:%M')) if 'ui_reason_'+k in TEXT[ui_lang] else k
        st.write('**'+t('reasons')+'**');st.json({reason(k):v for k,v in debug.get('rejected_counts',{}).items()})
        if debug.get('candidates'):st.dataframe([{t('col_place'):c['name'],t('col_category'):c['category'],t('col_score'):c['score'],t('col_travel'):c['travel_min'],t('col_status'):c['open_status']['state'],t('col_shelter'):c.get('shelter'),t('col_outdoor'):c.get('outdoor_min'),t('col_hub'):c.get('warm_hub')} for c in debug['candidates']],hide_index=True)
        if debug.get('layover_windows'):st.write('**'+t('layover_windows')+'**');st.dataframe([{t('col_anchor'):place(ui_lang,w['anchor']),t('col_taxi'):w['transfer_min'],t('col_city'):w['city_min'],t('col_arrive'):w['arrive_city'][11:16],t('col_leave'):w['leave_city_by'][11:16]} for w in debug['layover_windows']],hide_index=True)
        if debug.get('rejections'):st.dataframe([{t('col_place'):r['name'],t('col_reason'):reason(r['reason']),t('col_travel'):r['travel_min']} for r in debug['rejections']],hide_index=True)
        st.caption(t('score_caption'))
        st.write('**'+t('tech_check')+'**');st.json(debug.get('generation',{}))
        st.download_button(t('download'),answer.model_dump_json(indent=2),file_name='recommendation.json',mime='application/json',help=t('download_help'))

st.divider()
st.caption(t('footer'))
viewport(key='qala_scroll',data={'mode':'scroll','token':state.answer_seq if answer else 0})
