"""Frozen coverage regression: three cases, two orders, three pinned models.

Reuse the final coverage method without prompt changes. At most 18 attempts;
failed/partial outputs consume their slot. All controls and raw streams are kept.
This is a development regression, not the reserved 100-question evaluation.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from uuid import uuid4
import zipfile

ROOT=Path(__file__).resolve().parent
VERSION='frozen-coverage-regression-1.0.0'
ACTIVE='config/frozen_coverage_regression_v1.json'
MAX_CALLS=18
MODELS={
 'qwen3:8b':'500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41',
 'qwen3:4b-instruct-2507-q4_K_M':'0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0',
 'gemma3:4b':'68ceab7e468a31c988b44d5a4984a0e21f58c4f7158c6ce29c1804babac38df7'}
CODE=('run_frozen_coverage_regression.py','run_evidence_coverage_v2.py',
      'run_evidence_coverage_pilot.py','run_tool_assisted_pilot_v2.py',
      'evidence_reasoning_tools.py','run_rerank_comparison.py','run_real_document_pilot.py',
      'run_direct_answer_baseline.py','audit_pilot_retrieval.py')
LIMITS='Fixed three-case development regression, two orders, three models. All questions have been exposed during development. The smaller Qwen is the previously probed replacement artifact, not the original thinking-heavy Qwen 4B. Known IDs, valid schemas and required fields do not establish factual correctness or citation entailment. No prompt tuning after this run; report remaining failures. No fine-tuning or reserved-split evaluation.'


def pipeline(root):
    spec=importlib.util.spec_from_file_location('frozen_coverage_pipeline',root/'run_evidence_coverage_v2.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    _,core,comparison,_=module.libs(root)
    return module,core,comparison


def code_hashes(root):return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in CODE}


def source_inputs(root):
    method,core,_=pipeline(root)
    old_plan=core.read(root/method.ACTIVE)
    folder,prepared=method.verify(root,old_plan)
    summary=core.read(folder/'summary.json')
    if len(summary['records'])!=6 or any(r['pipeline_status']=='not_started' for r in summary['records']):raise ValueError('Expected the completed six-row final coverage diagnostic.')
    provenance={'source_plan_sha256':core.sha((folder/'plan.json').read_bytes()),
                'source_summary_sha256':core.sha((folder/'summary.json').read_bytes()),
                'source_bundle_sha256':core.sha((folder/'evidence_coverage_v2_bundle.zip').read_bytes()),
                'benchmark_freeze_sha256':old_plan['provenance']['benchmark_freeze_sha256']}
    return prepared,provenance,core.read(folder/'models.json'),summary['records']


def inspect_models(api,core):
    """Pin installed weights, native templates and server version without calls."""
    tags=api.json('/api/tags').get('models',[])
    result={'ollama_version':api.json('/api/version'),'models':{}}
    for model,digest in MODELS.items():
        matches=[m for m in tags if m.get('name',m.get('model'))==model]
        if len(matches)!=1 or matches[0].get('digest')!=digest:raise ValueError('Missing model or unexpected digest: '+model)
        show=api.json('/api/show',{'model':model})
        lengths=[v for k,v in show.get('model_info',{}).items() if k.endswith('.context_length') and type(v) is int]
        if not lengths or max(lengths)<32768:raise ValueError('Insufficient advertised context: '+model)
        if 'completion' not in show.get('capabilities',[]):raise ValueError('Completion capability is not advertised: '+model)
        thinking=show.get('thinking')
        if isinstance(thinking,dict) and isinstance(thinking.get('values'),list) and False not in thinking['values']:raise ValueError('think=false is explicitly excluded: '+model)
        result['models'][model]={'digest':digest,'show':show,'show_identity':core.show_identity(show),
                                'thinking_metadata':thinking,
                                'limits':'Absence of thinking metadata is not a guarantee of no thinking; the actual output is checked and a violating model is blocked.'}
    return result


def jobs_for(method,prepared,core):
    jobs=[]
    for model in MODELS:
        for job in method.jobs_for(prepared,core):
            jobs.append({**job,'model':model,'id':core.digest([VERSION,model,job['case_id'],job['order']])[:24]})
    return jobs


def prepare(root,api,loader=source_inputs):
    if (root/ACTIVE).exists():
        plan=json.loads((root/ACTIVE).read_text());verify(root,plan,loader);print('Existing frozen regression verified. Generation calls: 0.');return plan
    method,core,comparison=pipeline(root)
    prepared,provenance,old_native,controls=loader(root)
    native=inspect_models(api,core)
    if native['ollama_version']!=old_native['ollama_version'] or native['models']['qwen3:8b']['show_identity']!=old_native['show_identity']:raise ValueError('Qwen 8B template/server differs from the final diagnostic.')
    jobs=jobs_for(method,prepared,core)
    if len(jobs)!=18 or len({j['id'] for j in jobs})!=18:raise ValueError('Unexpected regression matrix.')
    for job in jobs:
        context=method.context_for(prepared,job);question,_=method.generation_question(job,context)
        core.budget_for(core.messages_for(method.PROMPT,question,context),comparison.OPTIONS)
    folder=root/'results'/('frozen_coverage_regression_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]);folder.mkdir(parents=True)
    for name,data in [('prepared.json',prepared),('models.json',native),('prior_controls.json',controls)]:core.write(folder/name,data)
    for name in CODE:
        dest=folder/'code_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,dest)
    files={str(p.relative_to(folder)):core.sha(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}
    plan={'version':VERSION,'pipeline_version':method.VERSION,'max_generation_attempts':MAX_CALLS,
          'models':MODELS,'generation_options':comparison.OPTIONS,'prompt':method.PROMPT,'requirements':method.REQUIREMENTS,
          'think':False,'stream':True,'response_format':'per-input JSON schema','fine_tuning':False,
          'folder':str(folder.relative_to(root)),'ollama_host':api.host,'prepared_files':files,
          'code_hashes':code_hashes(root),'provenance':provenance,'limits':LIMITS}
    core.write(folder/'plan.json',plan);core.write(root/ACTIVE,plan);export(folder,plan,prepared,method,core)
    print('Prepared: 3 cases × 2 orders × 3 models = 18 maximum attempts. Generation calls: 0.');print('Saved:',folder)
    return plan


def verify(root,plan,loader=source_inputs):
    if code_hashes(root)!=plan['code_hashes']:raise ValueError('Code changed after regression preparation.')
    method,core,comparison=pipeline(root)
    settings={'version':VERSION,'pipeline_version':method.VERSION,'max_generation_attempts':MAX_CALLS,
              'models':MODELS,'generation_options':comparison.OPTIONS,'prompt':method.PROMPT,'requirements':method.REQUIREMENTS,
              'think':False,'stream':True,'response_format':'per-input JSON schema','fine_tuning':False,'limits':LIMITS}
    if any(plan.get(k)!=v for k,v in settings.items()):raise ValueError('Frozen regression settings changed.')
    folder=(root/plan['folder']).resolve()
    if not folder.is_relative_to((root/'results').resolve()):raise ValueError('Unsafe results path.')
    if core.read(folder/'plan.json')!=plan or core.read(root/ACTIVE)!=plan:raise ValueError('Frozen plan copies differ.')
    for name,expected in plan['prepared_files'].items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder) or core.sha(path.read_bytes())!=expected:raise ValueError('Frozen input changed: '+name)
    prepared,provenance,_,controls=loader(root)
    if prepared!=core.read(folder/'prepared.json') or provenance!=plan['provenance'] or controls!=core.read(folder/'prior_controls.json'):raise ValueError('Final diagnostic inputs changed.')
    return folder,prepared


def export(folder,plan,prepared,method,core):
    for path in (folder/'jobs').glob('*/answer/record.json'):
        record=core.read(path)
        if not record.get('complete'):core.write(path,core.recover_partial(path.parent,record))
    rows=[];calls=0
    for job in jobs_for(method,prepared,core):
        base=folder/'jobs'/job['id'];state=core.read(base/'state.json') if (base/'state.json').exists() else {}
        record=core.read(base/'answer/record.json') if (base/'answer/record.json').exists() else None
        calls+=int(record is not None)
        rows.append({**job,'pipeline_status':state.get('status','not_started'),'state':state,
                     'generation_status':record['status'] if record else 'not_attempted',
                     'raw_answer':record['answer'] if record else None,'candidate_answer':state.get('rendered_answer'),
                     'whole_answer_verified':False})
    result={'version':VERSION,'pipeline_version':method.VERSION,'reserved_attempt_slots':calls,'max_generation_attempts':MAX_CALLS,
            'pipeline_status_counts':dict(Counter(r['pipeline_status'] for r in rows)),
            'by_model':{model:dict(Counter(r['pipeline_status'] for r in rows if r['model']==model)) for model in MODELS},
            'records':rows,'semantic_accuracy':None}
    core.write(folder/'summary.json',result)
    lines=['# Frozen coverage regression','',LIMITS,'',f'Recorded attempts: {calls}/18.','']
    for r in rows:lines+=['## '+r['model']+' / '+r['case_id']+' / '+r['order'],'',r['pipeline_status'],'',r['candidate_answer'] or '(No rendered answer; see saved state/raw output.)','']
    (folder/'FROZEN_REGRESSION.md').write_text('\n'.join(lines))
    target=folder/'frozen_regression_bundle.zip';tmp=folder/'frozen_regression_bundle.tmp'
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path not in (target,tmp) and path.suffix!='.lock':z.write(path,str(path.relative_to(folder)))
    tmp.replace(target);return result


def run(root,api,loader=source_inputs):
    if not (root/ACTIVE).exists():raise ValueError('Run --prepare first.')
    plan=json.loads((root/ACTIVE).read_text());folder,prepared=verify(root,plan,loader)
    method,core,_=pipeline(root);expected=core.read(folder/'models.json')
    if api.host!=plan['ollama_host']:raise ValueError('Ollama origin changed.')
    def native_check():
        current=inspect_models(api,core)
        if current!=expected:raise ValueError('Model metadata or Ollama version changed during regression.')
    blocked_path=folder/'blocked_models.json'
    with core.process_lock(folder/'frozen_regression.lock'):
        native_check();export(folder,plan,prepared,method,core)
        blocked=core.read(blocked_path) if blocked_path.exists() else {}
        try:
            for index,job in enumerate(jobs_for(method,prepared,core),1):
                base=folder/'jobs'/job['id'];state_path=base/'state.json'
                if state_path.exists() and core.read(state_path).get('terminal'):continue
                if job['model'] in blocked:
                    core.write(state_path,{'terminal':True,'status':'model_protocol_blocked_not_attempted','reason':blocked[job['model']]});continue
                if not (base/'answer/record.json').exists() and len(list((folder/'jobs').glob('*/answer/record.json')))>=MAX_CALLS:raise ValueError('Regression attempt budget exhausted.')
                print(f"[{index}/18] {job['model']} · {job['case_id']} · {job['order']}",flush=True)
                context=method.context_for(prepared,job);native_check()
                answer=method.run_structured_job(core,job,context,base/'answer',plan,api)
                native_check()
                thinking=bool(answer.get('thinking') or re.search(r'</?think\b',answer.get('answer',''),re.I))
                if thinking:
                    blocked[job['model']]='Unexpected thinking output with think=false; raw output retained. Further calls for this model were not attempted.'
                    core.write(blocked_path,blocked)
                if answer['status']=='output_recorded' and not thinking and not answer.get('stop_batch'):
                    try:
                        text,parts=method.render_answer(answer['answer'],job['case_id'],context)
                        checks=core.citation_checks(text,context,'stop')
                        state={'terminal':True,'status':'blocked_by_check' if checks['mechanical_issues'] else 'candidate_unverified',
                               'rendered_answer':text,'structural_checks':checks,'whole_answer_verified':False}
                        core.write(base/'structured_answer.json',parts)
                        core.write(base/'selected_evidence.json',{key:[c for c in context if c['id'] in part['evidence_ids']] for key,part in parts['parts'].items()})
                    except (ValueError,TypeError,KeyError) as exc:state={'terminal':True,'status':'structure_failed_preserved','error':str(exc)}
                else:state={'terminal':True,'status':'model_protocol_violation_preserved' if thinking else 'generation_failed_preserved'}
                core.write(state_path,state);export(folder,plan,prepared,method,core)
                if answer.get('interrupted') or answer.get('stop_batch'):break
        finally:result=export(folder,plan,prepared,method,core)
    print('Recorded attempts:',result['reserved_attempt_slots'],'/ 18');print('By model:',result['by_model']);print('Saved:',folder/'frozen_regression_bundle.zip')
    return result


class FakeAPI:
    host='http://localhost:11434'
    def __init__(self):self.calls=0;self.payloads=[];self.mode='valid';self.interrupt_at=-1
    def json(self,path,payload=None):
        if path=='/api/tags':return {'models':[{'name':m,'digest':h} for m,h in MODELS.items()]}
        if path=='/api/version':return {'version':'fixture'}
        if path=='/api/show':return {'model_info':{'fixture.context_length':32768},'capabilities':['completion'],'template':'fixture','thinking':None}
        raise AssertionError(path)
    def lines(self,payload):
        self.calls+=1;self.payloads.append(copy.deepcopy(payload))
        if self.calls==self.interrupt_at:raise KeyboardInterrupt()
        parts={k:{'status':'answered','text':'Supported answer.','evidence_ids':['doc_0123456789abcdef0123_p0_c0']} for k in payload['format']['properties']['parts']['required']}
        text=json.dumps({'parts':parts})+('}' if self.mode=='bad_json' else '')
        thinking='unexpected' if self.mode=='q4_thinking' and payload['model']==list(MODELS)[1] else ''
        yield json.dumps({'model':payload['model'],'message':{'content':text,'thinking':thinking},'done':True,'done_reason':'stop'}).encode()+b'\n'


class Tests(unittest.TestCase):
    def fixture(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);root=Path(td.name)
        for name in CODE:shutil.copy2(ROOT/name,root/name)
        method,core,_=pipeline(root)
        prepared={'inputs':[{'id':cid,'question':'Question','source_ids':['s']} for cid in method.CASES],
                  'contexts':{cid:[{'id':'doc_0123456789abcdef0123_p0_c0','source':'s.txt','page':0,'text':'Evidence'}] for cid in method.CASES}}
        api=FakeAPI();native=inspect_models(api,core)
        old={'ollama_version':native['ollama_version'],'show_identity':native['models']['qwen3:8b']['show_identity']}
        def loader(*args):return copy.deepcopy(prepared),{'fixture':True},copy.deepcopy(old),[]
        return root,api,prepared,loader
    def ready(self):
        from contextlib import redirect_stdout
        root,api,prepared,loader=self.fixture()
        with redirect_stdout(io.StringIO()):plan=prepare(root,api,loader)
        return root,api,prepared,loader,plan
    def execute(self,root,api,loader):
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):return run(root,api,loader)
    def test_prepare_no_generation(self):self.assertEqual(self.ready()[1].calls,0)
    def test_18_calls_then_resume_zero(self):
        root,api,_,loader,_=self.ready();result=self.execute(root,api,loader);self.execute(root,api,loader)
        self.assertEqual(api.calls,18);self.assertEqual(result['pipeline_status_counts'],{'candidate_unverified':18})
    def test_bad_json_preserved_without_retry(self):
        root,api,_,loader,_=self.ready();api.mode='bad_json';result=self.execute(root,api,loader);self.execute(root,api,loader)
        self.assertEqual(api.calls,18);self.assertEqual(result['pipeline_status_counts'],{'structure_failed_preserved':18})
    def test_interrupted_attempt_not_retried(self):
        root,api,_,loader,_=self.ready();api.interrupt_at=1;self.execute(root,api,loader);r=self.execute(root,api,loader)
        self.assertEqual(api.calls,18);self.assertEqual(r['pipeline_status_counts']['generation_failed_preserved'],1)
    def test_thinking_model_blocked_and_other_models_continue(self):
        root,api,_,loader,_=self.ready();api.mode='q4_thinking';r=self.execute(root,api,loader)
        self.assertEqual(api.calls,13);self.assertEqual(r['pipeline_status_counts']['model_protocol_blocked_not_attempted'],5)
        self.assertEqual(r['by_model']['gemma3:4b'],{'candidate_unverified':6})
    def test_changed_code_refused(self):
        root,_,_,loader,plan=self.ready();(root/'run_evidence_coverage_v2.py').write_text('changed')
        with self.assertRaises(ValueError):verify(root,plan,loader)
    def test_changed_evidence_refused(self):
        root,_,data,loader,plan=self.ready();data['contexts'][list(data['contexts'])[0]][0]['text']='changed'
        with self.assertRaises(ValueError):verify(root,plan,loader)
    def test_wrong_digest_refused(self):
        root,api,_,_=self.fixture();_,core,_=pipeline(root);old=api.json
        def changed(path,payload=None):
            r=old(path,payload)
            if path=='/api/tags':r['models'][0]['digest']='changed'
            return r
        api.json=changed
        with self.assertRaises(ValueError):inspect_models(api,core)
        self.assertEqual(api.calls,0)
    def test_matrix_unique_and_balanced(self):
        root,_,data,_=self.fixture();method,core,_=pipeline(root);jobs=jobs_for(method,data,core)
        self.assertEqual(len(jobs),18);self.assertEqual(len({j['id'] for j in jobs}),18)
        self.assertEqual(Counter(j['model'] for j in jobs),{m:6 for m in MODELS})
    def test_payload_only_model_changes_between_models(self):
        root,api,_,loader,_=self.ready();self.execute(root,api,loader)
        controls={}
        for p in api.payloads:
            content=json.dumps({k:v for k,v in p.items() if k!='model'},sort_keys=True)
            controls.setdefault(p['model'],[]).append(content)
        self.assertTrue(all(values==controls['qwen3:8b'] for values in controls.values()))
    def test_no_gold_inputs_and_schema_saved(self):
        root,api,_,loader,plan=self.ready();self.execute(root,api,loader)
        stored=[json.loads(p.read_text())['request'] for p in (root/plan['folder']/'jobs').glob('*/answer/record.json')]
        self.assertEqual(sorted(json.dumps(p,sort_keys=True) for p in stored),sorted(json.dumps(p,sort_keys=True) for p in api.payloads))
        for p in stored:self.assertNotIn('reference_answer',json.dumps(p));self.assertIs(p['think'],False);self.assertIn('format',p)
    def test_frozen_source_bundle_filename(self):
        from unittest.mock import patch
        root,_,prepared,_=self.fixture();method,core,comparison=pipeline(root)
        folder=root/'results/final_diagnostic';folder.mkdir(parents=True)
        old_plan={'provenance':{'benchmark_freeze_sha256':'fixture'}}
        core.write(root/method.ACTIVE,old_plan);core.write(folder/'plan.json',old_plan)
        core.write(folder/'summary.json',{'records':[{'pipeline_status':'candidate_unverified'} for _ in range(6)]});core.write(folder/'models.json',{})
        (folder/'evidence_coverage_v2_bundle.zip').write_bytes(b'frozen final bundle')
        fake=SimpleNamespace(ACTIVE=method.ACTIVE,verify=lambda *_:(folder,prepared))
        with patch(__name__+'.pipeline',return_value=(fake,core,comparison)):
            _,provenance,_,_=source_inputs(root)
        self.assertEqual(provenance['source_bundle_sha256'],core.sha(b'frozen final bundle'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--self-test',action='store_true');group.add_argument('--prepare',action='store_true');group.add_argument('--run',action='store_true');args=parser.parse_args()
    if not (ROOT/'pyproject.toml').exists():parser.error('Save the script in the existing project root.')
    try:
        if not args.self_test and (ROOT/ACTIVE).exists() and code_hashes(ROOT)!=json.loads((ROOT/ACTIVE).read_text())['code_hashes']:raise ValueError('Code changed after preparation.')
        _,core,_=pipeline(ROOT)
        if args.self_test:
            stream=io.StringIO();r=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
            path=ROOT/'results'/('frozen_regression_selftest_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8])/'selftest.json'
            core.write(path,{'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'model_calls':0,'script_sha256':core.sha(Path(__file__).read_bytes()),'log':stream.getvalue()})
            print(stream.getvalue());print('Saved:',path);return 0 if r.wasSuccessful() else 1
        passed=any(r.get('script_sha256')==core.sha(Path(__file__).read_bytes()) and r['tests']>=12 and r['failures']==r['errors']==0 for p in (ROOT/'results').glob('frozen_regression_selftest_*/selftest.json') for r in [core.read(p)])
        if not passed:raise ValueError('Run --self-test successfully for this exact script first.')
        import os
        api=core.LocalAPI(os.environ.get('OLLAMA_HOST','http://localhost:11434'))
        if args.prepare:
            with core.process_lock(ROOT/'results/frozen_regression_prepare.lock'):prepare(ROOT,api)
        else:run(ROOT,api)
        return 0
    except Exception as exc:
        path=ROOT/'results'/('frozen_regression_error_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]+'.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'error':f'{type(exc).__name__}: {exc}'},indent=2)+'\n');print(type(exc).__name__+': '+str(exc));print('Saved error:',path);return 1


if __name__=='__main__':raise SystemExit(main())
