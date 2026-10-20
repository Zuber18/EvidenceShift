"""Exercise the installed upload/search API and frozen candidate generator.

Gold evidence requirements are measured after full-corpus semantic search.
They never influence retrieval, candidate prompts or production delivery.
"""
import copy
import csv
import hashlib
import importlib.metadata
import json
import platform
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from . import grounded as base,fresh_candidates as candidates
from .e2e_fixtures import make_files

VERSION='document-e2e-1.0.0'
normalize=lambda text:' '.join(text.split())


@contextmanager
def real_backend(root):
    from fastapi.testclient import TestClient
    from .app import build_engine,create_app
    engine=build_engine(data_root=root)
    with TestClient(create_app(engine=engine)) as api:
        yield SimpleNamespace(api=api,profile=engine.store.profile)


def expected_body(fixture):
    return fixture['expected_text'].strip().split('\n\n',1)[1]


def check_document(fixture,summary,chunks):
    raw=fixture['path'].read_bytes();sha=hashlib.sha256(raw).hexdigest()
    doc_id='doc_'+hashlib.sha256(raw+('.'+fixture['format']).encode()).hexdigest()[:20]
    body=normalize(expected_body(fixture))
    metadata_ok=all(c.get('document_id')==doc_id and c.get('source')==fixture['filename'] and c.get('sha256')==sha for c in chunks)
    ids_ok=all(c.get('id')==f"{doc_id}_p{c.get('page')}_c{c.get('chunk')}" for c in chunks)
    pages_ok=all(c.get('page') in ([1,2] if fixture['format']=='pdf' else [0]) for c in chunks)
    body_hits=[c for c in chunks if body in normalize(c['text'])]
    body_page_ok=bool(body_hits) and all(c['page']==(2 if fixture['format']=='pdf' else 0) for c in body_hits)
    checks={'summary_document_id_matches_bytes':summary.get('document_id')==doc_id,
            'nonempty_chunks':bool(chunks),'stable_chunk_ids':ids_ok,
            'source_and_hash_metadata_match':metadata_ok,'page_metadata_valid':pages_ok,
            'operative_body_extracted_on_expected_page':body_page_ok}
    return checks


def evidence_coverage(required,fixtures,documents,hits):
    result=[]
    for fixture_id in required:
        fixture=fixtures[fixture_id];doc_id=documents[fixture_id]['document_id']
        marker=normalize(expected_body(fixture))
        matches=[h['id'] for h in hits if h.get('document_id')==doc_id and marker in normalize(h['text'])]
        result.append({'fixture_id':fixture_id,'document_id':doc_id,'marker':expected_body(fixture),
                       'retrieved_chunk_ids':matches,'covered':bool(matches)})
    return {'requirements':result,'required_units':len(required),'covered_units':sum(x['covered'] for x in result),
            'all_required_units_found':all(x['covered'] for x in result) if required else None,
            'recall':sum(x['covered'] for x in result)/len(required) if required else None,
            'meaning':'Exact normalized operative-text coverage in retrieved chunks; not a semantic relevance or answer-correctness score.'}


def get_json(response):
    response.raise_for_status();return response.json()


def run_suite(root,output,client,backend_factory=real_backend):
    root=Path(root)
    raw=(root/'evaluation/fresh_baseline_cases.json').read_bytes();plan=json.loads(raw)
    requirements=json.loads((root/'evaluation/document_e2e_requirements.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=requirements['fresh_plan_sha256']:raise ValueError('Fresh evaluation plan changed; preserve the frozen plan before this run.')
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=plan['baseline_module_sha256']:raise ValueError('Preserved baseline module changed.')
    if requirements['version']!=VERSION or plan['experiment_version']!=candidates.VERSION:raise ValueError('Experiment versions differ.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]
    folder=Path(output)/('document_e2e_'+stamp);folder.mkdir(parents=True)
    result={'complete':False,'experiment_version':VERSION,'expected_answer_records':len(plan['cases'])*3,
            'document_checks':[],'format_checks':[],'records':[],'rows':[],
            'factual_correctness':'not_automatically_scored','production_delivery':False}
    setup={'experiment_version':VERSION,'plan':plan,'requirements':requirements,
           'model':plan['model'],'options':plan['options'],'think':False,'top_k':requirements['top_k'],
           'scope':'In-process real /documents and /search API routes, isolated per-format test indexes; frozen candidate generation. No HTTP server, demo or hosted-network test.',
           'python':platform.python_version(),'platform':platform.platform(),'packages':{},'source_module_sha256':{},'profiles':{}}
    for name in ['fastapi','httpx','pypdf','python-docx','chromadb','langchain-text-splitters','sentence-transformers','ollama']:
        try:setup['packages'][name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:setup['packages'][name]=None
    for name in ['app.py','store.py','ingestion.py','word_documents.py','grounded.py','fresh_candidates.py','document_e2e.py','e2e_fixtures.py']:
        path=Path(__file__).parent/name
        if path.exists():setup['source_module_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (folder/'frozen_plan.json').write_bytes(raw)
    (folder/'requirements.json').write_text(json.dumps(requirements,indent=2),encoding='utf-8')
    def checkpoint():
        (folder/'setup.json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
        temp=folder/'results.tmp';temp.write_text(json.dumps(result,indent=2),encoding='utf-8');temp.replace(folder/'results.json')
        if result['rows']:
            with (folder/'results.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(result['rows'][0]));writer.writeheader();writer.writerows(result['rows'])
    checkpoint()
    try:
        setup['model_inventory']=client.list().model_dump(mode='json')
        if plan['model'] not in {x['model'] for x in setup['model_inventory'].get('models',[])}:raise ValueError('Frozen model is not installed: '+plan['model'])
        fixtures=make_files(plan,folder/'fixtures')
        for fmt in requirements['formats']:
            print('Format:',fmt,flush=True)
            format_fixtures=[f for f in fixtures if f['format']==fmt]
            by_id={f['fixture_id']:f for f in format_fixtures};documents={}
            try:
                with backend_factory(folder/'indexes'/fmt) as backend:
                    profile=backend.profile;setup['profiles'][fmt]=profile
                    expected={'embedding_model':'sentence-transformers/all-MiniLM-L6-v2','chunk_tokens':180,'overlap_tokens':30,'splitter':'recursive-huggingface-token-v1'}
                    if any(profile.get(k)!=v for k,v in expected.items()):raise ValueError('Retrieval profile differs from the existing frozen MiniLM pipeline.')
                    api=backend.api
                    for fixture in format_fixtures:
                        print('  Upload:',fixture['filename'],flush=True)
                        raw_file=fixture['path'].read_bytes()
                        summary=get_json(api.post('/documents',files={'file':(fixture['filename'],raw_file,'application/octet-stream')}))
                        documents[fixture['fixture_id']]=summary
                        chunks=get_json(api.get('/documents/'+summary['document_id']+'/chunks',params={'limit':200,'offset':0}))
                        checks=check_document(fixture,summary,chunks)
                        result['document_checks'].append({'format':fmt,'fixture_id':fixture['fixture_id'],'filename':fixture['filename'],
                            'file_sha256':hashlib.sha256(raw_file).hexdigest(),'ingestion':summary,'chunks':chunks,'checks':checks,'passed':all(checks.values())})
                        checkpoint()
                    first=format_fixtures[0];again=get_json(api.post('/documents',files={'file':(first['filename'],first['path'].read_bytes(),'application/octet-stream')}))
                    catalog=get_json(api.get('/documents'))
                    dedup_ok=again.get('deduplicated') is True and again['document_id']==documents[first['fixture_id']]['document_id']
                    size_ok=len(catalog)==len(format_fixtures)
                    format_check={'format':fmt,'deduplication_matches':dedup_ok,'expected_document_count_matches':size_ok,'documents':catalog}
                    result['format_checks'].append(format_check);checkpoint()
                    if not dedup_ok or not size_ok or any(not d['passed'] for d in result['document_checks'] if d['format']==fmt):raise ValueError('Ingestion/provenance checks failed; generation for this format was not attempted.')
                    for case in plan['cases']:
                        print('  Question:',case['id'],flush=True)
                        hits=[]
                        try:
                            # Search the entire format corpus. No gold IDs, case filter or expected-answer hint is supplied.
                            hits=get_json(api.post('/search',json={'question':case['question'],'top_k':requirements['top_k']}))['passages']
                            for hit in hits:
                                known=next((d for d in result['document_checks'] if d['format']==fmt and d['ingestion']['document_id']==hit['document_id']),None)
                                original=next((c for c in known['chunks'] if c['id']==hit['id']),None) if known else None
                                if original is None or any(hit[k]!=original[k] for k in original):raise ValueError('Search result differs from the indexed source snapshot.')
                            coverage=evidence_coverage(requirements['required_fixture_ids'][case['id']],by_id,documents,hits)
                            answer,bundle=candidates.run(case['question'],hits,client,plan['model'],plan['options'],folder/'runs',
                                                        {'case_id':case['id'],'format':fmt,'context_origin':'actual_full_corpus_semantic_search'})
                            record={'format':fmt,'case_id':case['id'],'question':case['question'],'retrieved':hits,'retrieval_coverage':coverage,
                                    'source_review_criteria':case['source_review_criteria'],'result':answer,'bundle':str(bundle.relative_to(folder))}
                        except Exception as exc:
                            record={'format':fmt,'case_id':case['id'],'question':case['question'],'retrieved':hits,'error':f'{type(exc).__name__}: {exc}'}
                        result['records'].append(record)
                        answer=record.get('result',{});coverage=record.get('retrieval_coverage',{})
                        result['rows'].append({'format':fmt,'case_id':case['id'],'status':answer.get('status','search_or_generation_error'),
                            'retrieved_chunks':len(record.get('retrieved',[])),'required_evidence_units':coverage.get('required_units'),
                            'covered_evidence_units':coverage.get('covered_units'),'all_required_evidence_found':coverage.get('all_required_units_found'),
                            'answer':answer.get('candidate_answer'),'calls':sum(s['status']!='skipped_input' for s in answer.get('stages',[])),
                            'seconds':round(sum(s.get('seconds',0) for s in answer.get('stages',[])),2),
                            'factual_correctness':'not_automatically_scored','error':record.get('error') or answer.get('error')})
                        checkpoint()
            except Exception as exc:
                result.setdefault('format_errors',[]).append({'format':fmt,'error':f'{type(exc).__name__}: {exc}'})
                checkpoint()
    except Exception as exc:
        result['fatal_error']=f'{type(exc).__name__}: {exc}'
    result['complete']=True;result['all_expected_answer_records_present']=len(result['records'])==result['expected_answer_records'];checkpoint()
    lines=['# Document ingestion and retrieval evaluation','','Coverage is exact operative-text presence, not factual correctness. Answers are unapproved evaluation candidates.','',
           '| Format | Case | Required units found | Candidate status |','| --- | --- | --- | --- |']
    for row in result['rows']:
        coverage_text='not applicable' if row['required_evidence_units']==0 else str(row['covered_evidence_units'])+'/'+str(row['required_evidence_units'])
        lines.append(f"| {row['format']} | {row['case_id']} | {coverage_text} | {row['status']} |")
    for record in result['records']:
        lines += ['', '## '+record['format']+' / '+record['case_id'],'', 'Question: '+record['question'],'',
                  '> '+(record.get('result',{}).get('candidate_answer') or '(No mechanically valid candidate)').replace('\n','\n> '),'']
        for hit in record.get('retrieved',[]):lines+=['Source '+hit['source']+', page '+str(hit['page'])+', chunk '+hit['id']+':','', '> '+hit['text'].replace('\n','\n> '),'']
    if result.get('fatal_error'):lines+=['','Fatal error: '+result['fatal_error']]
    for error in result.get('format_errors',[]):lines+=['','Format error: '+error['format']+': '+error['error']]
    (folder/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import zipfile
    bundle=folder/'document_e2e_bundle.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob('*'):
            relative=path.relative_to(folder)
            if path.is_file() and path!=bundle and 'indexes' not in relative.parts and path.name!='grounded_bundle.zip':archive.write(path,relative)
    print('Answer records:',len(result['records']),'of',result['expected_answer_records']);print('Saved:',bundle.resolve())
    if result.get('fatal_error'):print('Fatal error:',result['fatal_error'])
    for issue in result.get('format_errors',[]):print('Format error:',issue['format'],issue['error'])
    return result,bundle
