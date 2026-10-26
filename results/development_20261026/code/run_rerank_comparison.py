"""Run the 32-attempt Qwen 8B retrieval comparison in the existing project.

Eight exposed development questions, two saved evidence sets, two orders.
--prepare makes no generation calls. --run streams one request per job and
preserves failures/partial outputs without retry. No retrieval, fine-tuning,
model downloads, original pilot replacement or reserved-question execution.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import csv
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = 'rerank-generation-comparison-1.0.0'
MODEL = 'qwen3:8b'
DIGEST = '500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41'
OPTIONS = {'temperature': 0, 'seed': 42, 'num_ctx': 32768, 'num_predict': 2048}
IDS = tuple(f'calibration_{i:02d}' for i in range(1, 9))
ARMS = ('original', 'reranked')
ORDERS = ('canonical', 'reversed')
LIMIT = 32
REVIEWED_CONTEXTS_SHA = '48e7b7307ac03b75e30ec395a0ecf1efd1d7926e15516a76ec4edd8e786b0db9'
ACTIVE = 'config/rerank_generation_comparison_v1.json'
CODE = ('run_rerank_comparison.py', 'run_real_document_pilot.py',
        'run_direct_answer_baseline.py', 'audit_pilot_retrieval.py')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def helpers(root):
    return load('comparison_pilot_core', root / 'run_real_document_pilot.py')


def code_hashes(root, core):
    return {name: core.sha((root / name).read_bytes()) for name in CODE}


def read_inputs(root, pilot_path, reranker_path=None):
    core = helpers(root)
    auditor = load('comparison_auditor', root / 'audit_pilot_retrieval.py')
    pilot = auditor.SavedPilot(pilot_path)
    audit = auditor.audit(pilot, root / 'evaluation/benchmarks/real_documents_v1')
    old_plan = pilot.json('plan.json'); old_prepared = pilot.json('prepared.json')
    for name in ('run_real_document_pilot.py', 'run_direct_answer_baseline.py'):
        if core.sha((root / name).read_bytes()) != old_plan['code_files'][name]:
            raise ValueError('Preserved baseline helper changed since original pilot: ' + name)
    paths = [Path(reranker_path)] if reranker_path else sorted((root / 'results').glob('reranker_*/reranker_bundle.zip'), reverse=True)
    bundle = None
    for path in paths:
        try:
            with zipfile.ZipFile(path) as archive:
                plan = json.loads(archive.read('plan.json'))
                results = json.loads(archive.read('rerank_results.json'))
                if plan['provenance']['pilot_plan_sha256'] == core.sha(pilot.raw('plan.json')):
                    bundle = (path.resolve(), plan, results); break
        except (KeyError, zipfile.BadZipFile):
            if reranker_path: raise
    if bundle is None:
        raise ValueError('No matching completed reranker_bundle.zip under results/. Use --reranker-bundle PATH if moved.')
    path, rerank_plan, result = bundle
    if result['model'] != 'cross-encoder/ms-marco-MiniLM-L6-v2' or result['revision'] != '233902d25c440f23af6f7d6e94d2946bac0bee0a':
        raise ValueError('Unexpected reranker model/revision.')
    if result.get('generation_calls') != 0 or rerank_plan['candidate_depth'] != 40 or rerank_plan['selected_count'] != 5:
        raise ValueError('Reranker protocol differs from the reviewed 40-to-five experiment.')
    cases = result['cases']; byid = {c['case_id']: c for c in cases}
    if len(cases) != 8 or set(byid) != set(IDS): raise ValueError('Expected exactly the eight development cases.')
    if tuple(c['id'] for c in old_prepared['inputs']) != IDS:
        raise ValueError('Unexpected original pilot question selection/order.')
    corpus = pilot.json('chunks.json'); contexts = {}; questions = []
    for source_case in old_prepared['inputs']:
        cid = source_case['id']; row = byid[cid]
        if row['question'] != source_case['question'] or row['original_top5'] != old_prepared['contexts'][cid]:
            raise ValueError('Question or original evidence changed: ' + cid)
        scoped = {c['id']: c for sid in source_case['source_ids'] for c in corpus[sid]}
        selected = row['selected_top5']
        if len(selected) != 5 or len({c['id'] for c in selected}) != 5:
            raise ValueError('Expected five distinct reranked chunks: ' + cid)
        if any(c != scoped.get(c['id']) for c in selected):
            raise ValueError('Reranked text/metadata escaped frozen source scope: ' + cid)
        with zipfile.ZipFile(path) as archive:
            scoring = json.loads(archive.read(f'cases/{cid}/inputs.json'))
            scores = json.loads(archive.read(f'cases/{cid}/partial_scores.json'))
        candidate_ids = scoring['candidate_ids']
        if len(candidate_ids) != len(set(candidate_ids)) or not 5 <= len(candidate_ids) <= 40:
            raise ValueError('Invalid reranker candidate pool: ' + cid)
        if scoring['pairs'] != [[source_case['question'], scoped[c]['text']] for c in candidate_ids]:
            raise ValueError('Scoring inputs differ from source passages: ' + cid)
        if scores['candidate_ids'] != candidate_ids or len(scores['raw_logits']) != len(candidate_ids):
            raise ValueError('Reranker scores differ from candidate IDs: ' + cid)
        import math
        if not all(math.isfinite(float(v)) for v in scores['raw_logits']): raise ValueError('Nonfinite reranker scores.')
        ranking = sorted(zip(candidate_ids, scores['raw_logits'], range(len(candidate_ids))), key=lambda x: (-x[1], x[2], x[0]))
        if [c['id'] for c in selected] != [x[0] for x in ranking[:5]]:
            raise ValueError('Selected five disagree with raw reranker scores: ' + cid)
        contexts[cid] = {'original': copy.deepcopy(row['original_top5']), 'reranked': copy.deepcopy(selected)}
        questions.append({k: copy.deepcopy(source_case[k]) for k in ('id', 'question', 'source_ids')})
    prepared = {'inputs': questions, 'contexts': contexts}
    if core.digest(contexts) != REVIEWED_CONTEXTS_SHA:
        raise ValueError('Evidence sets differ from the reviewed original/reranker comparison. No generation plan was created.')
    historical = pilot.json('models.json')['shows'][MODEL]
    provenance = {'original_pilot_plan_sha256': core.sha(pilot.raw('plan.json')),
                  'reranker_bundle': str(path), 'reranker_bundle_sha256': core.sha(path.read_bytes()),
                  'benchmark_freeze_sha256': audit['benchmark_freeze_sha256']}
    return prepared, provenance, historical


def inspect(api, core, historical=None):
    tags = api.json('/api/tags')
    rows = [m for m in tags.get('models', []) if m.get('name', m.get('model')) == MODEL]
    if len(rows) != 1 or rows[0].get('digest', '').removeprefix('sha256:') != DIGEST:
        raise ValueError('Pinned Qwen 8B model is missing or its digest changed.')
    show = api.json('/api/show', {'model': MODEL})
    capacities = [v for k, v in show.get('model_info', {}).items() if k.endswith('.context_length') and type(v) is int]
    if not capacities or max(capacities) < OPTIONS['num_ctx']: raise ValueError('Native context capacity not established.')
    values = (show.get('thinking') or {}).get('values', []) if isinstance(show.get('thinking'), dict) else []
    if not any(v is False for v in values):
        raise ValueError('This Qwen 8B artifact does not explicitly advertise the required think=false mode.')
    if historical is not None and core.show_identity(show) != core.show_identity(historical):
        raise ValueError('Qwen 8B template/settings differ from the saved original pilot.')
    return {'installed': rows[0], 'show': show, 'show_identity': core.show_identity(show),
            'ollama_version': api.json('/api/version')}


def jobs_for(prepared, core):
    conditions = [(arm, order) for arm in ARMS for order in ORDERS]
    jobs = []
    for index, case in enumerate(prepared['inputs']):
        # Rotate the four conditions: each occupies each serial position twice.
        shift = index % 4
        for arm, order in conditions[shift:] + conditions[:shift]:
            jobs.append({'id': core.digest([VERSION, MODEL, case['id'], arm, order])[:24],
                'model': MODEL, 'case_id': case['id'], 'arm': arm, 'order': order, 'question': case['question']})
    return jobs


def context_for(prepared, job):
    context = prepared['contexts'][job['case_id']][job['arm']]
    return list(reversed(context)) if job['order'] == 'reversed' else list(context)


def prepare(root, pilot_path, api, reranker_path=None, loader=read_inputs):
    core = helpers(root)
    active = root / ACTIVE
    if active.exists():
        plan = core.read(active)
        if plan['pilot_path'] != str(Path(pilot_path).resolve()): raise ValueError('Another comparison plan exists; it was preserved.')
        verify(root, core, plan, loader)
        print('Existing 32-attempt comparison plan verified. Generation calls: 0.')
        return plan
    prepared, provenance, historical = loader(root, pilot_path, reranker_path)
    native = inspect(api, core, historical)
    prompt = core.baseline(root).PROMPT
    if tuple(c['id'] for c in prepared['inputs']) != IDS: raise ValueError('Unexpected case selection.')
    jobs = jobs_for(prepared, core)
    if len(jobs) != LIMIT or len({j['id'] for j in jobs}) != LIMIT: raise ValueError('Invalid job matrix.')
    requests = []
    for job in jobs:
        context = context_for(prepared, job); messages = core.messages_for(prompt, job['question'], context)
        core.budget_for(messages, OPTIONS)
        requests.append({'job': job, 'request': {'model': MODEL, 'messages': messages,
                         'options': OPTIONS, 'think': False, 'stream': True}})
    folder = root / 'results' / ('rerank_comparison_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8])
    folder.mkdir(parents=True)
    core.write(folder / 'prepared.json', prepared); core.write(folder / 'models.json', native)
    core.write(folder / 'planned_requests.json', requests)
    for name in CODE:
        target = folder / 'code_snapshot' / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    frozen = [p for p in folder.rglob('*') if p.is_file()]
    plan = {'comparison_version': VERSION, 'max_generation_attempts': LIMIT,
            'model': MODEL, 'model_digest': DIGEST, 'generation_options': OPTIONS,
            'think': False, 'stream': True, 'prompt': prompt, 'prompt_sha256': core.sha(prompt.encode()),
            'pilot_path': str(Path(pilot_path).resolve()), 'provenance': provenance,
            'folder': str(folder.relative_to(root)), 'ollama_host': api.host,
            'code_hashes': code_hashes(root, core),
            'prepared_files': {str(p.relative_to(folder)): core.sha(p.read_bytes()) for p in frozen},
            'question_ids': list(IDS), 'arms': list(ARMS), 'orders': list(ORDERS),
            'condition_order': 'Four-condition cyclic rotation by case; each position occurs twice per condition.',
            'fine_tuning': False, 'verifier': False, 'publication': False,
            'limits': 'Exposed development comparison; not a held-out accuracy estimate. One attempt per condition, failures retained without automatic retries.'}
    core.write(folder / 'plan.json', plan); core.write(active, plan)
    export(folder, plan, prepared, core)
    print('Prepared: 8 questions × 2 evidence sets × 2 orders = 32 attempts.')
    print('Generation calls during preparation: 0'); print('Saved:', folder)
    return plan


def verify(root, core, plan, loader=read_inputs):
    checks = {'comparison_version': VERSION, 'max_generation_attempts': LIMIT, 'model': MODEL,
        'model_digest': DIGEST, 'generation_options': OPTIONS, 'think': False, 'stream': True,
        'question_ids': list(IDS), 'arms': list(ARMS), 'orders': list(ORDERS), 'fine_tuning': False, 'verifier': False}
    if any(plan.get(k) != v for k, v in checks.items()): raise ValueError('Comparison configuration changed.')
    folder = (root / plan['folder']).resolve()
    if not folder.is_relative_to((root / 'results').resolve()): raise ValueError('Unsafe result folder.')
    if core.read(folder / 'plan.json') != plan or core.read(root / ACTIVE) != plan: raise ValueError('Comparison plans differ.')
    if plan['code_hashes'] != code_hashes(root, core): raise ValueError('Comparison code changed after preparation.')
    for name, expected in plan['prepared_files'].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder) or core.sha(path.read_bytes()) != expected:
            raise ValueError('Prepared file changed: ' + name)
    if core.sha(core.baseline(root).PROMPT.encode()) != plan['prompt_sha256'] or core.baseline(root).PROMPT != plan['prompt']:
        raise ValueError('Baseline prompt changed.')
    fresh, provenance, _ = loader(root, Path(plan['pilot_path']), Path(plan['provenance']['reranker_bundle']))
    prepared = core.read(folder / 'prepared.json')
    if fresh != prepared or provenance != plan['provenance']: raise ValueError('Frozen input evidence or provenance changed.')
    return folder, prepared


def export(folder, plan, prepared, core):
    rows = []; reserved = 0
    for job in jobs_for(prepared, core):
        path = folder / 'jobs' / job['id'] / 'record.json'
        record = core.read(path) if path.exists() else {}
        if record:
            reserved += 1
            if not record.get('complete'):
                record = core.recover_partial(path.parent, record); core.write(path, record)
        final = record.get('final_response', {})
        rows.append({**job, 'status': record.get('status', 'not_started'), 'answer': record.get('answer'),
                     'done_reason': final.get('done_reason'), 'eval_count': final.get('eval_count'),
                     'prompt_eval_count': final.get('prompt_eval_count'), 'local_seconds': record.get('local_seconds'),
                     'error': record.get('error'), 'protocol_issue': record.get('protocol_issue'),
                     'checks': record.get('checks'), 'semantic_accuracy': None})
    result = {'comparison_version': VERSION, 'planned_attempts': LIMIT, 'reserved_attempt_slots': reserved,
              'remaining_attempt_slots': LIMIT - reserved, 'status_counts': dict(Counter(r['status'] for r in rows)),
              'semantic_accuracy': None, 'records': rows}
    core.write(folder / 'summary.json', result)
    fields = [key for key in rows[0] if key != 'checks']
    with (folder / 'runs.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({k: ("'" + row[k] if isinstance(row[k], str) and row[k].lstrip().startswith(('=', '+', '-', '@')) else row[k]) for k in fields})
    lines = ['# Qwen 8B original-versus-reranked comparison', '', plan['limits'], '',
             'Canonical is original retrieval order in the original arm and reranker order in the reranked arm. Reversed flips only that arm\'s saved five passages.', '',
             f'Reserved attempts: {reserved}/32. No automatic semantic score.', '']
    for row in rows:
        lines += [f"## {row['case_id']} · {row['arm']} · {row['order']}", '', 'Status: ' + row['status'], '', row.get('answer') or '(No answer recorded.)', '']
    (folder / 'COMPARISON.md').write_text('\n'.join(lines), encoding='utf-8')
    target = folder / 'comparison_bundle.zip'; temporary = folder / 'comparison_bundle.tmp'
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path not in (target, temporary) and path.suffix != '.lock':
                archive.write(path, str(path.relative_to(folder)))
    temporary.replace(target)
    return result


def run(root, api, loader=read_inputs):
    core = helpers(root)
    if not (root / ACTIVE).exists(): raise ValueError('Prepare this comparison first with --prepare.')
    plan = core.read(root / ACTIVE); folder, prepared = verify(root, core, plan, loader)
    if api.host != plan['ollama_host']: raise ValueError('Ollama origin differs from prepared origin.')
    with core.process_lock(folder / 'comparison.lock'):
        expected = core.read(folder / 'models.json')
        def check_native():
            current = inspect(api, core)
            if current['show_identity'] != expected['show_identity'] or current['ollama_version'] != expected['ollama_version']:
                raise ValueError('Ollama model metadata/server version changed after preparation.')
        check_native(); export(folder, plan, prepared, core)
        try:
            for index, job in enumerate(jobs_for(prepared, core)):
                job_folder = folder / 'jobs' / job['id']
                if (job_folder / 'record.json').exists(): continue
                if len(list((folder / 'jobs').glob('*/record.json'))) >= LIMIT: raise ValueError('32-attempt budget exhausted.')
                check_native()
                print(f"[{index+1}/32] {job['case_id']} · {job['arm']} · {job['order']}", flush=True)
                record = core.run_job(job, context_for(prepared, job), job_folder, plan, api)
                record['comparison_version'] = VERSION
                if record.get('thinking') or re.search(r'</?think\b', record.get('answer', ''), re.I):
                    record['protocol_issue'] = 'Unexpected thinking output under requested think=false; raw output preserved.'
                    record['stop_batch'] = True
                core.write(job_folder / 'record.json', record)
                export(folder, plan, prepared, core)
                if record.get('interrupted') or record.get('stop_batch'): break
                check_native()
        finally: result = export(folder, plan, prepared, core)
    print('Reserved attempt slots:', result['reserved_attempt_slots'], '/ 32')
    print('Saved:', folder / 'comparison_bundle.zip')
    if result['remaining_attempt_slots']: print('Unattempted jobs remain. Existing attempts will never be retried.')
    return result


class FakeAPI:
    host = 'http://localhost:11434'
    def __init__(self, behavior='success'):
        self.behavior = behavior; self.calls = 0; self.payloads = []; self.digest = DIGEST
        self.show = {'model_info': {'qwen3.context_length': 32768}, 'thinking': {'values': [False, True]}, 'template': 'offline fixture'}
    def json(self, endpoint, payload=None):
        if endpoint == '/api/tags': return {'models': [{'name': MODEL, 'digest': self.digest}]}
        if endpoint == '/api/show': return copy.deepcopy(self.show)
        if endpoint == '/api/version': return {'version': 'offline-fixture'}
        raise AssertionError(endpoint)
    def lines(self, payload):
        self.calls += 1; self.payloads.append(copy.deepcopy(payload))
        yield json.dumps({'message': {'content': 'Partial '}, 'done': False}).encode() + b'\n'
        if self.behavior == 'interrupt': raise KeyboardInterrupt()
        if self.behavior == 'failure': raise OSError('simulated disconnect')
        if self.behavior == 'thinking':
            yield json.dumps({'message': {'thinking': 'unexpected thinking'}, 'done': False}).encode() + b'\n'
        cid = json.loads(payload['messages'][1]['content'])['passages'][0]['id']
        yield json.dumps({'model': MODEL, 'message': {'content': 'answer [' + cid + ']'},
                          'done': True, 'done_reason': 'length' if self.behavior == 'length' else 'stop',
                          'prompt_eval_count': 100, 'eval_count': 20}).encode() + b'\n'


class Tests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup); root = Path(temporary.name)
        for name in CODE: shutil.copy2(ROOT / name, root / name)
        data = {'inputs': [], 'contexts': {}}
        for cid in IDS:
            data['inputs'].append({'id': cid, 'question': 'Question ' + cid, 'source_ids': ['s']})
            original = [{'id': f'doc_0123456789abcdef0123_p0_c{i}', 'source': 'source.txt', 'page': 0, 'text': 'Evidence ' + str(i)} for i in range(5)]
            data['contexts'][cid] = {'original': original, 'reranked': list(reversed(original))}
        api = FakeAPI()
        provenance = {'reranker_bundle': str(root / 'fake.zip'), 'digest': 'fixture'}
        def loader(*args): return copy.deepcopy(data), copy.deepcopy(provenance), copy.deepcopy(FakeAPI().show)
        return root, api, data, loader
    def ready(self):
        from contextlib import redirect_stdout
        root, api, data, loader = self.fixture()
        with redirect_stdout(io.StringIO()): plan = prepare(root, root / 'fake-pilot', api, loader=loader)
        return root, api, data, loader, plan
    def test_matrix_32_unique_balanced_conditions(self):
        root, api, data, loader = self.fixture(); jobs = jobs_for(data, helpers(root))
        self.assertEqual(len(jobs), 32); self.assertEqual(len({j['id'] for j in jobs}), 32)
        counts = Counter((i % 4, j['arm'], j['order']) for i, j in enumerate(jobs))
        self.assertEqual(set(counts.values()), {2})
    def test_reversal_changes_only_order(self):
        root, _, data, _ = self.fixture(); job = jobs_for(data, helpers(root))[0]
        original = context_for(data, job); job['order'] = 'reversed'
        self.assertEqual(context_for(data, job), original[::-1])
    def test_missing_model_refused(self):
        root, api, _, _ = self.fixture(); api.digest = '0' * 64
        with self.assertRaises(ValueError): inspect(api, helpers(root))
        self.assertEqual(api.calls, 0)
    def test_thinking_only_refused(self):
        root, api, _, _ = self.fixture(); api.show['thinking'] = {'values': [True]}
        with self.assertRaises(ValueError): inspect(api, helpers(root))
        self.assertEqual(api.calls, 0)
    def test_short_native_context_refused(self):
        root, api, _, _ = self.fixture(); api.show['model_info']['qwen3.context_length'] = 4096
        with self.assertRaises(ValueError): inspect(api, helpers(root))
    def test_prepare_zero_calls_and_no_gold_request_fields(self):
        root, api, _, loader, plan = self.ready(); self.assertEqual(api.calls, 0)
        requests = helpers(root).read(root / plan['folder'] / 'planned_requests.json')
        self.assertEqual(len(requests), 32)
        for item in requests:
            request = item['request']; self.assertIs(request['think'], False); self.assertNotIn('format', request)
            self.assertEqual(set(json.loads(request['messages'][1]['content'])), {'question', 'passages'})
    def test_changed_prepared_evidence_refused(self):
        root, api, _, loader, plan = self.ready(); core = helpers(root)
        core.write(root / plan['folder'] / 'prepared.json', {})
        with self.assertRaises(ValueError): verify(root, core, plan, loader)
        self.assertEqual(api.calls, 0)
    def test_changed_code_refused(self):
        root, api, _, loader, plan = self.ready()
        with (root / 'run_rerank_comparison.py').open('a') as handle: handle.write('\n# change\n')
        with self.assertRaises(ValueError): verify(root, helpers(root), plan, loader)
    def test_changed_evidence_arm_configuration_refused(self):
        root, _, _, loader, plan = self.ready(); plan['arms'] = ['reranked']
        with self.assertRaises(ValueError): verify(root, helpers(root), plan, loader)
    def test_all_32_then_resume_zero_additional_calls(self):
        from contextlib import redirect_stdout
        root, api, _, loader, plan = self.ready()
        with redirect_stdout(io.StringIO()): result = run(root, api, loader); run(root, api, loader)
        self.assertEqual(api.calls, 32); self.assertEqual(result['remaining_attempt_slots'], 0)
        self.assertEqual(result['status_counts'], {'output_recorded': 32})
        self.assertTrue((root / plan['folder'] / 'comparison_bundle.zip').exists())
    def test_interrupted_attempt_preserved_then_remaining_31_only(self):
        from contextlib import redirect_stdout
        root, api, _, loader, plan = self.ready(); api.behavior = 'interrupt'
        with redirect_stdout(io.StringIO()): first = run(root, api, loader)
        self.assertEqual(first['reserved_attempt_slots'], 1)
        api.behavior = 'success'
        with redirect_stdout(io.StringIO()): result = run(root, api, loader)
        self.assertEqual(api.calls, 32); self.assertEqual(result['status_counts']['interrupted_preserved'], 1)
    def test_failed_outputs_are_not_retried(self):
        from contextlib import redirect_stdout
        root, api, _, loader, plan = self.ready(); api.behavior = 'failure'
        with redirect_stdout(io.StringIO()): first = run(root, api, loader); run(root, api, loader)
        self.assertEqual(api.calls, 32); self.assertEqual(first['status_counts']['generation_failed'], 32)
    def test_length_limit_retained_as_incomplete(self):
        from contextlib import redirect_stdout
        root, api, _, loader, _ = self.ready(); api.behavior = 'length'
        with redirect_stdout(io.StringIO()): result = run(root, api, loader)
        self.assertEqual(result['status_counts'], {'incomplete_generation': 32})
    def test_changed_model_after_prepare_blocks_all_calls(self):
        root, api, _, loader, _ = self.ready(); api.show['template'] += ' changed'
        with self.assertRaises(ValueError): run(root, api, loader)
        self.assertEqual(api.calls, 0)
    def test_unexpected_thinking_stops_batch_without_stripping(self):
        from contextlib import redirect_stdout
        root, api, _, loader, plan = self.ready(); api.behavior = 'thinking'
        with redirect_stdout(io.StringIO()): result = run(root, api, loader)
        self.assertEqual(api.calls, 1); self.assertEqual(result['remaining_attempt_slots'], 31)
        row = next(r for r in result['records'] if r['status'] != 'not_started')
        self.assertIn('Unexpected thinking', row['protocol_issue'])
        record = helpers(root).read(root / plan['folder'] / 'jobs' / row['id'] / 'record.json')
        self.assertEqual(record['thinking'], 'unexpected thinking')
    def test_crash_reservation_recovered_without_resubmitting(self):
        from contextlib import redirect_stdout
        root, api, data, loader, plan = self.ready(); core = helpers(root)
        job = jobs_for(data, core)[0]; folder = root / plan['folder'] / 'jobs' / job['id']
        core.write(folder / 'record.json', {'job': job, 'complete': False, 'status': 'request_reserved'})
        (folder / 'stream.ndjson').write_text(json.dumps({'message': {'content': 'durable partial'}}) + '\n')
        with redirect_stdout(io.StringIO()): result = run(root, api, loader)
        self.assertEqual(api.calls, 31)
        self.assertEqual(result['status_counts']['interrupted_preserved'], 1)
        self.assertEqual(core.read(folder / 'record.json')['answer'], 'durable partial')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-test', action='store_true'); modes.add_argument('--prepare', action='store_true'); modes.add_argument('--run', action='store_true')
    parser.add_argument('--pilot', type=Path); parser.add_argument('--reranker-bundle', type=Path)
    args = parser.parse_args()
    if args.prepare and args.pilot is None: parser.error('--prepare requires --pilot PATH')
    if args.run and (args.pilot or args.reranker_bundle): parser.error('--run uses the saved plan; omit input arguments')
    if not (ROOT / 'pyproject.toml').exists(): parser.error('Save the script in the existing project root containing pyproject.toml.')
    core = helpers(ROOT)
    try:
        if args.self_test:
            output = io.StringIO(); result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
            path = ROOT / 'results' / ('comparison_selftest_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]) / 'selftest.json'
            core.write(path, {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                              'generation_calls': 0, 'script_sha256': core.sha(Path(__file__).read_bytes()), 'log': output.getvalue()})
            print(output.getvalue()); print('Saved:', path)
            return 0 if result.wasSuccessful() else 1
        successful = False
        for path in (ROOT / 'results').glob('comparison_selftest_*/selftest.json'):
            report = core.read(path)
            if report.get('script_sha256') == core.sha(Path(__file__).read_bytes()) and report['tests'] >= 14 and report['failures'] == report['errors'] == 0:
                successful = True; break
        if not successful: raise ValueError('Run --self-test successfully for this exact script before preparation or generation.')
        import os
        api = core.LocalAPI(os.environ.get('OLLAMA_HOST', 'http://localhost:11434'))
        if args.prepare:
            with core.process_lock(ROOT / 'results/comparison_prepare.lock'):
                prepare(ROOT, args.pilot, api, args.reranker_bundle)
        else: run(ROOT, api)
        return 0
    except Exception as exc:
        path = ROOT / 'results' / ('comparison_error_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8] + '.json')
        core.write(path, {'error': f'{type(exc).__name__}: {exc}'})
        print(type(exc).__name__ + ': ' + str(exc)); print('Saved error:', path)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
