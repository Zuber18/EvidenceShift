"""Compare saved development-pilot candidate pools without generating answers.

Requires audit_pilot_retrieval.py beside this file and the project's installed
retrieval dependencies. Cached MiniLM weights only. Builds an isolated temporary
Chroma collection from frozen chunks; never opens or changes the original index.
Saves Chroma pools of 5/10/20, exact cosine ranks, vectors, and a report under
results/. Annotation overlap is a diagnostic, never semantic accuracy.
"""
from __future__ import annotations
import argparse
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
POOLS = (5, 10, 20)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def load_auditor(root):
    spec = importlib.util.spec_from_file_location('saved_retrieval_auditor', root / 'audit_pilot_retrieval.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def exact_ranks(chunks, vectors, query):
    """Exhaustive cosine calculation; lexical IDs resolve exact score ties."""
    if len(chunks) != len(vectors) or len({c['id'] for c in chunks}) != len(chunks):
        raise ValueError('Candidate IDs/vectors are inconsistent.')
    query_norm = math.sqrt(sum(v * v for v in query))
    if not query_norm or not all(math.isfinite(v) for v in query):
        raise ValueError('Query embedding is empty, nonfinite or zero.')
    scored = []
    for chunk, vector in zip(chunks, vectors):
        if len(vector) != len(query) or not all(math.isfinite(v) for v in vector):
            raise ValueError('Invalid embedding dimensions or values.')
        length = math.sqrt(sum(v * v for v in vector))
        if not length:
            raise ValueError('Zero candidate embedding.')
        similarity = sum(a * b for a, b in zip(vector, query)) / (length * query_norm)
        scored.append({'id': chunk['id'], 'cosine_similarity': similarity})
    scored.sort(key=lambda row: (-row['cosine_similarity'], row['id']))
    return [dict(row, rank=index + 1) for index, row in enumerate(scored)]


def overlap_summary(case_audit, exact, pools):
    byid = {row['id']: row['rank'] for row in exact}
    spans = []
    for span in case_audit['annotation_spans']:
        candidates = span['overlapping_index_chunks']
        ids = [chunk['id'] for chunk in candidates]
        if any(cid not in byid for cid in ids):
            raise ValueError('Annotated candidate escaped the scoped ranking.')
        spans.append({'unit_id': span['unit_id'], 'alternative_index': span['alternative_index'],
                      'source_id': span['source_id'], 'section': span['section'],
                      'candidates': [{'id': cid, 'exact_cosine_rank': byid[cid],
                                      'in_chroma_pools': [k for k, rows in pools.items() if cid in {r['id'] for r in rows}]}
                                     for cid in ids],
                      'note': 'Overlaps an annotated span; does not establish semantic sufficiency.'})
    return spans


def run(root, pilot_path, folder, assets_factory=None, identity_function=None):
    audit_module = load_auditor(root)
    pilot = audit_module.SavedPilot(pilot_path)
    benchmark = root / 'evaluation/benchmarks/real_documents_v1'
    audit = audit_module.audit(pilot, benchmark)
    plan = pilot.json('plan.json'); prepared = pilot.json('prepared.json')
    save(folder / 'provenance.json', {
        'script_sha256': audit_module.sha(Path(__file__).read_bytes()),
        'auditor_sha256': audit_module.sha((root / 'audit_pilot_retrieval.py').read_bytes()),
        'pilot_plan_sha256': audit_module.sha(pilot.raw('plan.json')),
        'prepared_files': plan['prepared_files'],
        'generation_calls': 0})
    all_chunks = pilot.json('chunks.json'); original_identity = pilot.json('embedding_identity.json')
    relevant_code = ['web_demo/semantic.py', 'src/evidence_api/app.py', 'src/evidence_api/store.py',
                     'src/evidence_api/engine.py', 'src/evidence_api/local_upload.py', 'src/evidence_api/ingestion.py']
    for name in relevant_code:
        if audit_module.sha((root / name).read_bytes()) != plan['code_files'][name]:
            raise ValueError('Retrieval dependency changed since pilot: ' + name)
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    sys.path.insert(0, str(root / 'src')); sys.path.insert(0, str(root))
    if assets_factory is None:
        from web_demo.semantic import create_store
        assets_factory = create_store
    if identity_function is None:
        from evidence_api.local_upload import identity_for_store
        identity_function = identity_for_store
    corpus = [chunk for sid in sorted(all_chunks) for chunk in all_chunks[sid]]
    expected_sources = {sid for case in prepared['inputs'] for sid in case['source_ids']}
    if set(all_chunks) != expected_sources:
        raise ValueError('Saved corpus differs from the selected development sources.')
    save(folder / 'annotation_overlap_audit.json', audit)
    # Temporary assets are independent of the original persisted Chroma index.
    with tempfile.TemporaryDirectory(prefix='evidenceshift_pool_diagnostic_') as temporary:
        store = assets_factory(temporary)
        identity = identity_function(store)
        save(folder / 'embedding_identity.json', identity)
        if identity.get('fingerprint_sha256') != original_identity['fingerprint_sha256']:
            raise ValueError('Cached embedding identity differs from pilot; no comparison was performed.')
        lengths = [len(store.encoder.tokenizer.encode(c['text'], add_special_tokens=True, truncation=False)) for c in corpus]
        query_lengths = [len(store.encoder.tokenizer.encode(c['question'], add_special_tokens=True, truncation=False)) for c in prepared['inputs']]
        maximum = store.encoder.max_seq_length
        save(folder / 'token_lengths.json', {'encoder_maximum': maximum, 'max_chunk_tokens': max(lengths),
             'max_question_tokens': max(query_lengths), 'chunk_lengths': dict(zip([c['id'] for c in corpus], lengths))})
        if max(lengths + query_lengths) > maximum:
            raise ValueError('At least one saved chunk/question exceeds the embedding window; refuse silent truncation.')
        print('Encoding', len(corpus), 'frozen chunks with matching cached MiniLM weights...', flush=True)
        vectors = store.encode([c['text'] for c in corpus])
        save(folder / 'corpus_vectors.json', {'ids': [c['id'] for c in corpus], 'vectors': vectors})
        for offset in range(0, len(corpus), 64):
            batch = corpus[offset:offset + 64]
            store.collection.add(ids=[c['id'] for c in batch], documents=[c['text'] for c in batch],
                metadatas=[{k: v for k, v in c.items() if k not in ('id', 'text', 'distance') and isinstance(v, (str, int, float, bool))} for c in batch],
                embeddings=vectors[offset:offset + 64])
        if store.collection.count() != len(corpus):
            raise ValueError('Temporary index count differs from saved corpus.')
        results = []; query_vectors = {}
        audits = {c['case_id']: c for c in audit['cases']}
        for case in prepared['inputs']:
            cid = case['id']; scoped_ids = {c['document_id'] for sid in case['source_ids'] for c in all_chunks[sid]}
            selected = [(c, v) for c, v in zip(corpus, vectors) if c['document_id'] in scoped_ids]
            query = store.encode([case['question']])[0]; query_vectors[cid] = query
            ranked = exact_ranks([c for c, _ in selected], [v for _, v in selected], query)
            pools = {str(k): store.search(case['question'], min(k, len(selected)), sorted(scoped_ids)) for k in POOLS}
            for rows in pools.values():
                if any(c['document_id'] not in scoped_ids for c in rows):
                    raise ValueError('Chroma pool escaped the declared document scope.')
            original = [c['id'] for c in prepared['contexts'][cid]]
            reproduced = [c['id'] for c in pools['5']] == original
            results.append({'case_id': cid, 'question': case['question'], 'scoped_chunk_count': len(selected),
                'original_top5_ids': original, 'rebuilt_chroma_top5_matches_original': reproduced,
                'chroma_pools': pools, 'exact_cosine_ranking': ranked,
                'annotated_candidates': overlap_summary(audits[cid], ranked, pools)})
            print(cid + ': saved top-five order reproduced=' + str(reproduced), flush=True)
        save(folder / 'query_vectors.json', query_vectors)
    report = {'generation_calls': 0, 'embedding_inference_performed': True, 'questions': len(results),
        'candidate_pool_sizes': list(POOLS), 'benchmark_freeze_sha256': plan['benchmark_freeze_sha256'],
        'embedding_identity_matches_pilot': True, 'original_index_modified': False,
        'all_rebuilt_top5_orders_match_original': all(c['rebuilt_chroma_top5_matches_original'] for c in results),
        'limits': 'Development diagnostic only. Exact cosine ranks are exhaustive within each declared source scope; Chroma pools are separately queried approximate-index outputs from a rebuilt temporary index. Any baseline drift is explicitly flagged. More annotation overlap is not a semantic accuracy score. Pool size is candidate retrieval depth, not an instruction to send 20 passages to the generator.',
        'cases': results}
    save(folder / 'candidate_pools.json', report)
    lines = ['# Candidate pool diagnostic', '', report['limits'], '', 'Answer-generation calls: 0.', '',
             '| Case | Annotation-overlapping chunk | Exact cosine rank | Present in Chroma pools |', '|---|---|---:|---|']
    seen = set()
    for case in results:
        for span in case['annotated_candidates']:
            for candidate in span['candidates']:
                key = (case['case_id'], candidate['id'])
                if key in seen: continue
                seen.add(key)
                lines.append('| {} | {} | {} | {} |'.format(*key, candidate['exact_cosine_rank'], ', '.join(candidate['in_chroma_pools']) or 'none'))
    lines += ['', 'All rebuilt top-five orders match original: ' + str(report['all_rebuilt_top5_orders_match_original']), '']
    (folder / 'CANDIDATE_POOLS.md').write_text('\n'.join(lines), encoding='utf-8')
    return report


class Tests(unittest.TestCase):
    def test_exact_cosine_order(self):
        rows = exact_ranks([{'id': 'opposite'}, {'id': 'same'}], [[-1, 0], [1, 0]], [1, 0])
        self.assertEqual([r['id'] for r in rows], ['same', 'opposite'])
    def test_length_normalization(self):
        self.assertAlmostEqual(exact_ranks([{'id': 'a'}], [[5, 0]], [2, 0])[0]['cosine_similarity'], 1)
    def test_ties_are_stable(self):
        self.assertEqual(exact_ranks([{'id': 'b'}, {'id': 'a'}], [[1], [1]], [1])[0]['id'], 'a')
    def test_zero_query_refused(self):
        with self.assertRaises(ValueError): exact_ranks([{'id': 'a'}], [[1]], [0])
    def test_nonfinite_vector_refused(self):
        with self.assertRaises(ValueError): exact_ranks([{'id': 'a'}], [[float('nan')]], [1])
    def test_duplicate_ids_refused(self):
        with self.assertRaises(ValueError): exact_ranks([{'id': 'a'}, {'id': 'a'}], [[1], [1]], [1])
    def test_candidate_membership_is_actual_pool_membership(self):
        audit = {'annotation_spans': [{'unit_id': 'u', 'alternative_index': 0, 'source_id': 's', 'section': 'x', 'overlapping_index_chunks': [{'id': 'a'}]}]}
        result = overlap_summary(audit, [{'id': 'a', 'rank': 21}], {'5': [], '10': [], '20': [{'id': 'a'}]})
        self.assertEqual(result[0]['candidates'][0]['in_chroma_pools'], ['20'])
    def test_unknown_annotated_candidate_refused(self):
        audit = {'annotation_spans': [{'overlapping_index_chunks': [{'id': 'missing'}]}]}
        with self.assertRaises(ValueError): overlap_summary(audit, [], {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-test', action='store_true'); modes.add_argument('--pilot', type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
    folder = ROOT / 'results' / ('candidate_pools_' + stamp); folder.mkdir(parents=True)
    if args.self_test:
        output = io.StringIO(); result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        save(folder / 'selftest.json', {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                                       'generation_calls': 0, 'log': output.getvalue()})
        print(output.getvalue()); print('Saved:', folder / 'selftest.json')
        return 0 if result.wasSuccessful() else 1
    status = 1
    try:
        report = run(ROOT, args.pilot, folder)
        print('Eight development questions compared; answer-generation calls: 0.')
        print('Baseline top-five reproduction:', report['all_rebuilt_top5_orders_match_original'])
        status = 0
    except BaseException as exc:
        save(folder / 'error.json', {'error': f'{type(exc).__name__}: {exc}', 'generation_calls': 0})
        print(type(exc).__name__ + ': ' + str(exc))
    finally:
        destination = folder / 'candidate_pools_bundle.zip'
        with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.iterdir()):
                if path != destination and path.is_file(): archive.write(path, path.name)
        print('Saved:', destination)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
