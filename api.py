"""Same-origin FastAPI shell around the existing QALA engine; no session storage."""
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from threading import Lock
from typing import Literal
import json, os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from core.engine import Engine
from core.schemas import Answer, Strict
from core.settings import ROOT, DATA, CONFIG
from core.hours import TZ
from core import llm
from eval.run_eval import scenarios
from ui_service import RecommendRequest, UIResponse, recommend

PUBLIC_SCENARIOS=scenarios()[:5]

@asynccontextmanager
async def lifespan(app):
    app.state.engine=Engine()
    app.state.feedback=Counter()
    app.state.feedback_lock=Lock()
    yield

app=FastAPI(title='QALA',version='0.2.0',lifespan=lifespan)

@app.middleware('http')
async def privacy_headers(request,call_next):
    response=await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request,error):
    # Do not echo locations or query contents in error bodies/logs.
    return JSONResponse(status_code=422,content={'detail':'invalid_request','fields':['.'.join(str(p) for p in e['loc']) for e in error.errors()]})

def runtime_status(engine):
    return {'ready':True,'poi_count':len(engine.pois),
            'retrieval_backend':engine.retriever.backend,'retrieval_warning':engine.retriever.warning,
            'generation_mode':'gemini_configured' if llm.enabled() else 'local_templates'}

@app.get('/api/health')
def health(request:Request):
    return runtime_status(request.app.state.engine)

@app.get('/api/presets')
def presets(request:Request):
    return {'presets':[{'id':name,'location':value} for name,value in CONFIG['presets'].items()],
            'scenarios':[{k:c[k] for k in ['id','query','preset','now','language']} for c in PUBLIC_SCENARIOS],
            'now':datetime.now(TZ).isoformat(),'quality':json.loads((DATA/'quality.json').read_text(encoding='utf-8')),
            'airport_reserve_min':CONFIG['layover']['return_reserve_min'],'demo_cache':os.getenv('DEMO_CACHE','0')=='1',
            'runtime':runtime_status(request.app.state.engine)}

@app.post('/api/recommend',response_model=Answer|UIResponse)
def recommendations(body:RecommendRequest,request:Request,details:bool=False):
    try:result=recommend(body,request.app.state.engine,PUBLIC_SCENARIOS)
    except (ValueError,TypeError):raise HTTPException(422,detail='invalid_request') from None
    except Exception:raise HTTPException(503,detail='temporarily_unavailable') from None
    # Default remains the original Pydantic Answer. The SPA explicitly opts into presentation/debug.
    return result if details else result.answer

class Feedback(Strict):
    poi_id:str=Field(max_length=80)
    reason:Literal['hours','location','accessibility','other']='other'

@app.post('/api/feedback')
def feedback(body:Feedback,request:Request):
    poi=request.app.state.engine.by_id.get(body.poi_id)
    if not poi:raise HTTPException(404,detail='unknown_poi')
    # Anonymous aggregate only: no free-text, location, identifier or persistent log.
    with request.app.state.feedback_lock:request.app.state.feedback[body.reason]+=1
    return {'accepted':True,'persisted':False,'source_url':poi['source']}

@app.get('/api/map-context')
def map_context():
    return FileResponse(DATA/'map_context.geojson',media_type='application/geo+json')

app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='frontend')
