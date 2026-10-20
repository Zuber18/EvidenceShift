"""Local multi-document demo service using evaluated retrieval and generation.

Saved candidates and provenance are inspectable experimental outputs. Identity
locks measure local weights/settings; they do not certify factual correctness.
"""
import copy
import csv
import hashlib
import importlib.metadata
import json
import platform
import threading
import zipfile
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4
from . import grounded as base,fresh_candidates as generator

VERSION='local-upload-1.0.0'
MAX_FILE=5*1024*1024
MAX_TOTAL=20*1024*1024
MAX_FILES=8
MAX_TEXT=100_000
MAX_PAGES=50
LOCK=threading.RLock()


def stamp(prefix):
    return prefix+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]


def digest_json(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()).hexdigest()


def parameter_digest(named_parameters):
    """Hash exact stored tensor bytes with names, dtypes and shapes; never save weights."""
    digest=hashlib.sha256()
    for name,tensor in sorted(named_parameters.items()):
        array=tensor.detach().cpu().contiguous().numpy()
        header=json.dumps({'name':name,'dtype':str(array.dtype),'shape':list(array.shape)},sort_keys=True).encode()
        digest.update(len(header).to_bytes(8,'big'));digest.update(header)
        raw=array.tobytes(order='C');digest.update(len(raw).to_bytes(8,'big'));digest.update(raw)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def encoder_identity(encoder):
    """Measure once per loaded encoder, which this service treats as immutable."""
    tokenizer=encoder.tokenizer
    if getattr(tokenizer,'backend_tokenizer',None) is not None:
        token_config=json.loads(tokenizer.backend_tokenizer.to_str())
        # These are mutable batching controls; the fixed encode settings are recorded separately.
        token_config.pop('padding',None);token_config.pop('truncation',None)
    else:
        token_config={'vocab':tokenizer.get_vocab(),'special_tokens':tokenizer.special_tokens_map}
    modules=[{'class':type(module).__module__+'.'+type(module).__qualname__,
              'config':module.get_config_dict() if hasattr(module,'get_config_dict') else None}
             for module in encoder._modules.values()]
    return {'weights_sha256':parameter_digest(encoder.state_dict()),'tokenizer_sha256':digest_json(token_config),
            'modules':modules,'max_seq_length':encoder.max_seq_length,
            'measurement':'Exact loaded parameter bytes plus tokenizer/module settings; no Hub commit is inferred.'}


def identity_for_store(store):
    identity=copy.deepcopy(encoder_identity(store.encoder))
    identity['retrieval_profile']=copy.deepcopy(store.profile)
    identity['encode_settings']={'device':'cpu','normalize_embeddings':True,'metric':'cosine'}
    identity['packages']={}
    for name in ['sentence-transformers','transformers','tokenizers','torch','chromadb','langchain-text-splitters']:
        try:identity['packages'][name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:identity['packages'][name]=None
    identity['fingerprint_sha256']=digest_json(identity)
    return identity


def enforce_identity_lock(path,identity):
    """Create the initial measured lock; refuse silent replacement after a change."""
    path=Path(path)
    if path.exists():
        existing=json.loads(path.read_text())
        if existing.get('fingerprint_sha256')!=identity['fingerprint_sha256']:
            raise ValueError('Embedding identity differs from config/local_embedding_lock.json. Preserve the lock and review the changed weights/settings before proceeding.')
        return 'matched_existing_lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation also protects two sessions starting at the same time.
    try:
        with path.open('x',encoding='utf-8') as stream:json.dump(identity,stream,indent=2)
    except FileExistsError:return enforce_identity_lock(path,identity)
    return 'created_measured_lock'


def validated_plan(root):
    raw=(Path(root)/'evaluation/fresh_baseline_cases.json').read_bytes();plan=json.loads(raw)
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=plan['baseline_module_sha256']:
        raise ValueError('Preserved baseline generation module differs from the evaluated version.')
    if plan['experiment_version']!=generator.VERSION:raise ValueError('Candidate generator version differs from the fixed plan.')
    return plan


def ollama_client():
    import os
    from ollama import Client
    host=os.environ.get('OLLAMA_HOST','http://localhost:11434')
    if urlsplit(host).hostname not in {'localhost','127.0.0.1','::1'}:
        raise ValueError('This local demo requires a loopback OLLAMA_HOST URL.')
    return Client(host=host,timeout=180.0)


class Workspace:
    def __init__(self,root,uploads,store_factory=None,identity_reader=identity_for_store,parser=None):
        self.root=Path(root);self.plan=validated_plan(self.root);self.closed=False;self.store=None;self.documents=[]
        if not uploads or len(uploads)>MAX_FILES:raise ValueError('Choose between one and eight documents.')
        if sum(len(raw) for name,raw in uploads)>MAX_TOTAL:raise ValueError('Combined upload limit is 20 MiB.')
        if parser is None:
            from .ingestion import parse_document
            parser=parse_document
        parsed=[];characters=0
        for name,raw in uploads:
            if not raw or len(raw)>MAX_FILE:raise ValueError('Each file must be nonempty and at most 5 MiB.')
            doc=parser(name,raw);characters+=sum(len(p['text']) for p in doc['pages'])
            if len(doc['pages'])>MAX_PAGES:raise ValueError('Each document is limited to 50 text-bearing pages.')
            parsed.append((doc,raw))
        if characters>MAX_TEXT:raise ValueError('Combined extracted-text limit is 100,000 characters.')
        runtime=self.root/'data_local/upload_sessions';runtime.mkdir(parents=True,exist_ok=True)
        self.temporary=TemporaryDirectory(prefix='session_',dir=runtime)
        self.folder=self.root/'results'/stamp('local_upload_session_');self.folder.mkdir(parents=True)
        self.runs=[]
        try:
            if store_factory is None:
                from web_demo.semantic import create_store
                store_factory=create_store
            with LOCK:
                self.store=store_factory(self.temporary.name)
                expected={'embedding_model':'sentence-transformers/all-MiniLM-L6-v2','chunk_tokens':180,
                          'overlap_tokens':30,'splitter':'recursive-huggingface-token-v1'}
                if any(self.store.profile.get(k)!=v for k,v in expected.items()):raise ValueError('The semantic retrieval profile differs from the evaluated MiniLM pipeline.')
                self.identity=identity_reader(self.store)
                self.lock_status=enforce_identity_lock(self.root/'config/local_embedding_lock.json',self.identity)
                ids=set()
                for doc,raw in parsed:
                    summary=self.store.ingest(doc['source'],raw)
                    if summary['document_id'] in ids:continue
                    ids.add(summary['document_id'])
                    archive_path=self.folder/'uploads'/(summary['document_id']+doc['extension'])
                    archive_path.parent.mkdir(exist_ok=True);archive_path.write_bytes(raw)
                    self.documents.append({**summary,'sha256':doc['sha256'],'pages':len(doc['pages']),
                         'warnings':doc['warnings'],'archive_path':str(archive_path.relative_to(self.folder))})
            self.manifest={'service_version':VERSION,'session_id':self.folder.name,'documents':self.documents,
                           'retrieval_identity':self.identity,'lock_status':self.lock_status,
                           'python':platform.python_version(),'model':self.plan['model'],'options':self.plan['options'],
                           'source_module_sha256':{},'note':'Local experimental candidates; mechanical checks do not establish factual correctness.'}
            for name in ['grounded.py','fresh_candidates.py','local_upload.py','app.py','store.py','ingestion.py','word_documents.py']:
                path=Path(__file__).parent/name
                if path.exists():self.manifest['source_module_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
            (self.folder/'session.json').write_text(json.dumps(self.manifest,indent=2),encoding='utf-8')
            (self.folder/'embedding_identity.json').write_text(json.dumps(self.identity,indent=2),encoding='utf-8')
            self.save_summary()
        except Exception as exc:
            (self.folder/'startup_error.json').write_text(json.dumps({'error':f'{type(exc).__name__}: {exc}'},indent=2))
            self.close();raise

    def search(self,question):
        if self.closed:raise ValueError('The workspace has been cleared.')
        if not question.strip() or len(question)>1200:raise ValueError('Enter a question of 1–1200 characters.')
        with LOCK:return self.store.search(question,5,[d['document_id'] for d in self.documents])

    def ask(self,question,variant='retrieved',client=None):
        if variant not in {'retrieved','reversed','no_context'}:raise ValueError('Unknown evidence-order variant.')
        folder=self.folder/'runs'/stamp('run_');folder.mkdir(parents=True)
        run={'run_id':folder.name,'service_version':VERSION,'question':question,'variant':variant,
             'factual_correctness':'not_automatically_scored','production_delivery':False,
             'embedding_identity':self.identity,'documents':self.documents,'complete':False}
        try:
            hits=self.search(question);used=list(reversed(hits)) if variant=='reversed' else [] if variant=='no_context' else hits
            run.update(retrieved=hits,used_context=used,omitted_for_budget=[])
            # No prefix fitting: oversized evidence is recorded by the evaluated generator as a failure.
            if used:
                client=client or ollama_client()
                inventory=client.list().model_dump(mode='json');run['model_inventory']=inventory
                if self.plan['model'] not in {m['model'] for m in inventory.get('models',[])}:
                    raise ValueError('The frozen model is not installed in Ollama: '+self.plan['model'])
            else:run['model_inventory']={'check':'skipped for empty-context code control'}
            result,bundle=generator.run(question,used,client,self.plan['model'],self.plan['options'],folder/'trace',
                      {'source':'local_upload_ui','variant':variant,'session_id':self.folder.name})
            run['result']=result;run['status']=result['status']
        except Exception as exc:run.update(status='run_failed',error=f'{type(exc).__name__}: {exc}')
        run['complete']=True
        (folder/'run.json').write_text(json.dumps(run,indent=2),encoding='utf-8')
        candidate=run.get('result',{}).get('candidate_answer')
        lines=['# Local document run','','Question: '+question,'','Variant: '+variant,'','Status: '+run['status'],'',
               'Generated candidate (not factually certified):','','> '+(candidate or '(No mechanically valid candidate)').replace('\n','\n> '),'']
        for passage in run.get('used_context',[]):
            lines+=['Source '+passage['source']+'; page '+str(passage['page'])+'; '+passage['id'],'','> '+passage['text'].replace('\n','\n> '),'']
        if run.get('error') or run.get('result',{}).get('error'):lines+=['Error: '+str(run.get('error') or run['result']['error'])]
        (folder/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        self.runs.append({'run_id':folder.name,'question':question,'variant':variant,'status':run['status'],
                          'answer':candidate,'run_path':str((folder/'run.json').relative_to(self.folder)),
                          'factual_correctness':'not_automatically_scored'})
        self.save_summary()
        return run

    def save_summary(self):
        payload={'session_id':self.folder.name,'documents':self.documents,'runs':self.runs,'factual_correctness':'not_automatically_scored'}
        temp=self.folder/'summary.tmp';temp.write_text(json.dumps(payload,indent=2),encoding='utf-8');temp.replace(self.folder/'summary.json')
        if self.runs:
            with (self.folder/'runs.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(self.runs[0]));writer.writeheader();writer.writerows(self.runs)

    def export(self):
        bundle=self.folder/'local_upload_smoke_bundle.zip'
        temp=self.folder/'export.tmp'
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in self.folder.rglob('*'):
                if path.is_file() and path not in {bundle,temp} and path.name!='grounded_bundle.zip':archive.write(path,path.relative_to(self.folder))
        temp.replace(bundle)
        return bundle

    def close(self):
        if self.closed:return
        self.closed=True
        try:
            if self.store is not None:self.store.client.delete_collection(self.store.collection.name)
        finally:
            if hasattr(self,'temporary'):self.temporary.cleanup()
