"""Confirm frozen direct Qwen 3 8B on the reserved synthetic cases.

Save beside run_direct_answer_baseline.py and compare_evidence_models.py in the
existing project root. Run --self-test, then run without flags. No app edits.
16 model calls (8 questions x 2 passage orders) plus one zero-call control.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

VERSION='direct-confirmation-1.0.0'
MODEL='qwen3:8b'
PACKAGING_VALIDATION={
    'self_tests_passed':4,
    'controlled_saved_records':17,
    'controlled_generation_calls':16,
    'completed_resume_additional_calls':0,
    'frozen_prompt_options_no_schema_preserved':True,
    'exact_context_reversal_pairs':8,
    'actual_Ollama_executed_during_packaging':False,
    'semantic_reliability_established':False,
}

MODEL_DIGEST='500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41'
REQUIRED={
 'run_direct_answer_baseline.py':'935aa7576d165f4ee0c48f89acc8ad17799152c6211c3f30152744851cb4e8b3',
 'compare_evidence_models.py':'94e20274faf6dc789208a266f87cc616a930ffa413dc4035529ccaac33ee8bae',
}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def load_references(root):
    # All preflight checks precede any output creation or model call.
    for name,sha in REQUIRED.items():
        path=Path(root)/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError(name+' differs from the frozen evaluated file. No experiment started.')
    modules=[]
    for name in REQUIRED:
        spec=importlib.util.spec_from_file_location('_frozen_'+uuid4().hex,Path(root)/name)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules.append(module)
    return tuple(modules)


def make_jobs(cases):
    jobs=[]
    for case in cases:
        for order in ('retrieved','reversed'):
            jobs.append({'job_id':digest([MODEL,case['case_id'],order])[:20],
                         'model':MODEL,'case_id':case['case_id'],'question':case['question'],'order':order})
    jobs.append({'job_id':digest([MODEL,'confirmation_code_control'])[:20],
                 'model':MODEL,'case_id':cases[0]['case_id'],'question':cases[0]['question'],'order':'no_context'})
    return jobs


def enforce_lock(path,selection):
    if Path(path).exists():
        if digest(read_json(path))!=digest(selection):
            raise ValueError('Confirmation selection changed; existing lock and results preserved.')
    else:
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation prevents two processes silently replacing a selection.
        try:
            with Path(path).open('x',encoding='utf-8') as stream:json.dump(selection,stream,indent=2)
        except FileExistsError:enforce_lock(path,selection)


def export(folder):
    target=folder/'direct_confirmation_bundle.zip';temporary=folder/'export.tmp'
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path not in {target,temporary}:
                archive.write(path,path.relative_to(folder))
    temporary.replace(target)
    return target


def summarize(folder,jobs):
    records=[]
    for job in jobs:
        path=folder/'jobs'/job['job_id']/'record.json'
        if not path.exists():continue
        r=read_json(path)
        if not r.get('complete'):continue
        checks=r.get('checks',{})
        records.append({**job,'status':r['status'],'answer':r.get('candidate_answer'),
            'has_citations':checks.get('has_citations'),'citation_ids_valid':checks.get('citation_ids_valid'),
            'exact_abstention':checks.get('exact_abstention'),'error':r.get('error'),
            'factual_correctness':'not_automatically_scored'})
    write_json(folder/'summary.json',{'experiment_version':VERSION,'planned':len(jobs),'recorded':len(records),'records':records})
    if records:
        with (folder/'runs.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(records)
    (folder/'README.md').write_text('''# Frozen direct-answer confirmation

Eight reserved fictional Harbor Workshop cases, in both passage orders, plus
one zero-call control. The candidate is direct Qwen 3 8B with the exact previously
evaluated prompt, model digest, options and run function. Code snapshots, source
hashes, raw outputs, requests, timing, tokens and original citation checks are saved.
No prompt tuning, output repair or model judge is performed.

This is a fixed-context test. No new ingestion or semantic retrieval is measured.
The synthetic cases were reserved before model selection, but are not an
independently held-out benchmark. This is limited confirmation, not a production
approval. Existing role-reversal and false-abstention failures remain recorded.

Selection is locked before generation under results/direct_confirmation_selection.json.
Completed failures are retained on resume. Interrupted records are preserved under
interruptions/ before a new attempt. An optional Ollama version observation is
recorded when the installed client supports it; inability to read it is logged.

Original checks use a strict single-ID bracket parser. Comma-grouped citations
may be flagged as unknown despite containing known individual IDs. This existing
parser limitation is retained to keep the evaluated run function frozen; semantic
support must be assessed separately. See runs.csv and the original trial records.
''',encoding='utf-8')
    return export(folder)


def execute(root,client,resume=None):
    root=Path(root).resolve();baseline,matrix=load_references(root)
    cases=matrix.cases_for(root,'confirmation')
    jobs=make_jobs(cases)
    inventory=client.list().model_dump(mode='json')
    known={m.get('model',m.get('name')):m.get('digest') for m in inventory.get('models',[])}
    if known.get(MODEL)!=MODEL_DIGEST:
        raise ValueError('Installed Qwen 3 8B digest differs from the reviewed candidate or is missing. No calls made.')
    selection={'candidate':'frozen direct Qwen 3 8B','model':MODEL,'model_digest':MODEL_DIGEST,
               'prompt_sha256':digest(baseline.PROMPT),'options':baseline.OPTIONS,'think':False,
               'cases_sha256':digest(cases),'required_source_hashes':REQUIRED}
    plan={'experiment_version':VERSION,'selection':selection,'prompt':baseline.PROMPT,
          'cases':cases,'jobs':jobs,'confirmation_cases_only':True,
          'order_semantics':'retrieved means canonical reserved paragraph order; no retrieval search is executed',
          'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'automatic_semantic_accuracy_scoring':False,
          'known_development_failures':['Reversed Jim-to-Della gift role reversal','Both why-question trials incorrectly abstained'],
          'scope':'Reserved synthetic fixed-context confirmation; not independent held-out evaluation.'}
    if resume:
        folder=Path(resume).resolve()
        if not folder.is_relative_to(root/'results'):raise ValueError('Resume folder must be inside this project results/.')
        if digest(read_json(folder/'plan.json'))!=digest(plan):raise ValueError('Resume plan or code changed; results preserved.')
    enforce_lock(root/'results/direct_confirmation_selection.json',selection)
    if not resume:
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]
        folder=root/'results'/('direct_confirmation_'+stamp);folder.mkdir(parents=True)
        write_json(folder/'plan.json',plan);write_json(folder/'model_inventory.json',inventory)
        write_json(folder/'runner_validation.json',PACKAGING_VALIDATION)
        snapshot=folder/'source_snapshot';snapshot.mkdir()
        for name in REQUIRED:(snapshot/name).write_bytes((root/name).read_bytes())
        (snapshot/'run_direct_confirmation.py').write_bytes(Path(__file__).read_bytes())
        try:
            version=client.version()
            observation=version.model_dump(mode='json') if hasattr(version,'model_dump') else dict(version)
        except Exception as exc:observation={'unavailable':f'{type(exc).__name__}: {exc}'}
        write_json(folder/'ollama_version_observation.json',observation)
    by_id={case['case_id']:case for case in cases}
    print('Results:',folder,flush=True);print('Planned: 16 generation calls and 1 zero-call control.',flush=True)
    summarize(folder,jobs)
    try:
        for i,job in enumerate(jobs,1):
            trial=folder/'jobs'/job['job_id'];path=trial/'record.json'
            if path.exists():
                old=read_json(path)
                if old.get('complete'):
                    print(f'[{i}/{len(jobs)}] Completed saved trial retained',flush=True);continue
                prior=folder/'interruptions'/(job['job_id']+'_'+uuid4().hex[:8])
                prior.parent.mkdir(parents=True,exist_ok=True);trial.rename(prior)
            trial.mkdir(parents=True)
            context=copy.deepcopy(by_id[job['case_id']]['context'])
            if job['order']=='reversed':context.reverse()
            elif job['order']=='no_context':context=[]
            print(f'[{i}/{len(jobs)}] {job["order"]}: {job["question"]}',flush=True)
            result=baseline.run_one(job,context,client,trial)
            summarize(folder,jobs);print('  '+result['status'],flush=True)
    finally:
        bundle=summarize(folder,jobs);print('Saved ZIP:',bundle,flush=True)
        print('Resume: python run_direct_confirmation.py --resume "'+str(folder)+'"',flush=True)
    return folder


class Tests(unittest.TestCase):
    def test_fixed_model_and_matrix_size(self):
        cases=[{'case_id':str(i),'question':'Question?'} for i in range(8)]
        jobs=make_jobs(cases)
        self.assertEqual(len(jobs),17);self.assertEqual(len({j['job_id'] for j in jobs}),17)
        self.assertEqual(sum(j['order']!='no_context' for j in jobs),16)
        self.assertTrue(all(j['model']==MODEL for j in jobs))
    def test_lock_persists_and_rejects_change(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'lock.json';selection={'model':MODEL,'seed':42}
            enforce_lock(path,selection);enforce_lock(path,selection)
            with self.assertRaises(ValueError):enforce_lock(path,{**selection,'seed':43})
            self.assertEqual(read_json(path),selection)
    def test_export_keeps_failure_and_partial_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);write_json(folder/'failed.json',{'status':'failed'})
            write_json(folder/'interruptions/partial.json',{'status':'started'})
            with zipfile.ZipFile(export(folder)) as archive:
                self.assertIn('failed.json',archive.namelist());self.assertIn('interruptions/partial.json',archive.namelist())
                self.assertNotIn('direct_confirmation_bundle.zip',archive.namelist())
    def test_changed_reference_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in REQUIRED:(root/name).write_text('changed source')
            with self.assertRaises(ValueError):load_references(root)
            self.assertFalse((root/'results').exists())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--resume',type=Path)
    args=parser.parse_args()
    if args.self_test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
        return
    root=Path(__file__).resolve().parent
    load_references(root)
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'src'))
    from evidence_api.local_upload import ollama_client
    try:execute(root,ollama_client(),args.resume)
    except KeyboardInterrupt:
        print('Stopped; completed records and partial trials preserved.',flush=True);raise SystemExit(130)


if __name__=='__main__':main()
