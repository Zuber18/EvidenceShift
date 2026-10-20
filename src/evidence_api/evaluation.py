"""Mechanical checks and offline reports. No factual correctness inference."""
import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ABSTENTION = 'The supplied evidence does not answer this question.'
CHECK_VERSION = '1.0.0'


def inspect_answer(answer, chunks, done_reason):
    answer = answer if isinstance(answer, str) else ''
    citations = set(re.findall(r'\[([^\]]+)\]', answer))
    supplied = {c['id'] for c in chunks}
    contains = ABSTENTION[:-1].lower() in ' '.join(answer.lower().split())
    exact = answer.strip() == ABSTENTION
    issues = []
    if done_reason != 'stop':
        issues.append('incomplete_generation')
    if not answer.strip():
        issues.append('empty_answer')
    if citations - supplied:
        issues.append('unknown_citation_ids')
    if contains and not exact:
        issues.append('abstention_with_extra_text')
    if not exact and not citations:
        issues.append('missing_citations')
    if not chunks and not exact:
        issues.append('empty_context_requires_exact_abstention')
    if re.search(r'</?think\b', answer, re.I):
        issues.append('reasoning_markup_in_answer')
    return {
        'check_version': CHECK_VERSION,
        'completed': done_reason == 'stop', 'nonempty': bool(answer.strip()),
        'citation_ids': sorted(citations), 'unknown_citation_ids': sorted(citations - supplied),
        'citation_ids_valid': citations <= supplied, 'has_citations': bool(citations),
        'exact_abstention': exact, 'contains_prescribed_abstention': contains,
        'abstention_with_extra_text': contains and not exact,
        'mechanical_issues': issues, 'mechanical_pass': not issues,
        'factual_correctness': 'not_automatically_scored',
        'review_required': True,
    }


def assess_record(record):
    """Recompute checks from raw fields; never trust stale saved check flags."""
    missing = [k for k in ('answer', 'context', 'done_reason') if k not in record]
    malformed = ('answer' in record and not isinstance(record['answer'], str)) or (
        'context' in record and (not isinstance(record['context'], list) or
        any(not isinstance(c, dict) or not isinstance(c.get('id'), str) for c in record['context'])))
    context = record.get('context', []) if not malformed else []
    checks = inspect_answer(record.get('answer'), context, record.get('done_reason'))
    issues = checks['mechanical_issues']
    if record.get('error'):
        issues.insert(0, 'generation_error')
    if missing or malformed:
        issues.insert(0, 'missing_or_malformed_record_fields')
    checks['mechanical_pass'] = not issues
    checks['missing_fields'] = missing
    return checks


def summary_for(result, setup=None):
    rows = []
    for index, record in enumerate(result.get('records', [])):
        checks = assess_record(record)
        rows.append({
            'record_index': index, 'run_id': result.get('run_id'),
            'prompt_name': record.get('prompt_name'), 'variant': record.get('variant'),
            'answer_sha256': hashlib.sha256(str(record.get('answer', '')).encode()).hexdigest(),
            'answer': record.get('answer'), 'context': record.get('context'),
            'original_checks': record.get('checks'), 'error': record.get('error'),
            'done_reason': record.get('done_reason'), 'generated_tokens': record.get('generated_tokens'),
            'seconds': record.get('seconds'), 'checks': checks,
            'status': 'blocked' if not checks['mechanical_pass'] else 'needs_factual_review',
            'human_review': {'status': 'pending', 'reviewer': None, 'notes': None},
        })
    integrity = []
    if setup:
        req = setup.get('request', {})
        expected = {(p, v) for p in req.get('prompts', []) for v in req.get('variants', [])}
        observed = [(r['prompt_name'], r['variant']) for r in rows]
        integrity.extend('missing_record:' + repr(k) for k in sorted(expected - set(observed)))
        integrity.extend('unexpected_record:' + repr(k) for k in set(observed) - expected)
        if len(set(observed)) != len(observed):
            integrity.append('duplicate_prompt_variant_records')
    else:
        integrity.append('setup_unavailable_expected_record_count_not_verified')
    return {'check_version': CHECK_VERSION, 'run_id': result.get('run_id'),
            'record_count': len(rows), 'blocked_count': sum(r['status'] == 'blocked' for r in rows),
            'needs_factual_review_count': sum(r['status'] == 'needs_factual_review' for r in rows),
            'factual_pass_count': None,
            'review_labels': (setup or {}).get('request', {}),
            'review_checklist': [
                'Check every claim against the cited passage, not just the retrieved set.',
                'Check conditions, exceptions, uncertainty, and optional versus required actions.',
                'Check that every part of the question is answered.',
                'For abstentions with evidence, check whether the evidence actually answers the question.',
                'Do not treat a mechanical pass as factual correctness.'
            ],
            'issue_counts': dict(Counter(i for r in rows for i in r['checks']['mechanical_issues'])),
            'integrity_issues': integrity, 'rows': rows}


def write_reports(result, folder, setup=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    report = summary_for(result, setup)
    (folder / 'review.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    columns = ['run_id', 'record_index', 'prompt_name', 'variant', 'status', 'issues',
               'factual_review', 'answer', 'error', 'generated_tokens', 'seconds']
    with (folder / 'review.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in report['rows']:
            out = {k: row.get(k) for k in columns}
            out['issues'] = '; '.join(row['checks']['mechanical_issues'])
            out['factual_review'] = 'pending'
            # Prevent spreadsheet formula execution; JSON retains exact text.
            out = {k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
                   for k, v in out.items()}
            writer.writerow(out)
    return report


def archive_run(folder):
    folder = Path(folder)
    path = folder / 'review_bundle.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('setup.json', 'answers.jsonl', 'result.json', 'review.json', 'review.csv'):
            source = folder / name
            if source.exists():
                z.write(source, name)
    return path


def review_archive(source, output='results'):
    """Reassess saved ZIP or run directory without model calls or raw-data changes."""
    source = Path(source)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]
    destination = Path(output) / ('review_' + stamp)
    destination.mkdir(parents=True)
    if source.is_dir():
        blobs = {p.relative_to(source).as_posix(): p.read_bytes()
                 for p in source.rglob('*') if p.is_file() and p.name in ('setup.json', 'result.json', 'answers.jsonl', 'cases.json')}
    else:
        with zipfile.ZipFile(source) as z:
            blobs = {n: z.read(n) for n in z.namelist()
                     if Path(n).name in ('setup.json', 'result.json', 'answers.jsonl', 'cases.json')}
    parents = sorted({str(Path(n).parent) for n in blobs if Path(n).name != 'cases.json'})
    cases = {}
    for n, data in blobs.items():
        if Path(n).name == 'cases.json':
            loaded = json.loads(data)
            if isinstance(loaded, dict):
                cases.update(loaded)
    reports = []
    for index, parent in enumerate(parents):
        def get(name):
            return blobs.get(str(Path(parent) / name))
        setup = json.loads(get('setup.json')) if get('setup.json') else None
        result = json.loads(get('result.json')) if get('result.json') else {
            'run_id': (setup or {}).get('run_id'), 'records': []}
        lines = get('answers.jsonl')
        partial = []
        parse_error = False
        for line in (lines or b'').splitlines():
            try:
                partial.append(json.loads(line))
            except (ValueError, UnicodeError):
                parse_error = True
        if not get('result.json'):
            result['records'] = partial
        report = write_reports(result, destination / f'run_{index:03d}', setup)
        report['source_member'] = parent
        case = cases.get(Path(parent).name)
        if isinstance(case, dict):
            report['predeclared_review_criteria'] = case.get('review_criteria', [])
            report['reference_section'] = case.get('reference_section')
        if parse_error:
            report['integrity_issues'].append('malformed_answers_jsonl')
        if get('result.json') and lines is not None and partial != result.get('records'):
            report['integrity_issues'].append('result_json_answers_jsonl_mismatch')
        if not get('result.json'):
            report['integrity_issues'].append('partial_run_missing_result_json')
        (destination / f'run_{index:03d}' / 'review.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        reports.append(report)
    if not reports:
        raise ValueError('No saved run files found in source.')
    summary = {'source': str(source.resolve()), 'check_version': CHECK_VERSION,
               'record_count': sum(r['record_count'] for r in reports),
               'blocked_count': sum(r['blocked_count'] for r in reports),
               'factual_correctness': 'not_automatically_scored', 'runs': reports}
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    bundle = destination.with_suffix('.zip')
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in destination.rglob('*'):
            if p.is_file():
                z.write(p, p.relative_to(destination))
    return summary, bundle


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='Saved batch ZIP or run directory')
    parser.add_argument('--output', default='results')
    args = parser.parse_args()
    report, bundle = review_archive(args.source, args.output)
    print(f"Records: {report['record_count']}; blocked: {report['blocked_count']}")
    print(f'Saved: {bundle.resolve()}')
