"""Disk cache accepts only fixed public scenarios; live coordinates/queries never written."""
import hashlib,json,os
from core.settings import DATA
from core.schemas import Answer
from core.retrieve import fingerprint

def data_fingerprint(pois):
    # Cache validity covers all facts, including coordinates, facilities and collection date.
    return hashlib.sha256(json.dumps(pois,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def signature(query,location,now,intent):
    return hashlib.sha256(json.dumps([query,list(location),now.isoformat(),intent.model_dump(exclude={'parser','assumptions'})],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def load_demo(query,location,now,intent,pois,enabled=None):
    if not (os.getenv('DEMO_CACHE','0')=='1' if enabled is None else enabled):return None
    path=DATA/'demo_cache.json'
    if not path.exists():return None
    try:
        d=json.loads(path.read_text(encoding='utf-8'))
        if d['fingerprint']!=data_fingerprint(pois):return None
        answer=d['responses'].get(signature(query,location,now,intent))
        if answer:
            result=Answer.model_validate(answer);result.generation_backend='demo_cache';return result
    except (ValueError,KeyError):pass
    return None
