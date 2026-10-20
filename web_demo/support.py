"""Shared semantic retrieval and a structured inference adapter for document Q&A."""
import copy
import json
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import httpx

MAX_UPLOAD = 5 * 1024 * 1024
MAX_TEXT = 100_000
MAX_PAGES = 50
MODELS = ('openai/gpt-oss-20b', 'qwen/qwen3.8-27b')
from web_demo.semantic import PROFILE


def parse_upload(name, raw):
    """Use the API parser, token splitter, embeddings and Chroma store unchanged."""
    from evidence_api.ingestion import parse_document
    from web_demo.semantic import SemanticDocument
    name = Path(name.replace('\\', '/')).name
    if not raw or len(raw) > MAX_UPLOAD:
        raise ValueError('Choose a nonempty file up to 5 MiB.')
    parsed = parse_document(name, raw)
    if len(parsed['pages']) > MAX_PAGES:
        raise ValueError('Demo limit: 50 text-bearing pages.')
    if sum(len(page['text']) for page in parsed['pages']) > MAX_TEXT:
        raise ValueError('Demo limit: 100,000 extracted characters.')
    session = SemanticDocument(name, raw)
    return {'document_id': session.document_id, 'source': parsed['source'],
            'pages': len(parsed['pages']), 'chunk_count': session.summary['chunks'],
            'warnings': parsed['warnings'], 'sha256': parsed['sha256'],
            'retrieval_profile': PROFILE, 'retrieval_settings': session.profile,
            '_semantic_session': session}


def close_document(document):
    if document and document.get('_semantic_session'):
        document['_semantic_session'].close()


def retrieve(document, question, top_k=5):
    if not question.strip() or len(question) > 1200:
        raise ValueError('Enter a question of 1–1200 characters.')
    return document['_semantic_session'].search(question, top_k)


def schema_for_transport(schema):
    """Keep provider's structural schema portable; local validation enforces size bounds."""
    value=copy.deepcopy(schema)
    def walk(v):
        if isinstance(v,dict):
            for k in ('minLength','maxLength','minItems','maxItems','minimum','maximum'):v.pop(k,None)
            for child in v.values():walk(child)
        elif isinstance(v,list):
            for child in v:walk(child)
    walk(value);return value


class GroqClient:
    def __init__(self,key,model,transport=None):
        if not key:raise ValueError('Server inference key is not configured.')
        if model not in MODELS:raise ValueError('Model is not enabled for this demo.')
        self._key,self.model=key,model
        self.transport=transport
        self.actual_requests=[]
    def list(self):
        return SimpleNamespace(model_dump=lambda **kw:{'provider':'groq','models':[{'model':self.model}],
            'reasoning_effort':'low' if self.model.startswith('openai/') else 'none',
            'ollama_think_flag':'not_applicable','context_limit_control':'provider-defined',
            'schema_mode':'strict structural schema; local size/semantic checks retained',
            'automatic_retries':0,'paid_fallback':False})
    def chat(self,*,model,messages,format,options,think,stream):
        if model!=self.model or stream:raise ValueError('Unsupported transport request.')
        if not messages or messages[0].get('role') != 'system':
            raise ValueError('A system message is required.')
        schema=schema_for_transport(format)
        # The provider sees length/item bounds as instructions; local validation remains strict.
        messages=copy.deepcopy(messages)
        messages[0]['content']+='\nRespect these output constraints: '+json.dumps(format,separators=(',',':'))
        payload={'model':model,'messages':messages,'temperature':0,'seed':42,'stream':False,
                 'max_completion_tokens':int(options.get('num_predict',4096)),
                 'reasoning_effort':'low' if model.startswith('openai/') else 'none',
                 'include_reasoning':False,
                 'response_format':{'type':'json_schema','json_schema':{'name':'evidenceshift_stage','strict':True,'schema':schema}}}
        self.actual_requests.append(copy.deepcopy(payload))
        with httpx.Client(timeout=90.0,transport=self.transport) as client:
            response=client.post('https://api.groq.com/openai/v1/chat/completions',json=payload,
                                 headers={'Authorization':'Bearer '+self._key})
        if response.status_code==429:raise RuntimeError('Free inference quota/rate limit reached. No retry or paid fallback was attempted.')
        if response.status_code>=400:raise RuntimeError(f'Inference request rejected (HTTP {response.status_code}). No retry or paid fallback was attempted.')
        data=response.json();choice=data['choices'][0]
        return SimpleNamespace(message=SimpleNamespace(content=choice['message'].get('content') or '',thinking=None),
                               done_reason='stop' if choice['finish_reason']=='stop' else choice['finish_reason'],
                               eval_count=data.get('usage',{}).get('completion_tokens'))


class DemoBudget:
    """Bound public usage per process; provider free-plan quotas remain authoritative."""
    def __init__(self,limit=8,window=3600):self.limit,self.window=limit,window;self.events=deque();self.lock=threading.Lock()
    def reserve(self,now=None):
        now=time.time() if now is None else now
        with self.lock:
            while self.events and self.events[0]<=now-self.window:self.events.popleft()
            if len(self.events)>=self.limit:return False
            self.events.append(now);return True


def answer_document(document,question,model,key,variant='retrieved',transport=None):
    from evidence_api import grounded
    hits=retrieve(document,question)
    passages=hits if variant=='retrieved' else list(reversed(hits)) if variant=='reversed' else []
    # Retain the highest-ranked prefix under the core's byte budget; omissions are recorded.
    kept=[];omitted=[]
    for c in passages:
        test=kept+[c];catalog=grounded.evidence_catalog(test)
        body=json.dumps({'question':question,'paragraphs':[{'handle':x['selection_handle'],'text':x['quote']} for x in catalog]},ensure_ascii=False)
        size=len(grounded.SELECT_PROMPT.encode())+len(body.encode())+len(json.dumps(grounded.selection_schema(test),separators=(',',':')).encode())
        if size<=grounded.INPUT_BYTE_BUDGET:kept=test
        else:omitted.append(c['id'])
    if passages and not kept:raise ValueError('Retrieved evidence cannot fit the demo input budget.')
    source_id='live_'+uuid_hex()
    request={'question':question,'expected_answer':None,'gold_evidence_ids':[]}
    client=GroqClient(key,model,transport)
    setup={'run_id':source_id,'request':request,'model':model,
           'options':{'temperature':0,'seed':42,'num_ctx':8192,'num_predict':4096},'think':False,
           'profile':{'retrieval':PROFILE,'retrieval_settings':document['retrieval_settings'],'top_k':5,'inference':'groq-free-plan','reasoning_effort':client.list().model_dump()['reasoning_effort'],
                      'ollama_think_flag':'not_applicable','num_ctx':'provider-defined; local pipeline byte cap applies'},
           'retrieved':hits,'omitted_for_budget':omitted,'document':{k:v for k,v in document.items() if not k.startswith('_') and k!='chunks'}}
    record={'prompt_name':'live_input','variant':variant,'context':kept,'user_prompt':json.dumps({'question':question,'evidence':kept}),
            'input_only':True}
    with tempfile.TemporaryDirectory(prefix='evidenceshift_live_') as tmp:
        source=Path(tmp)/'input';source.mkdir()
        (source/'setup.json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
        (source/'result.json').write_text(json.dumps({'run_id':source_id,'records':[record]}),encoding='utf-8')
        result,bundle=grounded.run(source,Path(tmp)/'runs',client,prompt='live_input',variant=variant,thinking_mode='off')
        result['demo_profile']=setup['profile'];result['omitted_for_budget']=omitted
        result['provider_requests']=client.actual_requests
        # Update the downloadable result using the core's checkpoint/bundle writer.
        grounded.save(bundle.parent,result)
        return result,bundle.read_bytes(),kept


def uuid_hex():
    from uuid import uuid4
    return uuid4().hex[:12]
