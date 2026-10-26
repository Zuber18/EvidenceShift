"""Prepare and run the approved 48-generation EvidenceShift development pilot.

Save this file in the existing project root. Preparation measures the local
MiniLM identity and freezes retrieved evidence without generating answers:
    python run_real_document_pilot.py --self-test
    python run_real_document_pilot.py --prepare
    python run_real_document_pilot.py --run

The run command is resumable. Every reserved/started request consumes one of
48 attempt slots; failed or interrupted attempts are preserved and never retried.
Only the eight selected development questions are indexed or generated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import time
import unittest
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener
from uuid import uuid4
import zipfile

VERSION='real-document-pilot-1.0.1'
PILOT_IDS=tuple(f'calibration_{i:02d}' for i in range(1,9))
MODEL_DIGESTS={
 'qwen3:4b':'359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7',
 'qwen3:8b':'500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41',
 'gemma3:4b':'68ceab7e468a31c988b44d5a4984a0e21f58c4f7158c6ce29c1804babac38df7',
}
OPTIONS={'temperature':0,'seed':42,'num_ctx':32768,'num_predict':2048}
INPUT_BYTE_CAP=24576
ORDERS=('canonical','reversed')
ABSTENTION='The supplied evidence does not answer this question.'
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'evaluation/benchmarks/real_documents_v1'
CODE_FILES=('run_real_document_pilot.py','run_direct_answer_baseline.py',
 'scripts/validate_real_document_benchmark.py','web_demo/semantic.py',
 'src/evidence_api/app.py','src/evidence_api/engine.py','src/evidence_api/store.py',
 'src/evidence_api/ingestion.py','src/evidence_api/local_upload.py',
 'src/evidence_api/fresh_candidates.py','src/evidence_api/grounded.py',
 'src/evidence_api/prompts.py','src/evidence_api/evaluation.py')


def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def digest(value): return sha(canonical(value))
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def timestamp(): return datetime.now(timezone.utc).isoformat()


def write(path,value):
    """Replace a report atomically so interruption cannot leave truncated JSON."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def validator(root):
    spec=importlib.util.spec_from_file_location('pilot_benchmark_validator',root/'scripts/validate_real_document_benchmark.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def baseline(root):
    spec=importlib.util.spec_from_file_location('pilot_direct_baseline',root/'run_direct_answer_baseline.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def selected_inputs(inventory):
    """Project scoring records onto an explicit model-input allowlist."""
    byid={c['id']:c for c in inventory['cases']}
    result=[]
    for cid in PILOT_IDS:
        c=byid[cid]
        if c['split']!='development':raise ValueError('Pilot selection crossed into reserved evaluation.')
        result.append({k:copy.deepcopy(c[k]) for k in ('id','question','source_ids')})
    return result


def messages_for(prompt,question,context):
    payload={'question':question,'passages':[
        {k:c[k] for k in ('id','source','page','text')} for c in context]}
    return [{'role':'system','content':prompt},
            {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]


def budget_for(messages,options=OPTIONS):
    size=len(json.dumps(messages,ensure_ascii=False).encode())
    if size>INPUT_BYTE_CAP or size+options['num_predict']+1024>options['num_ctx']:
        raise ValueError('Input exceeds the conservative byte reservation; no evidence was trimmed.')
    return {'input_bytes':size,'input_byte_cap':INPUT_BYTE_CAP,'reserved_output_tokens':options['num_predict'],
            'template_margin_tokens':1024,'method':'Conservative UTF-8 byte proxy, not an exact model tokenizer count.'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Local Ollama redirects are refused.')


class LocalAPI:
    """Loopback-only metadata and streaming requests, without retries or proxies."""
    def __init__(self,host):
        host=host if '://' in host else 'http://'+host
        parsed=urlsplit(host)
        if parsed.scheme not in {'http','https'} or parsed.hostname not in {'localhost','127.0.0.1','::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'','/'}:
            raise ValueError('Use a loopback Ollama origin, for example http://localhost:11434.')
        self.host=host.rstrip('/');self.opener=build_opener(ProxyHandler({}),NoRedirect())

    def request(self,path,payload=None,timeout=30):
        data=None if payload is None else json.dumps(payload).encode()
        return self.opener.open(Request(self.host+path,data=data,headers={'Content-Type':'application/json'}),timeout=timeout)

    def json(self,path,payload=None):
        with self.request(path,payload) as response:return json.load(response)

    def lines(self,payload):
        with self.request('/api/chat',payload,timeout=180) as response:
            for line in response:
                if line.strip():yield line


def check_models(api):
    inventory=api.json('/api/tags')
    present={m.get('name',m.get('model')):m for m in inventory.get('models',[])}
    for name,expected in MODEL_DIGESTS.items():
        if present.get(name,{}).get('digest','').removeprefix('sha256:')!=expected:
            raise ValueError('Installed model missing or digest changed: '+name)
    return {name:present[name] for name in MODEL_DIGESTS}


def show_identity(show):
    # Omit volatile timestamps and platform-local blob paths from comparison.
    fields=('parameters','template','system','model_info','details','capabilities',
            'thinking','renderer','parser','template_source')
    return digest({k:show.get(k) for k in fields})


def inspect_models(api):
    installed=check_models(api);shows={}
    for model in MODEL_DIGESTS:
        show=api.json('/api/show',{'model':model})
        capacities=[v for k,v in show.get('model_info',{}).items()
                    if k.endswith('.context_length') and isinstance(v,int)]
        if not capacities or max(capacities)<OPTIONS['num_ctx']:
            raise ValueError('Cannot establish the configured native context capacity for '+model)
        # Preserve thinking metadata for reproducibility, but do not infer API
        # support from its shape. The generation request explicitly sends
        # think=False; a server rejection is recorded and stops the batch.
        shows[model]=show
    return {'installed':installed,'shows':shows,'show_identity':{m:show_identity(s) for m,s in shows.items()},
            'ollama_version':api.json('/api/version')}


def code_identity(root):
    return {name:sha((root/name).read_bytes()) for name in CODE_FILES}


def safe_run_folder(root,relative):
    path=(root/relative).resolve()
    if not path.is_relative_to((root/'results').resolve()):raise ValueError('Run folder must stay inside project results/.')
    return path


@contextmanager
def process_lock(path):
    """OS advisory locking releases automatically even when a process crashes."""
    import fcntl
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another pilot process holds this lock.')
        try:
            stream.seek(0);stream.truncate();stream.write(str(os.getpid()));stream.flush()
            yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def prepare(root,base,api,store_factory=None,identity_reader=None):
    check=validator(root).validate(base)
    if not check['benchmark_ready_for_configuration']:raise ValueError('Benchmark source/gold validation failed: '+str(check['errors']))
    active=base/'execution_plan.json'
    if active.exists():
        plan=read(active)
        if plan.get('pilot_version')!=VERSION:raise ValueError('Another execution plan exists; it will not be replaced.')
        verify_plan(root,base,plan)
        print('Existing pilot preparation verified:',plan['run_folder'])
        print('Generation calls during preparation: 0');return plan
    inputs=selected_inputs(read(base/'cases.json'))
    run_id='real_document_pilot_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]
    folder=root/'results'/run_id;folder.mkdir(parents=True)
    try:
        write(folder/'preparation.json',{'complete':False,'generation_calls':0,'started_on':timestamp()})
        metadata=inspect_models(api)
        # Existing cached weights only. These switches are set before importing
        # the project encoder; preparation never downloads model weights.
        os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['ANONYMIZED_TELEMETRY']='False'
        sys.path.insert(0,str(root/'src'));sys.path.insert(0,str(root))
        if store_factory is None:
            from web_demo.semantic import create_store
            store_factory=create_store
        if identity_reader is None:
            from evidence_api.local_upload import identity_for_store
            identity_reader=identity_for_store
        store=store_factory(root/'data_local/benchmark_pilot'/run_id)
        expected={'embedding_model':'sentence-transformers/all-MiniLM-L6-v2','chunk_tokens':180,
                  'overlap_tokens':30,'splitter':'recursive-huggingface-token-v1'}
        if any(store.profile.get(k)!=v for k,v in expected.items()):raise ValueError('Retrieval differs from the existing MiniLM/token-splitting policy.')
        identity=identity_reader(store)
        prior_lock=root/'config/local_embedding_lock.json'
        if prior_lock.exists() and read(prior_lock).get('fingerprint_sha256')!=identity.get('fingerprint_sha256'):
            raise ValueError('Loaded embedding identity differs from the existing local upload lock. The prior lock was preserved.')
        prompt=baseline(root).PROMPT
        source_ids=sorted({s for c in inputs for s in c['source_ids']})
        sources={s['id']:s for s in read(base/'sources.proposed.json')['sources']}
        summaries={};all_chunks={}
        for sid in source_ids:
            if sources[sid]['proposed_split']!='development':raise ValueError('Reserved document selected for pilot indexing.')
            raw=(base/'source_snapshots'/sid/'body.txt').read_bytes()
            text_copy=folder/'source_texts'/(sid+'.txt');text_copy.parent.mkdir(exist_ok=True)
            text_copy.write_bytes(raw)
            summaries[sid]=store.ingest(sid+'.txt',raw)
            docid=summaries[sid]['document_id'];chunks=[];offset=0
            while True:
                batch=store.chunks(docid,200,offset)
                if not batch:break
                chunks.extend(batch);offset+=len(batch)
            all_chunks[sid]=chunks
        contexts={};budgets={}
        for case in inputs:
            ids=[summaries[sid]['document_id'] for sid in case['source_ids']]
            hits=store.search(case['question'],5,ids)
            if not hits or len({p['id'] for p in hits})!=len(hits):raise ValueError('Retrieval returned empty or duplicate passages.')
            if any(h['document_id'] not in ids for h in hits):raise ValueError('Retrieval escaped declared source scope.')
            contexts[case['id']]=hits
            budgets[case['id']]={order:budget_for(messages_for(prompt,case['question'],hits if order=='canonical' else list(reversed(hits)))) for order in ORDERS}
        prepared={'pilot_version':VERSION,'inputs':inputs,'contexts':contexts,'budgets':budgets,
                  'documents':summaries,'scope':'body.txt ingested as unpaginated UTF-8 text; this is not a PDF/DOCX parser trial.'}
        write(folder/'prepared.json',prepared);write(folder/'chunks.json',all_chunks)
        write(folder/'embedding_identity.json',identity);write(folder/'models.json',metadata)
        packages={}
        for name in ('sentence-transformers','transformers','tokenizers','torch','chromadb','langchain-text-splitters','ollama'):
            try:packages[name]=importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:packages[name]=None
        write(folder/'environment.json',{'python':platform.python_version(),'platform':platform.platform(),'packages':packages,'generation_calls':0})
        for name in CODE_FILES:
            path=folder/'source_snapshot'/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((root/name).read_bytes())
        write(folder/'source_gold_preflight.json',check)
        frozen_paths=[folder/name for name in ['prepared.json','chunks.json','embedding_identity.json','models.json','environment.json','source_gold_preflight.json']]
        frozen_paths.extend(p for directory in ['source_texts','source_snapshot'] for p in (folder/directory).rglob('*') if p.is_file())
        frozen_files={str(path.relative_to(folder)):sha(path.read_bytes()) for path in frozen_paths}
        revision=store.profile.get('resolved_revision') or 'weights-sha256:'+identity['weights_sha256']
        plan={'status':'locked','pilot_version':VERSION,'prepared_on':timestamp(),
              'budget_selected_on':'2026-10-22','budget_selection':'Project owner selected the 48-generation development pilot.',
              'benchmark_freeze_sha256':sha((base/'freeze_manifest.json').read_bytes()),
              'model_digests':MODEL_DIGESTS,'generation_options':OPTIONS,'think':False,'stream':True,
              'prompt_sha256':sha(prompt.encode()),'generator_code_sha256':sha(Path(__file__).read_bytes()),
              'prompt':prompt,'code_files':code_identity(root),'question_ids':list(PILOT_IDS),
              'evidence_orders':list(ORDERS),'max_generation_calls':48,'verifier_enabled':False,
              'retrieval':{'embedding_model':expected['embedding_model'],'embedding_revision':revision,
                'embedding_weights_sha256':identity['weights_sha256'],'embedding_tokenizer_sha256':identity['tokenizer_sha256'],
                'identity_fingerprint_sha256':identity['fingerprint_sha256'],
                'chunk_size':180,'chunk_overlap':30,'chunk_units':'encoder tokens','top_k':5,
                'context_budget':INPUT_BYTE_CAP,'context_budget_units':'UTF-8 input-message bytes',
                'metric':'cosine','normalize_embeddings':True,'source_scope':'one declared development document per question',
                'policy':'Use saved Chroma ranking once per question; canonical means retrieved order. Reverse only the identical passage list.'},
              'run_folder':str(folder.relative_to(root)),'prepared_files':frozen_files,
              'ollama_host':api.host,'model_show_identity':metadata['show_identity'],
              'retry_policy':'No automatic retries. Every started request reserves one of 48 attempt slots, including failures and interrupted requests.',
              'review_policy':'Mechanical checks only; claim support/completeness/strict factual pass are not automatically scored.'}
        write(folder/'plan.json',plan)
        if active.exists():raise ValueError('An execution plan appeared during preparation; it was not replaced.')
        write(active,plan)
        verify_plan(root,base,plan)
        write(folder/'preparation.json',{'complete':True,'generation_calls':0,'planned_generation_attempts':48,'selected_questions':8,'split':'development','indexed_sources':source_ids})
        summary(folder,plan,prepared)
        print('Pilot prepared: 8 development questions; 3 models; 2 orders; 48 generation attempts.')
        print('Generation calls during preparation: 0')
        print('Saved:',folder)
        return plan
    except BaseException as exc:
        write(folder/'preparation_error.json',{'error':f'{type(exc).__name__}: {exc}','generation_calls':0})
        if active.exists() and read(active).get('run_folder')==str(folder.relative_to(root)):
            active.unlink()  # No generation occurred; keep the failed folder as provenance.
        raise


def verify_plan(root,base,plan):
    if plan.get('pilot_version')!=VERSION or plan.get('question_ids')!=list(PILOT_IDS) or plan.get('max_generation_calls')!=48 or plan.get('model_digests')!=MODEL_DIGESTS:
        raise ValueError('Pilot selection, model versions or budget differ from the approved plan.')
    if plan.get('evidence_orders')!=list(ORDERS) or plan.get('generation_options')!=OPTIONS or plan.get('think') is not False or plan.get('stream') is not True or plan.get('verifier_enabled') is not False:
        raise ValueError('Pilot generation protocol changed.')
    checks=validator(root).validate(base)
    if not checks['ready_for_model_execution']:raise ValueError('Execution readiness failed: '+str(checks['errors']+checks['execution_plan_blockers']))
    if plan['benchmark_freeze_sha256']!=sha((base/'freeze_manifest.json').read_bytes()):raise ValueError('Benchmark freeze changed.')
    if plan['code_files']!=code_identity(root) or plan['generator_code_sha256']!=sha(Path(__file__).read_bytes()):raise ValueError('Pilot or retrieval code changed after preparation.')
    if plan['prompt_sha256']!=sha(baseline(root).PROMPT.encode()) or plan['prompt']!=baseline(root).PROMPT:raise ValueError('Baseline prompt changed.')
    folder=safe_run_folder(root,plan['run_folder'])
    if read(folder/'plan.json')!=plan:raise ValueError('Active plan differs from the saved run plan.')
    for name,expected in plan['prepared_files'].items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder) or sha(path.read_bytes())!=expected:raise ValueError('Prepared input changed: '+name)
    prepared=read(folder/'prepared.json')
    if prepared['inputs']!=selected_inputs(read(base/'cases.json')):raise ValueError('Pilot input projection changed.')
    if set(prepared['contexts'])!=set(PILOT_IDS):raise ValueError('Context inventory differs from pilot selection.')
    return folder,prepared


def jobs_for(inputs):
    # Group by model to avoid unnecessary reloads; reverse the within-pair first
    # order on alternating questions so canonical is not always the first call.
    jobs=[]
    for model in MODEL_DIGESTS:
        for i,c in enumerate(inputs):
            orders=ORDERS if i%2==0 else tuple(reversed(ORDERS))
            for order in orders:
                jobs.append({'id':digest([VERSION,model,c['id'],order])[:24],
                             'model':model,'case_id':c['id'],'order':order,'question':c['question']})
    return jobs


def citation_checks(answer,context,done_reason):
    """Keep numeric/code brackets separate from canonical passage citations."""
    known={c['id'] for c in context};ids=[];unresolved=[]
    for group in re.findall(r'\[([^\[\]\n]+)\]',answer):
        pieces=re.split(r'[\s,;]+',group.strip())
        found=[s for s in pieces if s in known or s.startswith('doc_')]
        ids.extend(found)
        if not found:unresolved.append(group)
    ids=list(dict.fromkeys(ids));unknown=[s for s in ids if s not in known]
    exact=answer.strip()==ABSTENTION
    completed=done_reason=='stop' and bool(answer.strip())
    issues=[]
    if not completed:issues.append('incomplete_or_empty_generation')
    if unknown:issues.append('unknown_citation_ids')
    if not exact and not ids:issues.append('missing_canonical_citations')
    if ABSTENTION in answer and not exact:issues.append('abstention_with_extra_text')
    if re.search(r'</?think\b',answer,re.I):issues.append('reasoning_markup_in_answer')
    return {'completed':completed,'citation_ids':ids,'unknown_citation_ids':unknown,
            'has_citations':bool(ids),'citation_ids_valid':not unknown,'exact_abstention':exact,
            'other_bracket_groups':unresolved,'mechanical_issues':issues,
            'citation_support':'not_automatically_scored','factual_correctness':'not_automatically_scored',
            'required_unit_coverage':None,'strict_pass':None,
            'parser_note':'Other brackets may be Python list literals or ambiguous citation styles; preserve them for review. Canonical membership does not establish support.'}


def recover_partial(folder,record):
    """Recover durable streamed fragments after process loss without a new call."""
    answer=[];thinking=[];final={}
    path=folder/'stream.ndjson'
    if path.exists():
        for line in path.read_bytes().splitlines():
            try:frame=json.loads(line)
            except (ValueError,UnicodeError):continue
            msg=frame.get('message',{});answer.append(msg.get('content','') or '');thinking.append(msg.get('thinking','') or '')
            if frame.get('done'):final=frame
    record.update(answer=''.join(answer),thinking=''.join(thinking),final_response=final,
                  status='interrupted_preserved',complete=True,
                  error='Previous process ended after reserving this request; submission/completion may be uncertain. No retry was made.')
    return record


def run_job(job,context,folder,plan,api):
    folder.mkdir(parents=True,exist_ok=True);path=folder/'record.json'
    if path.exists():return read(path)
    messages=messages_for(plan['prompt'],job['question'],context)
    budget=budget_for(messages,plan['generation_options'])
    payload={'model':job['model'],'messages':messages,'options':plan['generation_options'],
             'think':False,'stream':True}
    record={'pilot_version':VERSION,'job':job,'status':'request_reserved','complete':False,
            'reserved_at':timestamp(),'attempt_slots_consumed':1,'request':payload,'budget':budget,
            'context':context,'answer':'','thinking':'','factual_correctness':'not_automatically_scored',
            'final_response':{},'strict_pass':None}
    # The reservation is durable before HTTP submission. A crash in that gap
    # consumes a slot conservatively rather than risking an unlogged retry.
    with path.open('x',encoding='utf-8') as file:
        json.dump(record,file,ensure_ascii=False,indent=2);file.flush();os.fsync(file.fileno())
    answer=[];thinking=[];final={};started=time.perf_counter();interrupted=False
    try:
        with (folder/'stream.ndjson').open('xb') as wire:
            for raw in api.lines(payload):
                wire.write(raw if raw.endswith(b'\n') else raw+b'\n');wire.flush();os.fsync(wire.fileno())
                if time.perf_counter()-started>900:raise TimeoutError('Total generation deadline exceeded.')
                frame=json.loads(raw)
                if frame.get('error'):
                    record['stop_batch']=True
                    raise RuntimeError(str(frame['error']))
                message=frame.get('message',{})
                answer.append(message.get('content','') or '');thinking.append(message.get('thinking','') or '')
                if frame.get('done'):
                    final=frame;break
        if not final:raise ValueError('Stream ended without a final done response.')
        if final.get('model',job['model'])!=job['model']:raise ValueError('Response model identity differs from the requested tag.')
        actual=final.get('prompt_eval_count')
        if actual is not None and actual+OPTIONS['num_predict']>OPTIONS['num_ctx']:
            raise ValueError('Actual prompt count violates the reserved output budget.')
        record['status']='output_recorded' if final.get('done_reason')=='stop' and ''.join(answer).strip() else 'incomplete_generation'
    except KeyboardInterrupt:
        interrupted=True;record.update(status='interrupted_preserved',error='KeyboardInterrupt; raw streamed fragments preserved.')
    except HTTPError as exc:
        raw_error=exc.read()
        (folder/'http_error.txt').write_bytes(raw_error)
        record.update(status='generation_failed',http_status=exc.code,
                      error=f'HTTP {exc.code}: '+raw_error.decode('utf-8',errors='replace'),
                      stop_batch=True)
    except Exception as exc:
        record.update(status='generation_failed',error=f'{type(exc).__name__}: {exc}')
    finally:
        record.update(answer=''.join(answer),thinking=''.join(thinking),final_response=final,
                      local_seconds=round(time.perf_counter()-started,3),complete=True)
        record['checks']=citation_checks(record['answer'],context,final.get('done_reason'))
        record['interrupted']=interrupted
        write(path,record)
    return record


def summary(folder,plan,prepared):
    """Save every planned row, including failed, interrupted and unattempted jobs."""
    rows=[];reserved=0
    for job in jobs_for(prepared['inputs']):
        record_path=folder/'jobs'/job['id']/'record.json'
        record=read(record_path) if record_path.exists() else {}
        if record:
            reserved+=1
            if not record.get('complete'):
                record=recover_partial(record_path.parent,record);write(record_path,record)
        checks=record.get('checks') or citation_checks(record.get('answer',''),record.get('context',[]),record.get('final_response',{}).get('done_reason'))
        rows.append({**job,'status':record.get('status','not_started'),'answer':record.get('answer'),
                     'done_reason':record.get('final_response',{}).get('done_reason'),
                     'local_seconds':record.get('local_seconds'),'prompt_eval_count':record.get('final_response',{}).get('prompt_eval_count'),
                     'eval_count':record.get('final_response',{}).get('eval_count'),
                     'citation_ids_valid':checks['citation_ids_valid'],'has_citations':checks['has_citations'],
                     'exact_abstention':checks['exact_abstention'],'error':record.get('error'),
                     'factual_correctness':'not_automatically_scored','strict_pass':None})
    result={'pilot_version':VERSION,'planned_generations':48,'reserved_attempt_slots':reserved,
            'remaining_attempt_slots':48-reserved,'status_counts':dict(Counter(r['status'] for r in rows)),
            'semantic_accuracy':None,'records':rows}
    write(folder/'summary.json',result)
    with (folder/'runs.csv').open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
    lines=['# EvidenceShift development pilot','','48 planned attempt slots: eight development questions, three models and two evidence orders.',
           f'Reserved attempts: {reserved}; remaining: {48-reserved}.','',
           'Every raw request, streamed response, partial output and failure is retained. Failed/started attempts are not retried.',
           'Canonical means the saved Chroma retrieval ranking. Reversed changes only the order of those exact passages.',
           'The corpus uses the frozen pre-extracted text; this does not evaluate PDF/DOCX parsing.',
           'Generation is ordinary text with no output schema or verifier. Citation membership is mechanical; semantic accuracy is not scored automatically.','']
    for row in rows:
        lines += [f"## {row['case_id']} · {row['model']} · {row['order']}",'',row['question'],'',
                  'Status: '+row['status'],'',row.get('answer') or '(No answer recorded.)','']
        if row.get('error'):lines+=['Error: '+row['error'],'']
    (folder/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    target=folder/'pilot_bundle.zip';temporary=folder/'pilot_bundle.tmp'
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path not in {target,temporary} and path.name!='pilot.lock':archive.write(path,path.relative_to(folder))
    temporary.replace(target)
    return result


def run(root,base,api):
    active=base/'execution_plan.json'
    if not active.exists():raise ValueError('Prepare the pilot first with --prepare.')
    plan=read(active);folder,prepared=verify_plan(root,base,plan)
    if api.host!=plan['ollama_host']:raise ValueError('Ollama origin differs from the locked plan.')
    with process_lock(folder/'pilot.lock'):
        metadata=inspect_models(api)
        if metadata['show_identity']!=plan['model_show_identity']:raise ValueError('Native model metadata changed after preparation.')
        if metadata['ollama_version']!=read(folder/'models.json')['ollama_version']:raise ValueError('Ollama server version changed after preparation.')
        summary(folder,plan,prepared)
        completed=0
        try:
            for job in jobs_for(prepared['inputs']):
                record_path=folder/'jobs'/job['id']/'record.json'
                if record_path.exists():completed+=1;continue
                if sum(1 for _ in (folder/'jobs').glob('*/record.json'))>=48:raise ValueError('The 48-slot request budget is exhausted.')
                check_models(api)
                context=prepared['contexts'][job['case_id']]
                if job['order']=='reversed':context=list(reversed(context))
                print(f"[{completed+1}/48] {job['model']} · {job['case_id']} · {job['order']}",flush=True)
                record=run_job(job,context,record_path.parent,plan,api)
                summary(folder,plan,prepared);completed+=1
                if record.get('interrupted') or record.get('stop_batch'):break
                # Detect tag mutation even if it happened during generation.
                check_models(api)
        finally:result=summary(folder,plan,prepared)
    print('Saved:',folder/'pilot_bundle.zip')
    print('Reserved attempt slots:',result['reserved_attempt_slots'],'/ 48')
    if result['remaining_attempt_slots']:
        print('Continue remaining jobs with: python run_real_document_pilot.py --run')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare',action='store_true');modes.add_argument('--run',action='store_true');modes.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if not (ROOT/'pyproject.toml').exists() or not BASE.exists():
        print('Save run_real_document_pilot.py in the existing EvidenceShift project root containing pyproject.toml and evaluation/.',file=sys.stderr)
        return 1
    if args.self_test:
        folder=ROOT/'results'/('benchmark_pilot_selftest_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8])
        folder.mkdir(parents=True)
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(SelfTests)
        with (folder/'selftest.txt').open('w',encoding='utf-8') as stream:
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        write(folder/'selftest.json',{'pilot_version':VERSION,'script_sha256':sha(Path(__file__).read_bytes()),
              'tests_run':result.testsRun,'passed':result.wasSuccessful(),
              'failures':[{'test':str(t),'trace':trace} for t,trace in result.failures],
              'errors':[{'test':str(t),'trace':trace} for t,trace in result.errors],
              'test_scope':'Offline request/accounting/integrity tests with fake transport and vectors; actual local retrieval and Ollama are checked during preparation/run.',
              'generation_calls':0})
        print(f'Ran {result.testsRun} self-tests; failures: {len(result.failures)}; errors: {len(result.errors)}.')
        print('Saved:',folder/'selftest.json')
        return 0 if result.wasSuccessful() else 1
    try:
        script_hash=sha(Path(__file__).read_bytes())
        tested=[]
        for path in (ROOT/'results').glob('benchmark_pilot_selftest_*/selftest.json'):
            try:
                report=read(path)
                if report.get('passed') is True and report.get('script_sha256')==script_hash:tested.append(path)
            except (OSError,ValueError):continue
        if not tested:raise ValueError('Run --self-test successfully for this exact script before preparation or generation.')
        api=LocalAPI(os.environ.get('OLLAMA_HOST','http://localhost:11434'))
        if args.prepare:
            with process_lock(ROOT/'data_local/benchmark_pilot/prepare.lock'):prepare(ROOT,BASE,api)
        else:run(ROOT,BASE,api)
        return 0
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr)
        destination=ROOT/'results'/('pilot_error_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]+'.json')
        write(destination,{'pilot_version':VERSION,'mode':'prepare' if args.prepare else 'run',
              'error':f'{type(exc).__name__}: {exc}',
              'generation_accounting':0 if args.prepare else 'See the preserved per-job reservation records.'})
        print('Saved error:',destination,file=sys.stderr)
        return 1


class FakeAPI:
    """Offline transport double: never contacts an Ollama server."""
    host='http://localhost:11434'
    def __init__(self,behavior='success'):
        self.behavior=behavior;self.calls=0;self.payloads=[];self.ctx=32768
    def json(self,path,payload=None):
        if path=='/api/tags':return {'models':[{'name':n,'digest':d} for n,d in MODEL_DIGESTS.items()]}
        if path=='/api/version':return {'version':'test-double'}
        if path=='/api/show':return {'model_info':{'test.context_length':self.ctx},'thinking':{'values':[False,True]},'parameters':'test-double'}
        raise AssertionError(path)
    def lines(self,payload):
        self.calls+=1;self.payloads.append(copy.deepcopy(payload))
        cid=json.loads(payload['messages'][1]['content'])['passages'][0]['id']
        yield json.dumps({'message':{'thinking':'diagnostic thinking','content':'Partial '},'done':False}).encode()+b'\n'
        if self.behavior=='interrupt':raise KeyboardInterrupt()
        if self.behavior=='failure':raise OSError('simulated disconnect')
        yield json.dumps({'model':payload['model'],'message':{'content':'answer ['+cid+']'},'done':True,
                          'done_reason':'length' if self.behavior=='length' else 'stop',
                          'prompt_eval_count':100,'eval_count':12}).encode()+b'\n'


class FakeStore:
    """Exercise plumbing with real frozen text and deliberately fake vectors."""
    profile={'embedding_model':'sentence-transformers/all-MiniLM-L6-v2','chunk_tokens':180,
             'overlap_tokens':30,'splitter':'recursive-huggingface-token-v1','resolved_revision':'test-only'}
    def __init__(self,path):self.documents={}
    def ingest(self,name,raw):
        docid='doc_'+sha(raw+b'.txt')[:20]
        self.documents[docid]=[{'id':f'{docid}_p0_c{i}','document_id':docid,'source':name,
                              'page':0,'chunk':i,'text':raw.decode()[:200]+f' (fixture {i})',
                              'sha256':sha(raw),'distance':i/10} for i in range(5)]
        return {'document_id':docid,'source':name,'chunks':5,'sha256':sha(raw)}
    def chunks(self,docid,limit=200,offset=0):return self.documents[docid][offset:offset+limit]
    def search(self,question,k,ids):return copy.deepcopy(self.documents[ids[0]][:k])


def fake_identity(store):
    return {'weights_sha256':'a'*64,'tokenizer_sha256':'b'*64,'fingerprint_sha256':'c'*64,'test_double':True}


class SelfTests(unittest.TestCase):
    def case_fixture(self):
        import shutil
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        for name in CODE_FILES:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,path)
        base=root/'evaluation/benchmarks/real_documents_v1'
        shutil.copytree(BASE,base);(base/'execution_plan.json').unlink(missing_ok=True)
        return root,base
    def prepared(self):
        import contextlib,io
        root,base=self.case_fixture();api=FakeAPI()
        with contextlib.redirect_stdout(io.StringIO()):plan=prepare(root,base,api,FakeStore,fake_identity)
        return root,base,api,plan
    def tiny_job(self,behavior='success'):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);folder=Path(tmp.name)/'job'
        context=[{'id':'doc_0123456789abcdef0123_p0_c0','source':'example.txt','page':0,'text':'Evidence.'}]
        job={'id':'one','model':'qwen3:4b','case_id':'calibration_01','order':'canonical','question':'Question?'}
        api=FakeAPI(behavior);plan={'prompt':'Use the evidence.','generation_options':OPTIONS}
        return job,context,folder,plan,api
    def test_gold_is_projected_out(self):
        inventory=read(BASE/'cases.json');inventory['cases'][0]['reference_answer']='SECRET_GOLD_CANARY'
        inventory['cases'][0]['gold_notes']='SECRET_GOLD_CANARY'
        selected=selected_inputs(inventory)
        self.assertNotIn('SECRET_GOLD_CANARY',json.dumps(selected))
        self.assertEqual(set(selected[0]),{'id','question','source_ids'})
    def test_reserved_question_refused(self):
        data=read(BASE/'cases.json');next(c for c in data['cases'] if c['id']==PILOT_IDS[0])['split']='reserved'
        with self.assertRaises(ValueError):selected_inputs(data)
    def test_jobs_are_exactly_48_unique_pairs(self):
        jobs=jobs_for(selected_inputs(read(BASE/'cases.json')))
        self.assertEqual(len(jobs),48);self.assertEqual(len({j['id'] for j in jobs}),48)
        self.assertEqual(Counter(j['model'] for j in jobs),{m:16 for m in MODEL_DIGESTS})
    def test_changed_model_digest_refused(self):
        class Changed(FakeAPI):
            def json(self,path,payload=None):
                data=super().json(path,payload)
                if path=='/api/tags':data['models'][0]['digest']='0'*64
                return data
        with self.assertRaises(ValueError):check_models(Changed())
    def test_context_capacity_checked_without_generation(self):
        api=FakeAPI();api.ctx=4096
        with self.assertRaises(ValueError):inspect_models(api)
        self.assertEqual(api.calls,0)
    def test_thinking_metadata_is_preserved_without_capability_inference(self):
        class Metadata(FakeAPI):
            def json(self,path,payload=None):
                data=super().json(path,payload)
                if path=='/api/show':data['thinking']=copy.deepcopy(self.metadata)
                return data
        for metadata in ({'default':True},{'values':['enabled','disabled']},True,None,{'values':[True]}):
            with self.subTest(metadata=metadata):
                api=Metadata();api.metadata=metadata
                result=inspect_models(api)
                self.assertEqual(api.calls,0)
                for show in result['shows'].values():self.assertEqual(show['thinking'],metadata)
    def test_server_mode_rejection_stops_without_retry_or_mode_change(self):
        class Rejected(FakeAPI):
            def lines(self,payload):
                self.calls+=1;self.payloads.append(copy.deepcopy(payload))
                yield json.dumps({'error':'requested thinking mode is unsupported'}).encode()+b'\n'
        job,context,folder,plan,_=self.tiny_job();api=Rejected()
        record=run_job(job,context,folder,plan,api)
        self.assertEqual(record['status'],'generation_failed');self.assertTrue(record['stop_batch'])
        self.assertIn('unsupported',record['error']);self.assertIs(api.payloads[0]['think'],False)
        run_job(job,context,folder,plan,api);self.assertEqual(api.calls,1)
        self.assertIn('unsupported',(folder/'stream.ndjson').read_text())
    def test_budget_refuses_without_trimming(self):
        messages=messages_for('Prompt','Question',[{'id':'one','source':'source','page':0,'text':'x'*30000}])
        with self.assertRaises(ValueError):budget_for(messages)
        self.assertEqual(len(json.loads(messages[1]['content'])['passages'][0]['text']),30000)
    def test_streamed_output_and_thinking_preserved(self):
        job,context,folder,plan,api=self.tiny_job();record=run_job(job,context,folder,plan,api)
        self.assertEqual(record['status'],'output_recorded');self.assertEqual(record['thinking'],'diagnostic thinking')
        self.assertIn('Partial answer',record['answer']);self.assertTrue((folder/'stream.ndjson').read_bytes())
        self.assertNotIn('format',api.payloads[0]);self.assertIs(api.payloads[0]['think'],False)
    def test_partial_failure_retained_and_not_retried(self):
        job,context,folder,plan,api=self.tiny_job('failure');record=run_job(job,context,folder,plan,api)
        self.assertEqual(record['answer'],'Partial ');self.assertEqual(record['status'],'generation_failed')
        run_job(job,context,folder,plan,api);self.assertEqual(api.calls,1)
    def test_keyboard_interrupt_consumes_one_slot(self):
        job,context,folder,plan,api=self.tiny_job('interrupt');record=run_job(job,context,folder,plan,api)
        self.assertTrue(record['interrupted']);self.assertEqual(record['attempt_slots_consumed'],1)
        self.assertEqual(record['answer'],'Partial ')
    def test_length_limit_is_not_completed(self):
        job,context,folder,plan,api=self.tiny_job('length');record=run_job(job,context,folder,plan,api)
        self.assertEqual(record['status'],'incomplete_generation');self.assertFalse(record['checks']['completed'])
        self.assertTrue(record['answer'])
    def test_list_literals_do_not_become_unknown_citations(self):
        cid='doc_0123456789abcdef0123_p0_c0'
        result=citation_checks('[1], [2], [1, 3]. ['+cid+']',[{'id':cid}],'stop')
        self.assertEqual(result['unknown_citation_ids'],[]);self.assertEqual(result['citation_ids'],[cid])
        self.assertIn('1, 3',result['other_bracket_groups'])
    def test_unknown_canonical_citation_retained(self):
        checks=citation_checks('Claim [doc_invented_p0_c0]',[],'stop')
        self.assertEqual(checks['unknown_citation_ids'],['doc_invented_p0_c0'])
    def test_prepare_makes_zero_generation_calls_and_no_reserved_index(self):
        root,base,api,plan=self.prepared();folder=safe_run_folder(root,plan['run_folder'])
        self.assertEqual(api.calls,0)
        self.assertEqual(len(read(folder/'prepared.json')['documents']),5)
        self.assertTrue(validator(root).validate(base)['ready_for_model_execution'])
    def test_changed_context_refused(self):
        root,base,api,plan=self.prepared();folder=safe_run_folder(root,plan['run_folder'])
        path=folder/'prepared.json';data=read(path);data['contexts'][PILOT_IDS[0]][0]['text']='Changed'
        write(path,data)
        with self.assertRaises(ValueError):verify_plan(root,base,plan)
        self.assertEqual(api.calls,0)
    def test_changed_generator_code_refused(self):
        root,base,api,plan=self.prepared();(root/'src/evidence_api/store.py').write_text('changed')
        with self.assertRaises(ValueError):verify_plan(root,base,plan)
    def test_previous_embedding_lock_is_preserved_on_mismatch(self):
        import contextlib,io
        root,base=self.case_fixture();path=root/'config/local_embedding_lock.json';write(path,{'fingerprint_sha256':'different'})
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):prepare(root,base,FakeAPI(),FakeStore,fake_identity)
        self.assertEqual(read(path)['fingerprint_sha256'],'different');self.assertFalse((base/'execution_plan.json').exists())
    def test_all_48_attempts_then_resume_makes_zero_new_calls(self):
        import contextlib,io
        root,base,api,plan=self.prepared()
        with contextlib.redirect_stdout(io.StringIO()):
            result=run(root,base,api);run(root,base,api)
        self.assertEqual(api.calls,48);self.assertEqual(result['remaining_attempt_slots'],0)
        for cid in PILOT_IDS:
            selected=[p for p in api.payloads if json.loads(p['messages'][1]['content'])['question']==next(i['question'] for i in read(safe_run_folder(root,plan['run_folder'])/'prepared.json')['inputs'] if i['id']==cid)]
            groups=[json.loads(p['messages'][1]['content'])['passages'] for p in selected]
            self.assertEqual(len(groups),6)
            self.assertEqual(groups[0],list(reversed(groups[1])))
            self.assertEqual(groups[0],groups[2]);self.assertEqual(groups[0],groups[4])
    def test_failed_jobs_remain_in_saved_export(self):
        import contextlib,io
        root,base,api,plan=self.prepared();api.behavior='failure'
        with contextlib.redirect_stdout(io.StringIO()):result=run(root,base,api)
        folder=safe_run_folder(root,plan['run_folder'])
        self.assertEqual(result['status_counts']['generation_failed'],48)
        with zipfile.ZipFile(folder/'pilot_bundle.zip') as z:
            self.assertEqual(len([n for n in z.namelist() if n.endswith('stream.ndjson')]),48)
            self.assertIn('Partial ',z.read('report.md').decode())
    def test_interrupted_run_continues_with_other_jobs_only(self):
        import contextlib,io
        root,base,api,plan=self.prepared();api.behavior='interrupt'
        with contextlib.redirect_stdout(io.StringIO()):first=run(root,base,api)
        self.assertEqual(first['reserved_attempt_slots'],1);api.behavior='success'
        with contextlib.redirect_stdout(io.StringIO()):last=run(root,base,api)
        self.assertEqual(api.calls,48);self.assertEqual(last['status_counts']['interrupted_preserved'],1)
    def test_lost_process_partial_stream_is_recovered(self):
        job,context,folder,plan,api=self.tiny_job();run_job(job,context,folder,plan,api)
        record=read(folder/'record.json');record['complete']=False;record['answer']=''
        recovered=recover_partial(folder,record)
        self.assertEqual(recovered['status'],'interrupted_preserved');self.assertIn('Partial answer',recovered['answer'])
        self.assertEqual(api.calls,1)
    def test_remote_ollama_origin_refused(self):
        with self.assertRaises(ValueError):LocalAPI('https://example.com')


if __name__=='__main__':raise SystemExit(main())
