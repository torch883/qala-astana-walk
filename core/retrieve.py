from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
import faiss
from sklearn.feature_extraction.text import TfidfVectorizer
from core.settings import DATA
from core.security import safe_text

MODEL_NAME='intfloat/multilingual-e5-small'
RUNTIME_MODEL='qala/multilingual-e5-small-int8'

def load_pois():return json.loads((DATA/'pois.json').read_text(encoding='utf-8'))

def document(p):
    # Raw untrusted instructions never reach the embedding model or generator.
    return ' '.join([safe_text(p['name']),p['category'],' '.join(p.get('search_tags',[])),safe_text(p.get('description','')),safe_text(p.get('review_description',''))])

def fingerprint(pois):
    content=json.dumps([(p['id'],document(p),p.get('opening_hours')) for p in pois],ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()

def load_model(local_only=True):
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource,PoolingType
    if RUNTIME_MODEL not in [m['model'] for m in TextEmbedding.list_supported_models()]:
        TextEmbedding.add_custom_model(model=RUNTIME_MODEL,pooling=PoolingType.MEAN,normalization=True,sources=ModelSource(hf=MODEL_NAME),dim=384,model_file='model.onnx',size_in_gb=0.12)
    path=Path(os.getenv('MODEL_CACHE_DIR',str(DATA/'models/e5-small')))
    if path.exists() and (path/'model.onnx').exists():
        return TextEmbedding(model_name=RUNTIME_MODEL,specific_model_path=str(path),threads=2)
    if local_only:raise FileNotFoundError('Run python -m core.retrieve --build to download E5')
    from data.download_model import download
    download(path)
    return TextEmbedding(model_name=RUNTIME_MODEL,specific_model_path=str(path),threads=2)

def vectors(model,texts):
    v=np.asarray(list(model.embed(texts,batch_size=32)),dtype='float32')
    faiss.normalize_L2(v)
    return v

def build_index():
    pois=load_pois(); print(f'Loading local E5 for {len(pois)} POIs...',flush=True);model=load_model(local_only=False)
    print('E5 loaded; encoding passages...',flush=True)
    chunks=[]
    for start in range(0,len(pois),256):
        chunks.append(vectors(model,['passage: '+document(p) for p in pois[start:start+256]]))
        print(f'Encoded {min(start+256,len(pois))}/{len(pois)}',flush=True)
    emb=np.concatenate(chunks)
    index=faiss.IndexFlatIP(emb.shape[1]);index.add(emb)
    faiss.write_index(index,str(DATA/'pois.faiss'))
    (DATA/'index.json').write_text(json.dumps({'model':MODEL_NAME,'fingerprint':fingerprint(pois),'ids':[p['id'] for p in pois],'count':len(pois),'dimension':emb.shape[1]}),encoding='utf-8')
    print(f'Built FAISS: {len(pois)} x {emb.shape[1]}')

class Retriever:
    def __init__(self,pois=None,backend=None):
        self.pois=pois if pois is not None else load_pois()
        self.backend='lexical';self.model=None;self.index=None
        self.warning=''
        self.vectorizer=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),max_features=40000)
        self.lexical=self.vectorizer.fit_transform(document(p) for p in self.pois)
        if (backend or os.getenv('EMBEDDING_BACKEND','e5'))=='e5' and (DATA/'index.json').exists():
            try:
                meta=json.loads((DATA/'index.json').read_text(encoding='utf-8'))
                if meta['fingerprint']!=fingerprint(self.pois):raise ValueError('stale_index')
                self.index=faiss.read_index(str(DATA/'pois.faiss'))
                self.model=load_model(local_only=True)
                self.backend='e5+lexical'
                # Warm-up: runtime initialization is outside the interactive response budget.
                vectors(self.model,['query: прогулка'])
            except Exception as exc:
                self.warning='Semantic model unavailable ('+type(exc).__name__+'); lexical fallback active.'
        else:
            self.warning='Lexical fallback: E5 index is unavailable or explicitly disabled.'

    def scores(self,query,categories):
        expanded=query+' '+' '.join(categories)
        lex=np.asarray((self.lexical@self.vectorizer.transform([expanded]).T).toarray()).ravel()
        if self.backend=='e5+lexical':
            q=vectors(self.model,['query: '+safe_text(query,1200)])
            scores,ids=self.index.search(q,len(self.pois))
            sem=np.zeros(len(self.pois))
            sem[ids[0]]=scores[0]
            combined=.8*sem+.2*lex
        else:combined=lex
        return {p['id']:float(s) for p,s in zip(self.pois,combined)}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--build',action='store_true');args=ap.parse_args()
    if args.build:build_index()
