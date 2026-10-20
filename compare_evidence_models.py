"""Compare installed local models and fixed evidence representations.

Run in the EvidenceShift project root:
    python compare_evidence_models.py --self-test
    python compare_evidence_models.py

No application files, prompts, retrieval indexes or prior results are changed.
Development: 3 installed models x 2 representations x 5 questions x 2 orders.
Confirmation: run only after selecting one configuration from development.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import sys
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

VERSION = 'model-matrix-1.0.0'
MODELS = ('qwen3:4b', 'qwen3:8b', 'gemma3:4b')
REPRESENTATIONS = ('passages', 'sentence_units')
OPTIONS = {'temperature': 0, 'seed': 42, 'num_ctx': 32768, 'num_predict': 2048}
EXPECTED_HANDLES_SHA = 'ad1d81245af840ba4821ab2f9d73259fb94531e64be82886e2150b96009e4244'
EXPECTED_BASE_SHA = '3b161a2531e4f76c0ab4983b6154cc7848a76b86c49a2453ec08faecaeda6eaf'
DEV_SUFFIXES = ('1f939d31', '2d84d462', '55b47cfd', 'e9abdb27', 'ae8d2dc4')
VALIDATION = {
    'self_tests_passed': 8,
    'controlled_development_records': 66,
    'controlled_development_generation_calls': 60,
    'resume_additional_generation_calls': 0,
    'controlled_confirmation_records': 17,
    'frozen_application_module_preserved': True,
    'passage_units_per_development_case': 19,
    'sentence_units_per_development_case': 224,
    'changed_confirmation_selection_refused': True,
    'actual_Ollama_executed_during_packaging': False,
    'semantic_accuracy_established': False,
}


# New fictional material reserved for confirmation. It is not used to choose a
# model or evidence representation and is not an independently held-out dataset.
CONFIRM_SOURCE = [
    'Fictional Harbor Workshop manual. Receipt L-84 confirms that a booking form arrived. '
    'It does not confirm approval. Only a separate approval notice confirms an approved booking.',
    'Saturday workshops begin at 09:30. Wednesday workshops begin at 18:15. '
    'The Wednesday time does not apply to Saturday workshops.',
    'Participants may request an email copy of the handout; requesting it is optional. '
    'Every participant must bring a membership card.',
    'Routine notes are kept for 30 days. Notes linked to an unresolved incident are kept '
    'for 90 days instead of 30 days.',
    'The blue notice replaces the green notice for this month. The green notice lists '
    'Monday pickup. The blue notice lists Wednesday pickup.',
    'Five practice kits were ordered. The first two kits are free. Each additional kit '
    'requires four workshop credits.',
    'Rina gave Omar a notebook. Omar gave Rina a calendar. Rina did not give Omar the calendar.',
    'The manual gives no birthplace or birth date for Rina and gives no information about '
    'the water resistance of any ticket.',
]
CONFIRM_QUESTIONS = (
    'Does receipt L-84 prove that the booking is approved?',
    'What time does a Saturday workshop begin?',
    'Must participants request an email copy, and what must they bring?',
    'Are notes linked to an unresolved incident deleted after 30 days?',
    'Which pickup day applies this month, and why?',
    'How many workshop credits are required for the five practice kits?',
    'What did Omar give Rina?',
    'Where was Rina born, and are the tickets waterproof?',
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def passage_units(context):
    """Same selection protocol, but each selectable unit is an entire passage."""
    numbers = {passage['id']: i+1 for i, passage in enumerate(sorted(context, key=lambda p: p['id']))}
    return [{'handle': f"U{numbers[p['id']]}", 'text': p['text'], 'passage_id': p['id'],
             'span_start': 0, 'span_end': len(p['text']), 'source': p['source'], 'page': p['page']}
            for p in context]


def load_engine(root, representation):
    """Isolate the experiment's factory override; never patch the imported app module."""
    if representation not in REPRESENTATIONS:
        raise ValueError('Unknown evidence representation')
    sys.path.insert(0, str(Path(root)/'src'))
    path = Path(root)/'src/evidence_api/source_handles.py'
    spec = importlib.util.spec_from_file_location('evidence_api._matrix_' + uuid4().hex, path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    # This private module instance uses the frozen prompts, schema construction,
    # span validation, budgeting, model call and trace persistence implementation.
    if representation == 'passages':
        engine.evidence_units = passage_units
    return engine


def check_project(root):
    expected = {'src/evidence_api/source_handles.py': EXPECTED_HANDLES_SHA,
                'src/evidence_api/grounded.py': EXPECTED_BASE_SHA}
    for name, sha in expected.items():
        path = Path(root)/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError(f'{name} differs from the frozen evaluated source. No experiment started.')


def cases_for(root, phase):
    if phase == 'development':
        source = read_json(Path(root)/'evaluation/handle_replay_evidence.json')['context']
        previous = read_json(Path(root)/'evaluation/local_upload_regression.json')['cases']
        cases = []
        for suffix in DEV_SUFFIXES:
            matches = [c for c in previous if c['id'].endswith(suffix)]
            if len(matches) != 1:
                raise ValueError('Expected one saved development question for ' + suffix)
            cases.append({'case_id': suffix, 'question': matches[0]['question'],
                          'context': copy.deepcopy(source)})
        return cases
    paragraphs = [{'id': f'confirm_p0_c{i}', 'document_id': 'confirm_harbor_workshop',
                   'source': 'fictional_harbor_workshop.txt', 'page': 0, 'chunk': i, 'text': text}
                  for i, text in enumerate(CONFIRM_SOURCE)]
    return [{'case_id': f'confirm_{i+1}', 'question': question, 'context': copy.deepcopy(paragraphs)}
            for i, question in enumerate(CONFIRM_QUESTIONS)]


def jobs_for(cases, models, representations):
    jobs = []
    for model in models:
        for representation in representations:
            for case in cases:
                for order in ('retrieved', 'reversed'):
                    jobs.append({'job_id': digest([model, representation, case['case_id'], order])[:20],
                                 'model': model, 'representation': representation,
                                 'case_id': case['case_id'], 'question': case['question'], 'order': order})
            jobs.append({'job_id': digest([model, representation, 'code_control'])[:20],
                         'model': model, 'representation': representation, 'case_id': cases[0]['case_id'],
                         'question': cases[0]['question'], 'order': 'no_context'})
    return jobs


def inventory_digests(inventory, models):
    known = {m.get('model', m.get('name')): m.get('digest') for m in inventory.get('models', [])}
    missing = [model for model in models if not known.get(model)]
    if missing:
        raise ValueError('Required models missing from Ollama: ' + ', '.join(missing) +
                         '. No models are downloaded automatically.')
    return {model: known[model] for model in models}


def assert_same_plan(saved, current):
    if digest(saved) != digest(current):
        raise ValueError('Resume plan, code, inputs, options or model digests changed; existing results preserved.')


def export(folder):
    target = folder/'model_matrix_bundle.zip'
    temporary = folder/'matrix_export.tmp'
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path not in {target, temporary} and path.name != 'grounded_bundle.zip':
                archive.write(path, path.relative_to(folder))
    temporary.replace(target)
    return target


def save_summary(folder, jobs):
    records = []
    for job in jobs:
        path = folder/'jobs'/job['job_id']/'record.json'
        if path.exists():
            record = read_json(path)
            records.append({**job, 'status': record['status'],
                            'answer': record.get('result', {}).get('candidate_answer'),
                            'error': record.get('error') or record.get('result', {}).get('error'),
                            'factual_correctness': 'not_automatically_scored'})
    write_json(folder/'summary.json', {'version': VERSION, 'planned': len(jobs),
                                     'recorded': len(records), 'records': records})
    if records:
        with (folder/'runs.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(records)
    (folder/'README.md').write_text(
        '# Fixed model and evidence representation comparison\n\n'
        'See plan.json for the fixed matrix, hashes and installed model digests.\n\n'
        'Every job retains its actual prompts, source mappings, raw output, model options and timing. '
        'Mechanical statuses are not semantic accuracy scores. No semantic model judge is used. '
        'The same question/context set is used across compared models and representations. '
        'The order variants reverse the supplied passage list; they are not new retrieval runs.\n\n'
        'The code controls make no generation calls. Failed completed jobs are retained and skipped '
        'on resume. An interrupted job without record.json is attempted again; its partial trace '
        'remains in the bundle. Confirmation cases are synthetic reserved cases, not an independently '
        'held-out benchmark.\n\n'
        'This is a fixed-context generation comparison. It does not measure retrieval, '
        'document ingestion or hosted behavior. Both representations use the same complete '
        'saved context. Source instructions and the ID-selection schema protocol are frozen, '
        'but allowed-ID lists and input token lengths differ by representation. Effective '
        'context/output options are retained in each trace. A single run per cell does not '
        'establish statistical significance or general accuracy.\n', encoding='utf-8')
    return export(folder)


def execute(root, phase, models, representations, client, resume=None):
    check_project(root)
    cases = cases_for(root, phase)
    inventory = client.list().model_dump(mode='json')
    model_digests = inventory_digests(inventory, models)
    engines = {representation: load_engine(root, representation) for representation in representations}
    code_hashes = {name: hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()
                   for name in ('src/evidence_api/source_handles.py', 'src/evidence_api/grounded.py')}
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    jobs = jobs_for(cases, models, representations)
    plan = {'version': VERSION, 'phase': phase, 'models': list(models),
            'representations': list(representations), 'options': OPTIONS, 'think': False,
            'model_digests': model_digests, 'code_hashes': code_hashes, 'runner_sha256': script_sha,
            'cases': cases, 'jobs': jobs, 'prompt': next(iter(engines.values())).PROMPT,
            'protocol': 'Frozen 2.1.0 ID selection; private factory override for whole-passage units.',
            'retrieval_scope': 'Fixed saved context; no new retrieval or indexing.',
            'automatic_semantic_accuracy_scoring': False}
    if resume:
        folder = Path(resume).resolve()
        if not folder.is_relative_to((Path(root)/'results').resolve()):
            raise ValueError('Resume directory must be inside this project results/.')
        assert_same_plan(read_json(folder/'plan.json'), plan)
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]
        folder = Path(root)/'results'/('model_matrix_' + phase + '_' + stamp)
        folder.mkdir(parents=True)
        write_json(folder/'plan.json', plan)
        write_json(folder/'model_inventory.json', inventory)
        write_json(folder/'runner_validation.json', VALIDATION)
        for name in code_hashes:
            target = folder/'source_snapshot'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((Path(root)/name).read_bytes())
        (folder/'source_snapshot/compare_evidence_models.py').write_bytes(Path(__file__).read_bytes())
    if phase == 'confirmation':
        lock = Path(root)/'results/model_matrix_confirmation_selection.json'
        selection = {'model': models[0], 'representation': representations[0],
                     'confirmation_cases_sha256': digest(cases), 'runner_sha256': script_sha,
                     'model_digest': model_digests[models[0]]}
        if lock.exists():
            assert_same_plan(read_json(lock), selection)
        else:
            write_json(lock, selection)
    by_id = {case['case_id']: case for case in cases}
    print('Results:', folder, flush=True)
    print('Planned:', len(jobs), 'records;', sum(j['order'] != 'no_context' for j in jobs), 'generation calls.', flush=True)
    bundle = save_summary(folder, jobs)
    try:
        for index, job in enumerate(jobs, 1):
            path = folder/'jobs'/job['job_id']/'record.json'
            if path.exists():
                print(f'[{index}/{len(jobs)}] Saved record retained', flush=True)
                continue
            context = copy.deepcopy(by_id[job['case_id']]['context'])
            if job['order'] == 'reversed': context.reverse()
            elif job['order'] == 'no_context': context = []
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f'[{index}/{len(jobs)}] {job["model"]} | {job["representation"]} | {job["order"]} | {job["question"]}', flush=True)
            record = {'experiment_version': VERSION, 'job': job, 'context': context}
            try:
                result, _ = engines[job['representation']].run(job['question'], context, client,
                    job['model'], OPTIONS, path.parent/'trace',
                    {'experiment': VERSION, 'phase': phase, 'representation': job['representation'],
                     'order': job['order'], 'job_id': job['job_id']})
                record.update(result=result, status=result['status'])
            except Exception as exc:
                record.update(status='run_failed', error=f'{type(exc).__name__}: {exc}')
            write_json(path, record)
            bundle = save_summary(folder, jobs)
            print('  '+record['status'], flush=True)
    finally:
        bundle = save_summary(folder, jobs)
        print('Saved ZIP:', bundle, flush=True)
        print('Resume if interrupted: python compare_evidence_models.py --phase '+phase+
              (' --model '+models[0]+' --representation '+representations[0] if phase=='confirmation' else '')+
              ' --resume "'+str(folder)+'"', flush=True)
    return folder


class SelfTests(unittest.TestCase):
    """Controlled protocol checks; never reported as model accuracy tests."""
    def test_passage_units_preserve_text_and_offsets(self):
        context = [{'id':'b','text':'Second.','source':'x','page':0},
                   {'id':'a','text':'First.','source':'x','page':0}]
        units = passage_units(context)
        self.assertEqual([u['text'] for u in units], ['Second.', 'First.'])
        self.assertEqual(units[0]['span_end'], len('Second.'))
        self.assertEqual({u['handle']:u for u in units},
                         {u['handle']:u for u in passage_units(list(reversed(context)))})

    def test_matrix_size_and_unique_jobs(self):
        cases = [{'case_id':str(i),'question':'Question?'} for i in range(5)]
        jobs = jobs_for(cases, MODELS, REPRESENTATIONS)
        self.assertEqual(len(jobs), 66)
        self.assertEqual(sum(j['order']!='no_context' for j in jobs),60)
        self.assertEqual(len({j['job_id'] for j in jobs}),66)

    def test_confirmation_has_single_configuration(self):
        cases = [{'case_id':str(i),'question':q} for i,q in enumerate(CONFIRM_QUESTIONS)]
        self.assertEqual(len(jobs_for(cases, MODELS[:1], REPRESENTATIONS[:1])),17)

    def test_missing_models_refused(self):
        with self.assertRaises(ValueError): inventory_digests({'models':[]},MODELS)

    def test_model_digests_retained(self):
        inventory={'models':[{'model':'qwen3:8b','digest':'abc'}]}
        self.assertEqual(inventory_digests(inventory,['qwen3:8b']),{'qwen3:8b':'abc'})

    def test_changed_resume_plan_refused(self):
        with self.assertRaises(ValueError): assert_same_plan({'model':'a'},{'model':'b'})
        assert_same_plan({'a':1,'b':2},{'b':2,'a':1})

    def test_confirmation_inputs_contain_no_expected_answers(self):
        cases=cases_for(Path('.'),'confirmation')
        self.assertEqual(len(cases),8)
        self.assertTrue(all(set(c)=={'case_id','question','context'} for c in cases))

    def test_export_keeps_failed_and_partial_records(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'jobs/a').mkdir(parents=True)
            write_json(folder/'jobs/a/record.json',{'status':'mechanical_failure'})
            write_json(folder/'jobs/a/partial_trace.json',{'status':'started'})
            bundle=export(folder)
            with zipfile.ZipFile(bundle) as archive:
                self.assertIn('jobs/a/record.json',archive.namelist())
                self.assertIn('jobs/a/partial_trace.json',archive.namelist())
                self.assertNotIn('model_matrix_bundle.zip',archive.namelist())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--phase',choices=['development','confirmation'],default='development')
    parser.add_argument('--model',choices=MODELS)
    parser.add_argument('--representation',choices=REPRESENTATIONS)
    parser.add_argument('--resume',type=Path)
    args=parser.parse_args()
    if args.self_test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(SelfTests)
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful(): raise SystemExit(1)
        return
    if args.phase=='confirmation' and (not args.model or not args.representation):
        parser.error('Confirmation requires one explicitly selected --model and --representation.')
    if args.phase=='development' and (args.model or args.representation):
        parser.error('Development runs the entire prespecified matrix; use --resume to continue it.')
    root=Path(__file__).resolve().parent
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'src'))
    check_project(root)
    from evidence_api.local_upload import ollama_client
    models=MODELS if args.phase=='development' else (args.model,)
    representations=REPRESENTATIONS if args.phase=='development' else (args.representation,)
    try:
        execute(root,args.phase,models,representations,ollama_client(),args.resume)
    except KeyboardInterrupt:
        print('Stopped. Completed records and partial traces have been preserved.',flush=True)
        raise SystemExit(130)


if __name__=='__main__': main()
