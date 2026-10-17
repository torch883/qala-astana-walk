"""Download original E5 ONNX files. Model identity is recorded in manifest.json."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,urllib.request
from core.settings import DATA

FILES={'model.onnx':'onnx/model_qint8_avx512_vnni.onnx','config.json':'onnx/config.json','tokenizer.json':'onnx/tokenizer.json','tokenizer_config.json':'onnx/tokenizer_config.json','special_tokens_map.json':'onnx/special_tokens_map.json','sentencepiece.bpe.model':'onnx/sentencepiece.bpe.model'}
REVISION='614241f622f53c4eeff9890bdc4f31cfecc418b3'

def download(path=None):
    path=Path(path or DATA/'models/e5-small');path.mkdir(parents=True,exist_ok=True)
    def get(item):
        name,source=item;target=path/name
        if not target.exists():
            with urllib.request.urlopen('https://huggingface.co/intfloat/multilingual-e5-small/resolve/'+REVISION+'/'+source,timeout=90) as response,target.with_suffix(target.suffix+'.part').open('wb') as f:
                while chunk:=response.read(1024*1024):f.write(chunk)
            target.with_suffix(target.suffix+'.part').replace(target)
        return {'file':name,'source':'https://huggingface.co/intfloat/multilingual-e5-small/blob/main/'+source,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size}
    with ThreadPoolExecutor(max_workers=3) as pool:manifest=list(pool.map(get,FILES.items()))
    (path/'manifest.json').write_text(json.dumps({'model':'intfloat/multilingual-e5-small','license':'MIT','format':'ONNX qint8','files':manifest},indent=2),encoding='utf-8')
    print('E5 files verified:',len(manifest))

if __name__=='__main__':download()
