from __future__ import annotations
import json
import os
import requests
from pydantic import BaseModel
from core.settings import ROOT

class LLMUnavailable(RuntimeError): pass

def enabled():
    return os.getenv('LLM_PROVIDER','none')=='gemini' and bool(os.getenv('GEMINI_API_KEY'))

def structured(system: str, payload: dict, schema: type[BaseModel]):
    if not enabled(): raise LLMUnavailable('No configured Gemini key')
    model=os.getenv('GEMINI_MODEL','gemini-2.5-flash')
    if not all(c.isalnum() or c in '-._' for c in model): raise LLMUnavailable('Invalid model name')
    # Key in header, never URL/logs. No user coordinates are included by callers.
    try:
        r=requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',headers={'x-goog-api-key':os.environ['GEMINI_API_KEY'],'Content-Type':'application/json'},json={'systemInstruction':{'parts':[{'text':system}]},'contents':[{'role':'user','parts':[{'text':json.dumps(payload,ensure_ascii=False)}]}],'generationConfig':{'temperature':0.1,'responseMimeType':'application/json','responseJsonSchema':schema.model_json_schema()}},timeout=(min(2,float(os.getenv('LLM_TIMEOUT_SEC','3'))),float(os.getenv('LLM_TIMEOUT_SEC','3'))))
        r.raise_for_status()
        parts=r.json()['candidates'][0]['content']['parts']
        raw=''.join(p.get('text','') for p in parts if not p.get('thought'))
        return schema.model_validate_json(raw)
    except (requests.RequestException,ValueError,KeyError,IndexError) as exc:
        # Do not leak requests, URLs containing secrets, model responses or user queries.
        raise LLMUnavailable(type(exc).__name__) from None
