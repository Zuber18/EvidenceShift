"""Build a compact, traceable browser dataset from the published experiments.

Only saved records and owner assessments are used. This performs no retrieval,
model inference or new factual scoring. Run from any directory with Python 3.12.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASES = [
    ('direct_confirmation', 'direct_confirmation_20261020', 'Reserved-case confirmation',
     'Eight short fictional questions, one frozen Qwen 8B model, two evidence orders.', 17, 16, 1),
    ('direct_answer', 'direct_answer_20261020', 'Direct-answer comparison',
     'Three local models answer five known story questions using the same saved passages.', 33, 30, 3),
    ('model_matrix', 'model_matrix_20261019', 'Evidence-selection matrix',
     'Three models select passage or text-unit IDs. Copied excerpts can still be irrelevant.', 66, 60, 6),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def build(root=ROOT, output=None, source_commit=''):
    root = Path(root)
    publication = root / 'results/published'
    manifest = read(publication / 'manifest.json')
    # Verify the full selected publication tree, not only the displayed excerpts.
    for name, expected in {**manifest['files'], **manifest['frozen_source_files']}.items():
        if sha((root / name).read_bytes()) != expected:
            raise ValueError('Publication integrity failed: ' + name)
    source_files = {}
    passages, experiments = {}, []
    for phase, review_name, title, description, expected, calls, controls in PHASES:
        review_path = publication / 'reviews' / review_name / 'assessment.json'
        review = read(review_path)
        source_files[review_path.relative_to(root).as_posix()] = sha(review_path.read_bytes())
        assessments = {row['job_id']: row for row in review['reviews']}
        if len(assessments) != expected:
            raise ValueError('Unexpected assessment count: ' + phase)
        records = []
        for path in sorted((publication / 'raw' / phase / 'jobs').glob('*/record.json')):
            record = read(path)
            job = record['job']
            assessment = assessments[job['job_id']]
            if any(job.get(k) != assessment.get(k) for k in ('model', 'case_id', 'question', 'order')):
                raise ValueError('Assessment/job mismatch: ' + str(path))
            result = record.get('result', record)
            context = record['context']
            context_ids = []
            for passage in context:
                compact = {k: passage[k] for k in ('id', 'source', 'page', 'text')}
                if passage['id'] in passages and passages[passage['id']] != compact:
                    raise ValueError('Source ID reused for different text')
                passages[passage['id']] = compact
                context_ids.append(passage['id'])
            answer = result.get('candidate_answer')
            # Retain the raw incomplete channel separately; never count it as a final answer.
            raw_answer = result.get('raw_answer') or ''
            checks = result.get('checks', result.get('mechanical_checks', {}))
            stages = result.get('stages', [])
            relative = path.relative_to(root).as_posix()
            source_files[relative] = sha(path.read_bytes())
            row = {
                'id': job['job_id'], 'case_id': job['case_id'], 'question': job['question'],
                'model': job['model'], 'order': job['order'],
                'representation': job.get('representation', 'direct'),
                'status': record['status'], 'answer': answer, 'raw_answer': raw_answer,
                'error': result.get('error'), 'context_ids': context_ids,
                'assessment': assessment['assessment'], 'notes': assessment.get('notes', ''),
                'checks': checks, 'group_parser_limitation': assessment.get('group_parser_limitation', False),
                'raw_path': relative, 'review_path': review_path.relative_to(root).as_posix(),
                'raw_sha256': sha(path.read_bytes()),
                'seconds': round(sum(s.get('seconds', 0) or 0 for s in stages), 2),
                'model_calls': 0 if job['order'] == 'no_context' else 1,
            }
            if answer is not None and assessment.get('answer') is not None and answer != assessment['answer']:
                if not assessment['answer'].startswith('(See preserved raw answer'):
                    raise ValueError('Reviewed answer differs from recorded candidate: ' + job['job_id'])
                row['review_answer_note'] = assessment['answer']
            records.append(row)
        if len(records) != expected or sum(r['model_calls'] for r in records) != calls:
            raise ValueError('Unexpected recorded denominator: ' + phase)
        by_pair = {}
        for record in records:
            if record['order'] != 'no_context':
                by_pair.setdefault((record['model'], record['representation'], record['case_id']), {})[record['order']] = record
        for pair in by_pair.values():
            if set(pair) != {'retrieved', 'reversed'} or pair['retrieved']['context_ids'] != list(reversed(pair['reversed']['context_ids'])):
                raise ValueError('Evidence order pair is not an exact reversal')
        questions = {}
        for record in records:
            questions.setdefault(record['case_id'], record['question'])
        experiments.append({
            'id': phase, 'title': title, 'description': description,
            'calls': calls, 'controls': controls, 'pairs': len(by_pair),
            'models': sorted({r['model'] for r in records}),
            'representations': sorted({r['representation'] for r in records}),
            'cases': [{'id': key, 'question': value} for key, value in sorted(questions.items())],
            'reviewer': review['reviewer'], 'decision': review['decision'],
            'assessment_counts': dict(Counter(r['assessment'] for r in records if r['order'] != 'no_context')),
            'records': records,
        })
    data = {
        'schema_version': 1, 'source_commit': source_commit,
        'repository': 'https://github.com/Zuber18/EvidenceShift',
        'experiment_date': '2026-10-20', 'mode': 'recorded_results',
        'review_scope': 'Project-owner manual verification against saved sources; case-specific findings.',
        'passages': passages, 'experiments': experiments,
        'source_sha256': source_files,
    }
    target = Path(output) if output else root / 'website/data/experiments.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'Built {target}: {sum(len(e["records"]) for e in experiments)} records, {len(passages)} source passages.')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--source-commit', default='')
    args = parser.parse_args()
    build(output=args.output, source_commit=args.source_commit)
