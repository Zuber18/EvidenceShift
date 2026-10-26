"""Local development diagnostic: exact MiniLM top 40 -> cross-encoder top five.

--self-test uses no model or network. --prepare --pilot PATH validates frozen
inputs and downloads a pinned public checkpoint. --run scores question/passage
pairs locally on CPU. No Ollama calls, generated answers, or original index
changes. Requires audit_pilot_retrieval.py and rank_pilot_candidates.py beside it.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
MODEL = 'cross-encoder/ms-marco-MiniLM-L6-v2'
REVISION = '233902d25c440f23af6f7d6e94d2946bac0bee0a'
DEPTH = 40
KEEP = 5
BATCH = 8
LIMIT = 512
LOCK = 'config/rerank_experiment_v1.json'
FILES = ['config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
         'special_tokens_map.json', 'vocab.txt', 'README.md']


def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)
def identifier(): return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def select_candidates(ranking, chunks, depth=DEPTH):
    byid = {c['id']: c for c in chunks}
    ids = [r['id'] for r in ranking]
    if len(byid) != len(chunks) or len(set(ids)) != len(ids) or set(ids) != set(byid):
        raise ValueError('Scoped ranking and frozen chunk IDs differ.')
    return [byid[cid] for cid in ids[:depth]]


def pair_inputs(question, candidates):
    # Explicit input allowlist. Gold annotations and reference answers never
    # enter scoring; they are consulted afterward only for overlap diagnostics.
    return [(question, c['text']) for c in candidates]


def order_scores(candidates, scores):
    values = [float(s) for s in scores]
    if len(values) != len(candidates) or not all(math.isfinite(s) for s in values):
        raise ValueError('Reranker returned invalid score count or nonfinite values.')
    rows = [{'id': c['id'], 'initial_candidate_rank': i + 1, 'raw_logit': s}
            for i, (c, s) in enumerate(zip(candidates, values))]
    rows.sort(key=lambda row: (-row['raw_logit'], row['initial_candidate_rank'], row['id']))
    return [dict(row, rerank_position=i + 1) for i, row in enumerate(rows)]


def input_data(root, pilot_path, bundle_path=None):
    auditor = load_module('rerank_saved_auditor', root / 'audit_pilot_retrieval.py')
    ranker = load_module('rerank_saved_ranker', root / 'rank_pilot_candidates.py')
    pilot = auditor.SavedPilot(pilot_path)
    audit = auditor.audit(pilot, root / 'evaluation/benchmarks/real_documents_v1')
    plan_sha = sha(pilot.raw('plan.json'))
    paths = [Path(bundle_path)] if bundle_path else sorted((root / 'results').glob('candidate_pools_*/candidate_pools_bundle.zip'), reverse=True)
    match = None
    for path in paths:
        try:
            with zipfile.ZipFile(path) as archive:
                provenance = json.loads(archive.read('provenance.json'))
                if provenance.get('pilot_plan_sha256') != plan_sha: continue
                required = ('candidate_pools.json', 'corpus_vectors.json', 'query_vectors.json', 'embedding_identity.json')
                data = {name: json.loads(archive.read(name)) for name in required}
                match = (path.resolve(), provenance, data)
                break
        except (KeyError, zipfile.BadZipFile):
            if bundle_path: raise
    if match is None:
        raise ValueError('No matching successful candidate_pools_bundle.zip found under results/. Use --candidate-bundle PATH if it was moved.')
    path, provenance, data = match
    if provenance['script_sha256'] != sha((root / 'rank_pilot_candidates.py').read_bytes()):
        raise ValueError('Ranking helper changed since the saved candidate experiment.')
    if provenance['auditor_sha256'] != sha((root / 'audit_pilot_retrieval.py').read_bytes()):
        raise ValueError('Auditor changed since the saved candidate experiment.')
    if data['embedding_identity.json'] != pilot.json('embedding_identity.json'):
        raise ValueError('Candidate bundle embedding identity differs from the original pilot.')
    report = data['candidate_pools.json']
    if report['benchmark_freeze_sha256'] != audit['benchmark_freeze_sha256']:
        raise ValueError('Candidate bundle benchmark freeze differs.')
    prepared = pilot.json('prepared.json'); chunks = pilot.json('chunks.json')
    vector_data = data['corpus_vectors.json']; ids = vector_data['ids']
    corpus_ids = [c['id'] for source in sorted(chunks) for c in chunks[source]]
    if len(set(ids)) != len(ids) or set(ids) != set(corpus_ids) or len(ids) != len(vector_data['vectors']):
        raise ValueError('Saved vector corpus does not match the frozen development chunks.')
    vectors = dict(zip(ids, vector_data['vectors'])); queries = data['query_vectors.json']
    inputs = prepared['inputs']; reports = {c['case_id']: c for c in report['cases']}
    if len(reports) != 8 or set(reports) != {c['id'] for c in inputs} or set(queries) != set(reports):
        raise ValueError('Expected exactly the eight pilot development questions.')
    jobs = []
    for case in inputs:
        cid = case['id']; scoped = [c for sid in case['source_ids'] for c in chunks[sid]]
        exact = ranker.exact_ranks(scoped, [vectors[c['id']] for c in scoped], queries[cid])
        if [r['id'] for r in exact] != [r['id'] for r in reports[cid]['exact_cosine_ranking']]:
            raise ValueError('Saved exact ranking disagrees with saved vectors: ' + cid)
        if reports[cid]['original_top5_ids'] != [c['id'] for c in prepared['contexts'][cid]]:
            raise ValueError('Original top-five context differs: ' + cid)
        jobs.append({'case_id': cid, 'question': case['question'],
                     'candidates': select_candidates(exact, scoped),
                     'original_top5': prepared['contexts'][cid]})
    return jobs, audit, {'pilot_plan_sha256': plan_sha, 'candidate_bundle': str(path),
                        'candidate_bundle_sha256': sha(path.read_bytes()),
                        'benchmark_freeze_sha256': audit['benchmark_freeze_sha256']}


def asset_hashes(path):
    return {name: sha((path / name).read_bytes()) for name in FILES if (path / name).is_file()}


def code_hashes(root):
    return {name: sha((root / name).read_bytes()) for name in
            ('rerank_pilot_candidates.py', 'audit_pilot_retrieval.py', 'rank_pilot_candidates.py')}


def prepare(root, pilot_path, bundle_path, folder):
    jobs, audit, provenance = input_data(root, pilot_path, bundle_path)
    save(folder / 'input_validation.json', provenance)
    lock = root / LOCK
    if lock.exists():
        old = read(lock)
        if old['provenance'] != provenance or old['code_hashes'] != code_hashes(root):
            raise ValueError('A different reranking plan already exists. It was preserved.')
        verify_lock(root, old)
        print('Existing pinned reranking plan verified; no download or inference needed.')
        return old
    from huggingface_hub import snapshot_download
    # Only public checkpoint files are downloaded. Documents are scored locally
    # in --run and are never sent to an inference service.
    print('Downloading pinned reranker checkpoint (first preparation only)...', flush=True)
    snapshot = Path(snapshot_download(repo_id=MODEL, revision=REVISION,
        cache_dir=str(root / 'data_local/reranker_cache'), allow_patterns=FILES,
        token=False, local_files_only=False))
    if not (snapshot / 'model.safetensors').is_file() or not (snapshot / 'config.json').is_file():
        raise ValueError('Pinned safetensors checkpoint is incomplete; no pickle fallback is used.')
    plan = {'model': MODEL, 'revision': REVISION, 'snapshot': str(snapshot),
            'asset_hashes': asset_hashes(snapshot), 'pilot': str(Path(pilot_path).resolve()),
            'provenance': provenance, 'code_hashes': code_hashes(root),
            'candidate_depth': DEPTH, 'selected_count': KEEP, 'pair_limit': LIMIT,
            'batch_size': BATCH, 'device': 'cpu', 'score': 'raw sequence-classification logit',
            'question_count': len(jobs), 'planned_pair_scores': sum(len(j['candidates']) for j in jobs),
            'generation_calls': 0}
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('x', encoding='utf-8') as handle: json.dump(plan, handle, indent=2)
    save(folder / 'prepared_plan.json', plan)
    print('Prepared:', len(jobs), 'development questions;', plan['planned_pair_scores'], 'local pair scores.')
    print('Saved plan:', lock)
    return plan


def verify_lock(root, plan):
    required = {'model': MODEL, 'revision': REVISION, 'candidate_depth': DEPTH,
                'selected_count': KEEP, 'pair_limit': LIMIT, 'batch_size': BATCH,
                'device': 'cpu', 'score': 'raw sequence-classification logit', 'question_count': 8}
    if any(plan.get(k) != v for k, v in required.items()):
        raise ValueError('Reranker settings differ from this experiment.')
    if plan['code_hashes'] != code_hashes(root): raise ValueError('Experiment code changed after preparation.')
    if asset_hashes(Path(plan['snapshot'])) != plan['asset_hashes']:
        raise ValueError('Pinned reranker assets changed after preparation.')


def run(root, folder):
    if not (root / LOCK).exists(): raise ValueError('Run --prepare --pilot PATH first.')
    plan = read(root / LOCK); verify_lock(root, plan)
    jobs, audit, provenance = input_data(root, plan['pilot'], plan['provenance']['candidate_bundle'])
    if provenance != plan['provenance']: raise ValueError('Input provenance changed.')
    save(folder / 'plan.json', plan); save(folder / 'annotation_audit.json', audit)
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    torch.manual_seed(42); torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(plan['snapshot'], local_files_only=True, trust_remote_code=False, token=False)
    model = AutoModelForSequenceClassification.from_pretrained(plan['snapshot'], local_files_only=True,
        trust_remote_code=False, use_safetensors=True, token=False)
    model = model.to(device='cpu', dtype=torch.float32); model.eval()
    if model.config.num_labels != 1 or model.config.max_position_embeddings < LIMIT:
        raise ValueError('Expected a single-logit checkpoint supporting the configured pair limit.')
    results = []
    for job in jobs:
        cid = job['case_id']; candidates = job['candidates']
        pairs = pair_inputs(job['question'], candidates)
        case_folder = folder / 'cases' / cid; case_folder.mkdir(parents=True)
        save(case_folder / 'inputs.json', {'case_id': cid, 'pairs': pairs, 'candidate_ids': [c['id'] for c in candidates]})
        lengths = [len(tokenizer(q, text, add_special_tokens=True, truncation=False)['input_ids']) for q, text in pairs]
        save(case_folder / 'pair_token_lengths.json', lengths)
        if max(lengths) > LIMIT:
            raise ValueError('Pair exceeds 512 tokens; refuse silent truncation: ' + cid)
        print(cid + ': scoring ' + str(len(pairs)) + ' candidate pairs...', flush=True)
        scores = []
        for offset in range(0, len(pairs), BATCH):
            batch = pairs[offset:offset + BATCH]
            encoded = tokenizer([q for q, _ in batch], [text for _, text in batch],
                padding=True, truncation=False, return_tensors='pt')
            with torch.inference_mode(): logits = model(**encoded).logits
            scores.extend(logits[:, 0].detach().cpu().tolist())
            save(case_folder / 'partial_scores.json', {'candidate_ids': [c['id'] for c in candidates[:len(scores)]], 'raw_logits': scores})
        ranking = order_scores(candidates, scores); selected_ids = [r['id'] for r in ranking[:KEEP]]
        byid = {c['id']: c for c in candidates}
        result = {'case_id': cid, 'question': job['question'], 'original_top5': job['original_top5'],
            'exact_cosine_top5': candidates[:KEEP], 'exact_cosine_candidate_ids': [c['id'] for c in candidates],
            'reranked_scores': ranking, 'selected_top5': [byid[cid] for cid in selected_ids],
            'max_pair_tokens': max(lengths)}
        save(case_folder / 'result.json', result); results.append(result)
    audits = {c['case_id']: c for c in audit['cases']}
    for result in results:
        ids = {c['id'] for c in result['selected_top5']}
        position = {r['id']: r['rerank_position'] for r in result['reranked_scores']}
        diagnostics = []
        seen = set()
        for span in audits[result['case_id']]['annotation_spans']:
            for candidate in span['overlapping_index_chunks']:
                cid = candidate['id']
                if cid in seen: continue
                seen.add(cid)
                diagnostics.append({'id': cid, 'in_original_top5': cid in {c['id'] for c in result['original_top5']},
                    'in_exact_top40': cid in position, 'rerank_position': position.get(cid), 'selected_top5': cid in ids})
        result['annotated_chunk_diagnostics'] = diagnostics
    report = {'model': MODEL, 'revision': REVISION, 'generation_calls': 0,
        'local_reranker_inference_performed': True, 'candidate_selection': 'exhaustive saved cosine ranks, top 40 or all if fewer',
        'score_interpretation': 'Raw relevance logits, not factual-support probabilities.',
        'semantic_accuracy': None, 'limits': 'Eight exposed development questions. Forty-candidate depth was selected after observing development ranks. An annotated chunk reaching top five does not prove complete evidence or reliable answers. Exact-cosine candidate selection is distinct from the original Chroma query. No answer generation or held-out evaluation performed.',
        'cases': results}
    save(folder / 'rerank_results.json', report)
    lines = ['# Development reranker comparison', '', report['limits'], '', report['score_interpretation'], '',
             '| Case | Annotated chunk | Original five | In cosine forty | Rerank position | Selected five |',
             '|---|---|---|---|---:|---|']
    for case in results:
        for row in case['annotated_chunk_diagnostics']:
            lines.append('| {} | {} | {} | {} | {} | {} |'.format(case['case_id'], row['id'], row['in_original_top5'], row['in_exact_top40'], row['rerank_position'] or 'outside pool', row['selected_top5']))
    (folder / 'RERANK_COMPARISON.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Scored all eight questions locally; generation calls: 0.')


class Tests(unittest.TestCase):
    def fake_run(self, length=12):
        from contextlib import nullcontext, redirect_stdout
        observed = []; model_calls = []
        class Values:
            def __init__(self, values): self.values = values
            def __getitem__(self, index): return self
            def detach(self): return self
            def cpu(self): return self
            def tolist(self): return self.values
        class Tokenizer:
            @classmethod
            def from_pretrained(cls, *args, **kwargs): return cls()
            def __call__(self, questions, passages, **kwargs):
                observed.append((questions, passages, kwargs))
                return {'count': len(questions)} if kwargs.get('return_tensors') else {'input_ids': [0] * length}
        class Model:
            config = SimpleNamespace(num_labels=1, max_position_embeddings=512)
            @classmethod
            def from_pretrained(cls, *args, **kwargs): return cls()
            def to(self, **kwargs): return self
            def eval(self): pass
            def __call__(self, count):
                model_calls.append(count)
                return SimpleNamespace(logits=Values([float(i) for i in range(count)]))
        fake_torch = SimpleNamespace(manual_seed=lambda x: None, set_num_threads=lambda x: None,
                                     float32='float32', inference_mode=nullcontext)
        jobs = [{'case_id': 'case_' + str(i), 'question': 'Question',
                 'candidates': [{'id': str(j), 'text': 'Passage', 'reference_answer': 'SECRET_GOLD'} for j in range(7)],
                 'original_top5': []} for i in range(8)]
        audit = {'cases': [{'case_id': job['case_id'], 'annotation_spans': []} for job in jobs]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); folder = root / 'report'; folder.mkdir()
            plan = {'snapshot': 'fake', 'pilot': 'fake', 'provenance': {'candidate_bundle': 'fake'}}
            save(root / LOCK, plan)
            fake_transformers = SimpleNamespace(AutoTokenizer=Tokenizer, AutoModelForSequenceClassification=Model)
            with patch.dict(sys.modules, {'torch': fake_torch, 'transformers': fake_transformers}), \
                 patch(__name__ + '.verify_lock'), \
                 patch(__name__ + '.input_data', return_value=(jobs, audit, plan['provenance'])), \
                 redirect_stdout(io.StringIO()):
                if length > LIMIT:
                    with self.assertRaisesRegex(ValueError, 'refuse silent truncation'): run(root, folder)
                else:
                    run(root, folder)
                    report = read(folder / 'rerank_results.json')
                    self.assertEqual(len(report['cases']), 8)
                    self.assertTrue(all(len(case['selected_top5']) == 5 for case in report['cases']))
                    self.assertEqual(report['generation_calls'], 0)
            return observed, model_calls
    def test_scoring_pipeline_uses_only_question_and_text(self):
        observed, calls = self.fake_run()
        self.assertNotIn('SECRET_GOLD', str(observed)); self.assertEqual(sum(calls), 56)
    def test_scoring_pipeline_refuses_oversized_pair_before_inference(self):
        _, calls = self.fake_run(LIMIT + 1)
        self.assertEqual(calls, [])
    def test_candidates_follow_rank(self):
        self.assertEqual(select_candidates([{'id': 'b'}, {'id': 'a'}], [{'id': 'a'}, {'id': 'b'}], 1), [{'id': 'b'}])
    def test_scope_mismatch_refused(self):
        with self.assertRaises(ValueError): select_candidates([{'id': 'a'}], [{'id': 'b'}])
    def test_duplicate_ranking_refused(self):
        with self.assertRaises(ValueError): select_candidates([{'id': 'a'}, {'id': 'a'}], [{'id': 'a'}])
    def test_input_allowlist_excludes_gold(self):
        pairs = pair_inputs('Question', [{'text': 'Passage', 'reference_answer': 'SECRET', 'gold_notes': 'SECRET'}])
        self.assertEqual(pairs, [('Question', 'Passage')]); self.assertNotIn('SECRET', str(pairs))
    def test_larger_logit_ranks_first(self):
        self.assertEqual(order_scores([{'id': 'a'}, {'id': 'b'}], [-4, 2])[0]['id'], 'b')
    def test_ties_preserve_initial_rank(self):
        self.assertEqual(order_scores([{'id': 'b'}, {'id': 'a'}], [1, 1])[0]['id'], 'b')
    def test_nonfinite_scores_refused(self):
        for score in (float('nan'), float('inf')):
            with self.assertRaises(ValueError): order_scores([{'id': 'a'}], [score])
    def test_wrong_score_count_refused(self):
        with self.assertRaises(ValueError): order_scores([{'id': 'a'}], [])
    def test_small_source_keeps_all_candidates(self):
        self.assertEqual(len(select_candidates([{'id': 'a'}], [{'id': 'a'}])), 1)
    def test_selection_keeps_five(self):
        rows = order_scores([{'id': str(i)} for i in range(40)], list(range(40)))
        self.assertEqual([r['id'] for r in rows[:KEEP]], ['39', '38', '37', '36', '35'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-test', action='store_true'); modes.add_argument('--prepare', action='store_true'); modes.add_argument('--run', action='store_true')
    parser.add_argument('--pilot', type=Path); parser.add_argument('--candidate-bundle', type=Path)
    args = parser.parse_args()
    if args.prepare and args.pilot is None: parser.error('--prepare requires --pilot PATH')
    if args.run and (args.pilot or args.candidate_bundle): parser.error('--run uses the pinned prepared plan; omit input arguments')
    folder = ROOT / 'results' / ('reranker_' + identifier()); folder.mkdir(parents=True)
    status = 1
    try:
        if args.self_test:
            output = io.StringIO(); result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
            save(folder / 'selftest.json', {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'generation_calls': 0, 'log': output.getvalue()})
            print(output.getvalue()); status = 0 if result.wasSuccessful() else 1
        else:
            if not (ROOT / 'pyproject.toml').is_file(): raise ValueError('Save this file in the existing project root.')
            save(folder / 'execution.json', {'script_sha256': sha(Path(__file__).read_bytes()), 'mode': 'prepare' if args.prepare else 'run', 'generation_calls': 0})
            if args.prepare: prepare(ROOT, args.pilot, args.candidate_bundle, folder)
            else: run(ROOT, folder)
            status = 0
    except BaseException as exc:
        save(folder / 'error.json', {'error': f'{type(exc).__name__}: {exc}', 'generation_calls': 0})
        print(type(exc).__name__ + ': ' + str(exc))
    finally:
        destination = folder / 'reranker_bundle.zip'
        with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.rglob('*')):
                if path.is_file() and path != destination: archive.write(path, str(path.relative_to(folder)))
        print('Saved:', destination)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
