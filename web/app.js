import {translations,presetNames} from './i18n.js?v=query-block';

const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={lang:'ru',page:'walk',view:'route',result:null,history:[],location:null,presets:[],scenarios:[],busy:false,sequence:0,publicCache:new Map(),map:null,mapLayer:null,customPoint:false,startedAt:Date.now(),savedResult:false,lastQuery:'',lastScenario:null};
const t=key=>translations[state.lang][key]??translations.ru[key]??key;
const hhmm=iso=>iso?String(iso).slice(11,16):'';
const clock=minutes=>`${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`;
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Almaty',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const nowISO=()=>`${$('demo-date').value}T${clock(Number($('demo-time').value))}:00+05:00`;
const localISO=epoch=>new Date(epoch+5*3600000).toISOString().slice(0,19)+'+05:00';
const rounded=point=>[Math.round(point[0]*1000)/1000,Math.round(point[1]*500)/500];
const returnIcon='<svg viewBox="0 0 28 28" aria-hidden="true"><path d="m10 4-6 6 6 6M4 10h12a7 7 0 0 1 0 14h-4"/></svg>';

function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>$('toast').hidden=true,4500);}
function notice(message){$('notice').textContent=message;$('notice').hidden=!message;}
function setLanguage(lang){
  state.lang=lang;document.documentElement.lang=lang;
  document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n));
  document.querySelectorAll('[data-i18n-aria]').forEach(el=>el.setAttribute('aria-label',t(el.dataset.i18nAria)));
  for(const id of ['duration','transfer'])for(const opt of $(id).options)opt.textContent=`${opt.value} ${t('minutes')}`;
  for(const opt of $('start').options)opt.textContent=opt.value==='map'?t('myPoint'):(presetNames[lang][opt.value]||opt.value);
  $('query').placeholder=t(state.page==='layover'?'layoverPlaceholder':state.result?.answer.interpretation.constraints.includes('children')?'childPlaceholder':'placeholder');
  $('planner').setAttribute('aria-label',t('apply'));
  document.querySelector('.segments').setAttribute('aria-label',t('route'));
  $('map').setAttribute('aria-label',t('map'));
  $('loading').setAttribute('aria-label',t('loading'));
  render();renderSaved();renderDeadline();updateDataStatus();
}

function example(){
  return `<p class="eyebrow">${esc(t('exampleLabel'))}</p><h1 class="route-title">${esc(t('sampleTitle'))}</h1><div class="route-meta">${t('sampleMeta').map(x=>`<span>${esc(x)}</span>`).join('')}</div><ol class="stops">${t('sampleNames').map((name,n)=>`<li class="stop"><button class="stop-toggle" data-example="${n}" aria-expanded="false" aria-controls="example-${n}"><span class="stop-number">${n+1}</span><span class="stop-name">${esc(name)}</span><span class="stop-role">${esc(t('sampleRoles')[n])}</span></button><div class="stop-details" id="example-${n}" hidden>${esc(t('sampleHint'))}</div></li>`).join('')}</ol>`;
}

function statusText(rec){
  const s=rec.open_status;
  return s.state==='open'&&s.confidence==='high'?`${t('open')}${s.next_change?' '+t('until')+' '+hhmm(s.next_change):''} · ${t('confidence')} ${t(s.confidence)}`:`${t('unknownHours')} · ${t('confidence')} ${t(s.confidence)}`;
}
function safeSource(url){try{const u=new URL(url);return u.protocol==='https:'&&u.hostname==='www.openstreetmap.org'?u.href:'#';}catch{return '#';}}
function recHTML(rec,index,prefix='stop'){
  const role=t('category')[rec.category]||t('walk');
  return `<li class="stop"><button class="stop-toggle" data-stop="${index}" aria-expanded="false" aria-controls="${prefix}-${index}"><span class="stop-number">${index+1}</span><span class="stop-name">${esc(rec.name)}</span><span class="stop-role">${esc(role)}</span></button>
  <div class="stop-details" id="${prefix}-${index}" hidden><p>${rec.distance_m} ${t('m')} · ≈ ${rec.travel_min} ${t('minute')} ${t('estimatedWalk')}</p><div class="badges"><span class="badge">${t('poiBadge')}</span><span class="badge">${t('ideaBadge')}</span></div>
  <h3>${t('why')}</h3><p class="line-clamp">${esc(rec.why)}</p><h3>${t('plan')} · ${rec.visit_min} ${t('minute')}</h3><p class="line-clamp">${esc(rec.what_to_do)}</p><p class="${rec.open_status.state==='open'?'open-status':'unknown-status'}">${esc(statusText(rec))}</p>
  <details><summary>${t('caveats')}</summary><p>${esc(rec.caveats)}</p><p>${t('used')}: ${esc(rec.data_used.join(', '))}</p><p>${t('updated')}: ${esc(rec.collected_at.slice(0,10))}</p><a href="${esc(safeSource(rec.source_url))}" target="_blank" rel="noopener noreferrer">${t('source')} ↗</a></details>
  <div class="stop-actions"><button data-save-stop="${esc(rec.poi_id)}">${t('save')}</button><button data-report="${esc(rec.poi_id)}">${t('report')}</button></div></div></li>`;
}
function orderedRecs(){const a=state.result?.answer;if(!a)return [];return a.route?a.route.stops.map(s=>a.recommendations.find(r=>r.poi_id===s.poi_id)).filter(Boolean):a.recommendations;}
function distanceText(m){return m>=1000?`${(m/1000).toLocaleString(state.lang==='kk'?'kk-KZ':state.lang,{maximumFractionDigits:1})} ${t('km')}`:`${m} ${t('m')}`;}

function render(){
  if(state.page==='saved')return;
  $('route-view').hidden=state.view!=='route'||state.busy;$('map-view').hidden=state.view!=='map'||state.busy;
  $('save-route').hidden=!state.result?.answer.recommendations.length||state.savedResult;
  if(!state.result){$('route-view').innerHTML=example();$('disclaimer').textContent=t('disclaimer');return;}
  const {answer:a,presentation:p}=state.result,recs=orderedRecs();
  let body=`<p class="eyebrow">${esc(t('answerLabel'))}</p><h1 class="route-title">${esc(p.title)}</h1>`;
  if(recs.length){
    body+=`<div class="route-meta"><span>≈ ${distanceText(p.distance_m)}</span><span>${recs.length} ${t(recs.length===1?'oneStop':'stops')}</span><span>${t('upTo')} ${p.total_min} ${t('minute')}</span></div><ol class="stops">${recs.map((r,n)=>recHTML(r,n)).join('')}</ol>`;
    body+=`<div class="return-row">${returnIcon}<span>${t('returnToStart')} · ${p.return_min} ${t('minute')}</span></div>`;
    if(a.layover)body+=`<p class="small-text">${esc(presetNames[state.lang][a.layover.anchor]||a.layover.anchor)} · ${t('transferBack')}: ${a.layover.transfer_min} ${t('minute')}. ${t('reserve')}: ${a.layover.reserve_min} ${t('minute')}.</p>`;
    if(a.weather)body+=`<p class="small-text">${t('weather')}: ${a.weather.feels_like_c} °C · ${esc(a.weather.source==='manual'?t('weatherFrost').split(' · ')[1]||'demo':'Open-Meteo')}</p>`;
  }else{
    body+=`<p class="response-message">${esc(a.clarifying_question||a.message||t('emptyMessage'))}</p>`;
    if(a.alternative)body+=`<p class="small-text">${t('alternative')}: ${esc(a.alternative.name)} · ${a.alternative.travel_min} ${t('minute')}. ${esc(a.alternative.relaxed_constraint)}. ${esc(a.alternative.caveat)}</p>`;
    body+=`<div class="suggestions"><button data-suggest="${state.page==='layover'?'layover':'walk'}">${t(state.page==='layover'?'longLayover':'newWalk')}</button><button data-suggest="retry">${t('retry')}</button></div>`;
  }
  $('route-view').innerHTML=body;
  $('disclaimer').textContent=recs.some(r=>r.open_status.state==='unknown'||r.open_status.confidence==='low')?t('unknownDisclaimer'):t('disclaimer');
  $('query').placeholder=t(state.page==='layover'?'layoverPlaceholder':a.interpretation.constraints.includes('children')?'childPlaceholder':'placeholder');
  if(state.view==='map')renderMap();
}

function setBusy(busy){state.busy=busy;$('apply').disabled=busy;document.querySelector('.send-button').disabled=busy;$('loading').hidden=!busy;$('planner').setAttribute('aria-busy',String(busy));$('query-block').setAttribute('aria-busy',String(busy));render();}
function setView(view){state.view=view;for(const name of ['route','map'])$(name+'-tab').setAttribute('aria-selected',String(name===view));render();if(view==='map')renderMap();}
function switchPage(page,keep=false){
  if(state.page!==page){++state.sequence;state.controller?.abort();setBusy(false);}
  if(state.page!==page&&!keep){state.result=null;state.history=[];state.lastQuery='';state.lastScenario=null;state.savedResult=false;notice('');}
  state.page=page;
  for(const button of document.querySelectorAll('[data-page]')){if(button.dataset.page===page)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');}
  $('planner').hidden=page==='saved';$('saved-view').hidden=page!=='saved';$('walk-controls').hidden=page==='layover';$('layover-controls').hidden=page!=='layover';
  $('query').placeholder=t(page==='layover'?'layoverPlaceholder':'placeholder');
  render();renderSaved();renderDeadline();
}
function departureISO(){let at=new Date(`${$('demo-date').value}T${$('departure').value}:00+05:00`).getTime();if(at<=new Date(nowISO()).getTime())at+=86400000;return localISO(at);}
function payload(query,scenario=null){
  return {query,preset:$('start').value==='map'?null:$('start').value,location:$('start').value==='map'?state.location:null,now:nowISO(),duration_min:Number($('duration').value),language:state.lang,group_size:Number($('group').value),accessible:$('accessible').checked,demo_cache:$('demo-cache').checked,weather:$('weather').value,history:state.history.slice(-6),scenario_id:scenario,departure_at:state.page==='layover'?departureISO():null,airport_transfer_min:Number($('transfer').value)};
}

async function request(query,scenario=null){
  if(state.page==='saved')switchPage('walk');
  const body=payload(query,scenario),key=JSON.stringify(body),token=++state.sequence;
  state.controller?.abort();const controller=new AbortController();state.controller=controller;
  const timer=setTimeout(()=>controller.abort(),16000);notice('');setBusy(true);
  try{
    const response=await fetch('/api/recommend?details=true',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
    if(!response.ok)throw new Error(response.status===422?'invalid':'networkError');
    const result=await response.json();if(token!==state.sequence)return;
    state.result=result;state.savedResult=false;state.startedAt=Date.now();state.lastQuery=query;state.lastScenario=scenario;
    state.history.push(query);state.history=state.history.slice(-6);
    if(scenario)state.publicCache.set(key,result);
    if(result.debug.cache_hit)notice(t('cached'));
    if(result.debug.weather_warning)notice(result.debug.weather_warning);
    if(result.answer.layover)state.location=result.presentation.origin;
  }catch(error){
    if(token!==state.sequence)return;
    if(scenario&&state.publicCache.has(key)){state.result=state.publicCache.get(key);notice(t('cached'));}
    else{notice(t(error.message==='invalid'?'invalid':'networkError'));state.result=null;}
  }finally{clearTimeout(timer);if(token===state.sequence){setBusy(false);renderDeadline();}}
}

async function quickScenario(index){
  if(!state.scenarios[index]){notice(t('offlineData'));return;}
  const c=state.scenarios[index];switchPage('walk');state.history=[];state.result=null;state.lastScenario=c.id;state.customPoint=false;state.location=null;
  $('start').value=c.preset;$('duration').value='60';$('demo-date').value=c.now.slice(0,10);$('demo-time').value=Number(c.now.slice(11,13))*60+Number(c.now.slice(14,16));$('time-output').textContent=hhmm(c.now);$('group').value='1';$('accessible').checked=false;$('weather').value='off';
  if(index===3){switchPage('layover');$('departure').value=hhmm(localISO(new Date(c.now).getTime()+120*60000));$('transfer').value='45';}
  setView('route');await request(c.query,c.id);
}
async function longLayover(){
  switchPage('layover');state.history=[];$('demo-date').value=today();$('demo-time').value='600';$('time-output').textContent='10:00';$('departure').value='18:00';$('transfer').value='45';$('weather').value='off';$('start').value='Аэропорт';
  await request({ru:'Что посмотреть в городе?',en:'What can I see in the city?',kk:'Қалада не көруге болады?'}[state.lang]);
}

function renderDeadline(){
  const banner=$('deadline-banner');banner.hidden=state.page!=='layover'&&!state.result?.presentation.deadline;
  if(banner.hidden)return;
  const p=state.result?.presentation,plan=state.result?.answer.layover;
  const deadline=p?.deadline||localISO(new Date(departureISO()).getTime()-(120+Number($('transfer').value))*60000);
  const base=p?.now||nowISO(),elapsed=p?Date.now()-state.startedAt:0;
  const left=Math.max(0,Math.floor((new Date(deadline).getTime()-new Date(base).getTime()-elapsed)/1000));
  const remaining=`${String(Math.floor(left/3600)).padStart(2,'0')}:${String(Math.floor(left%3600/60)).padStart(2,'0')}:${String(left%60).padStart(2,'0')}`;
  banner.classList.toggle('expired',left===0);
  banner.innerHTML=`<strong>${t('returnBy')} ${hhmm(deadline)}</strong><span>${left?`${t('timeLeft')} <b>${remaining}</b>`:t('expired')}</span>${!state.result?`<br><span>${t('draftDeadline')}</span>`:''}`;
}

async function renderMap(){
  if(state.view!=='map'||state.page==='saved'||state.busy)return;
  $('map-view').hidden=false;
  if(!window.L){notice(t('mapUnavailable'));return;}
  const origin=state.savedResult?null:state.result?.presentation.origin||($('start').value==='map'?state.location:state.presets.find(p=>p.id===$('start').value)?.location)||[51.128,71.43];
  if(!state.map){
    state.map=L.map('map',{zoomControl:true,scrollWheelZoom:false}).setView(origin||[51.128,71.43],14);
    // CARTO's raster endpoint returned "API KEY REQUIRED" tiles during QA.
    // The checked-in OSM street/river snapshot is an honest offline dark basemap.
    state.map.attributionControl.addAttribution('© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>');
    state.map.createPane('context');state.map.getPane('context').style.zIndex=200;state.map.getPane('context').setAttribute('aria-hidden','true');
    state.mapLayer=L.layerGroup().addTo(state.map);
    state.map.on('click',event=>{state.location=rounded([event.latlng.lat,event.latlng.lng]);state.customPoint=true;$('start').value='map';state.result=null;state.history=[];notice(t('pointSelected'));renderMap();});
    try{const response=await fetch('/api/map-context');if(!response.ok)throw new Error();const geo=await response.json();L.geoJSON(geo,{pane:'context',style:f=>({color:f.properties?.kind==='river'?'#305364':'#43535b',weight:f.properties?.kind==='river'?9:2,opacity:.8}),onEachFeature:(f,layer)=>{if(f.properties?.name)layer.bindTooltip(document.createTextNode(f.properties.name),{sticky:true});}}).addTo(state.map);}catch{$('tile-warning').hidden=false;}
  }
  state.map.invalidateSize();state.mapLayer.clearLayers();
  const recs=orderedRecs(),points=[];
  if(origin){points.push(origin);L.circleMarker(origin,{radius:7,color:'#e6f0f2',weight:2,fillColor:'#cde88a',fillOpacity:1}).bindTooltip(t('selectedPoint')).addTo(state.mapLayer);L.circle(origin,{radius:state.result?.presentation.radius_m||1230,color:'#cde88a',weight:1,dashArray:'4 6',fillOpacity:.035}).addTo(state.mapLayer);}
  recs.forEach((r,n)=>{const p=[r.lat,r.lon];points.push(p);L.marker(p,{icon:L.divIcon({className:'',html:`<span class="map-marker">${n+1}</span>`,iconSize:[32,32],iconAnchor:[16,16]})}).bindPopup(document.createTextNode(r.name)).addTo(state.mapLayer);});
  if(origin&&recs.length)points.push(origin);
  if(points.length>1){L.polyline(points,{color:'#cde88a',weight:3,opacity:.8,dashArray:'5 5'}).addTo(state.mapLayer);state.map.fitBounds(points,{padding:[42,42],maxZoom:15});}
  else if(origin)state.map.setView(origin,14);
}

function savedItems(){try{const parsed=JSON.parse(localStorage.getItem('qala:saved:v1')||'[]');return Array.isArray(parsed)?parsed.slice(0,30):[];}catch{return [];}}
function writeSaved(items){try{localStorage.setItem('qala:saved:v1',JSON.stringify(items.slice(0,30)));toast(t('savedToast'));return true;}catch{toast(t('saveFailed'));return false;}}
function saveItem(poiId=null){
  if(!state.result)return;
  const recs=poiId?state.result.answer.recommendations.filter(r=>r.poi_id===poiId):orderedRecs();if(!recs.length)return;
  // Persist only explicitly saved public POI data. Never store origin, query, history, debug or deadline.
  const item={id:poiId||'route:'+recs.map(r=>r.poi_id).join('|'),kind:poiId?'place':'route',title:poiId?recs[0].name:state.result.presentation.title,recommendations:recs};
  writeSaved([item,...savedItems().filter(x=>x.id!==item.id)]);
}
function renderSaved(){
  const items=savedItems();
  if(!items.length){$('saved-view').innerHTML=`<div class="saved-empty"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M6 3h16v23l-8-7-8 7z"/></svg><h1>${t('savedEmpty')}</h1><p>${t('savedHint')}</p><button class="outline-button" data-suggest="walk">${t('newWalk')}</button></div>`;return;}
  $('saved-view').innerHTML=`<h1 class="saved-heading">${t('savedTitle')}</h1><p class="small-text">${t('savedLocal')}</p>${items.map((item,n)=>`<article class="saved-item"><h3>${esc(item.title)}</h3><p>${(item.recommendations||[]).map(r=>esc(r.name)).join(' · ')}</p><button class="outline-button" data-saved-show="${n}">${t('view')}</button><button class="outline-button" data-saved-remove="${n}">${t('remove')}</button><div id="saved-detail-${n}" hidden><ol class="stops">${(item.recommendations||[]).map((r,i)=>recHTML(r,i,'saved-'+n)).join('')}</ol></div></article>`).join('')}`;
}

function showRAG(){
  const d=state.result?.debug,a=state.result?.answer;
  if(!d||!a){$('rag-content').textContent=t('noAnswer');$('rag-dialog').showModal();return;}
  const i=a.interpretation,reason=code=>t('reasonCodes')[code]||code;
  const interpreted={[t('budget')]:`${i.duration_min} ${t('minute')}`,[t('tags')]:i.tags,[t('restrictions')]:i.constraints,[t('assumptions')]:i.assumptions};
  $('rag-content').innerHTML=`<h3>${t('constraints')}</h3><pre>${esc(JSON.stringify(interpreted,null,2))}</pre><h3>${t('pipeline')}</h3><p>${t('total')}: ${d.total_pois??'—'} · ${t('accepted')}: ${d.accepted??0}<br>${esc(d.retrieval_backend||a.retrieval_backend)} · ${d.elapsed_ms??0} ms</p><p>${t('generation')}: ${esc(t(a.generation_backend))}<br>${t('titleSource')}: ${esc(t(state.result.presentation.title_source))}<br>${t('history')}: ${d.history_turns||0}</p>
  <h3>${t('candidates')}</h3><table><thead><tr><th>${t('place')}</th><th>${t('score')}</th></tr></thead><tbody>${(d.candidates||[]).map(c=>`<tr><td>${esc(c.name)}<br><small>${c.travel_min} ${t('minute')} · ${esc(t('category')[c.category]||c.category)}</small></td><td>${c.score}</td></tr>`).join('')}</tbody></table>
  <h3>${t('rejections')}</h3><p>${Object.entries(d.rejected_counts||{}).map(([k,v])=>`${esc(reason(k))}: ${v}`).join(' · ')}</p><table>${(d.rejections||[]).slice(0,15).map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(reason(r.reason))}</td></tr>`).join('')}</table><h3>${t('dataUsed')}</h3><p>${esc([...new Set(a.recommendations.flatMap(r=>r.data_used))].join(' · ')||t('now'))}</p>${a.message?`<p>${esc(a.message)}</p>`:''}${d.weather_warning?`<p>${esc(d.weather_warning)}</p>`:''}`;
  $('rag-dialog').showModal();
}
async function report(poiId){try{const response=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({poi_id:poiId,reason:'other'})});if(!response.ok)throw new Error();toast(t('feedback'));}catch{toast(t('networkError'));}}
function updateDataStatus(){if(state.quality)$('data-status').textContent=`${state.quality.count.toLocaleString(state.lang)} ${t('total')} · OSM · ${state.quality.collected_at.slice(0,10)} · E5 / FAISS`;}

document.addEventListener('click',event=>{
  const el=event.target.closest('button');if(!el)return;
  if(el.dataset.view)setView(el.dataset.view);
  if(el.dataset.page)switchPage(el.dataset.page);
  if(el.dataset.scenario!==undefined)quickScenario(Number(el.dataset.scenario));
  if(el.dataset.stop!==undefined||el.dataset.example!==undefined){const panel=$(el.getAttribute('aria-controls'));panel.hidden=!panel.hidden;el.setAttribute('aria-expanded',String(!panel.hidden));}
  if(el.dataset.saveStop)saveItem(el.dataset.saveStop);
  if(el.dataset.report)report(el.dataset.report);
  if(el.dataset.savedRemove!==undefined){const items=savedItems();items.splice(Number(el.dataset.savedRemove),1);writeSaved(items);renderSaved();toast(t('removed'));}
  if(el.dataset.savedShow!==undefined){const panel=$('saved-detail-'+el.dataset.savedShow);panel.hidden=!panel.hidden;}
  if(el.dataset.suggest==='layover')longLayover();
  if(el.dataset.suggest==='walk')quickScenario(0);
  if(el.dataset.suggest==='retry')request(state.lastQuery||t('walk'),state.lastScenario);
});
$('parameters').addEventListener('submit',event=>{event.preventDefault();request(state.lastQuery||t('walk'));});
$('chat-form').addEventListener('submit',event=>{event.preventDefault();const query=$('query').value.trim();if(query){$('query').value='';request(query);}});
$('language').addEventListener('change',()=>{const hadResult=!!state.result;setLanguage($('language').value);if(hadResult&&state.page!=='saved'){state.history=[];request(state.lastQuery||t('walk'));}});
$('demo-time').addEventListener('input',()=>{$('time-output').textContent=clock(Number($('demo-time').value));renderDeadline();});
for(const id of ['demo-date','demo-time','group','weather','accessible','demo-cache','start','duration','departure','transfer'])$(id).addEventListener('change',()=>{if(id==='start'){state.location=null;state.customPoint=false;if($('start').value==='map'){setView('map');notice(t('pickPoint'));return;}}notice(t('dirty'));renderDeadline();});
$('clear-session').addEventListener('click',()=>{++state.sequence;state.controller?.abort();state.history=[];state.result=null;state.location=null;state.lastQuery='';state.lastScenario=null;$('query').value='';setBusy(false);render();toast(t('cleared'));});
$('long-layover').addEventListener('click',longLayover);
$('info-button').addEventListener('click',showRAG);$('rag-link').addEventListener('click',showRAG);$('close-rag').addEventListener('click',()=>$('rag-dialog').close());
$('rag-dialog').addEventListener('click',event=>{if(event.target===$('rag-dialog'))$('rag-dialog').close();});
$('save-route').addEventListener('click',()=>saveItem());
document.querySelector('.segments').addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();setView(state.view==='route'?'map':'route');$(state.view+'-tab').focus();}});
setInterval(renderDeadline,1000);
$('demo-date').value=today();$('jury-panel').open=window.matchMedia('(min-width:900px)').matches;
setLanguage('ru');
try{const response=await fetch('/api/presets');if(!response.ok)throw new Error();const data=await response.json();state.presets=data.presets;state.scenarios=data.scenarios;state.quality=data.quality;$('demo-cache').checked=data.demo_cache;updateDataStatus();}catch{notice(t('offlineData'));}
