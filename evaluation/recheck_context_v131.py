"""Recheck saved v1.3 candidates without regenerating answers or changing delivery."""
import argparse
import csv
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from evidence_api import context_audit_v131 as audit


def read_benchmark(source):
    source = Path(source)
    if source.is_dir():
        raw = (source / 'results.json').read_bytes()
        setup_raw = (source / 'setup.json').read_bytes()
    else:
        with zipfile.ZipFile(source) as archive:
            raw = archive.read('results.json')
            setup_raw = archive.read('setup.json')
    result, setup = json.loads(raw), json.loads(setup_raw)
    if not result.get('complete') or setup.get('pipeline_version') != '1.3.0':
        raise ValueError('Select a completed v1.3.0 benchmark, not a baseline or another diagnostic.')
    return result, setup, raw, setup_raw


def latest_benchmark(results):
    candidates = []
    for folder in Path(results).glob('benchmark_v13_*'):
        try:
            read_benchmark(folder)
            candidates.append(folder)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
    if not candidates:
        raise ValueError('No completed v1.3.0 benchmark found under results/. Use --source PATH explicitly.')
    return max(candidates, key=lambda path: path.name)


def recheck(source, output, client, model='qwen3:8b'):
    benchmark, original_setup, raw, setup_raw = read_benchmark(source)
    inventory = client.list().model_dump(mode='json')
    if model not in {item['model'] for item in inventory.get('models', [])}:
        raise ValueError('The requested checker model is not installed: ' + model)
    options = original_setup['preserved_plan']['options']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]
    folder = Path(output) / ('context_recheck_v131_' + stamp)
    folder.mkdir(parents=True)
    (folder / 'previous_benchmark_results.json').write_bytes(raw)
    (folder / 'previous_benchmark_setup.json').write_bytes(setup_raw)
    controls = json.loads((ROOT / 'tests/fixtures/context_audit_controls.json').read_text())
    tasks = []
    for record in benchmark['records']:
        result = record.get('result', {})
        if not result.get('structured_answer', {}).get('claims'):
            continue
        tasks.append({
            'name': record['case_id'] + '/' + record['variant'], 'kind': 'saved_v13_candidate',
            'question': result['question'], 'candidate_answer': result['candidate_answer'],
            'context': result['original_record']['context'], 'original_status': result['status'],
            'original_run_id': result['run_id'],
            'expected_context_result': ('context_objection_confirmed'
                                        if record['case_id'] == 'authentication_vs_refusal' else 'context_clear'),
        })
    tasks.extend(controls)
    setup = {'audit_version': audit.VERSION, 'checker_model': model, 'inventory': inventory,
             'source_results_sha256': hashlib.sha256(raw).hexdigest(), 'options': options,
             'source_benchmark': str(Path(source).resolve()), 'task_count': len(tasks),
             'scope': 'Saved-answer context diagnostic with known negative controls; not end-to-end delivery or held-out accuracy.',
             'control_definitions': controls}
    (folder / 'setup.json').write_text(json.dumps(setup, indent=2), encoding='utf-8')
    rows, records = [], []

    def checkpoint(complete):
        payload = {'complete': complete, 'diagnostic_only': True, 'rows': rows, 'records': records}
        temp = folder / 'results.tmp'
        temp.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        temp.replace(folder / 'results.json')
        if rows:
            with (folder / 'results.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

    checkpoint(False)
    for task in tasks:
        print(task['name'], flush=True)
        metadata = {k: v for k, v in task.items() if k not in ['question', 'candidate_answer', 'context']}
        result, bundle = audit.audit(task['question'], task['candidate_answer'], task['context'],
                                     client, model, options, folder / 'runs', metadata)
        rows.append({'name': task['name'], 'kind': task['kind'],
                     'expected_context_result': task['expected_context_result'], 'status': result['status'],
                     'expectation_met': result['status'] == task['expected_context_result'],
                     'calls': sum(s['status'] != 'skipped_input' for s in result['stages']),
                     'seconds': round(sum(s.get('seconds', 0) for s in result['stages']), 2),
                     'error': result.get('error'), 'bundle': str(bundle.relative_to(folder))})
        records.append({'name': task['name'], 'kind': task['kind'], 'result': result})
        checkpoint(False)
    checkpoint(True)
    bundle = folder / 'context_recheck_bundle.zip'
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob('*'):
            if path.is_file() and path != bundle and path.name != 'grounded_bundle.zip':
                archive.write(path, path.relative_to(folder))
    print('Saved:', bundle.resolve())
    print('Diagnostic only: no original answer or delivery status was changed.')
    return rows, bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--latest', action='store_true')
    choice.add_argument('--source')
    parser.add_argument('--output', default=str(ROOT / 'results'))
    parser.add_argument('--model', default='qwen3:8b')
    args = parser.parse_args()
    from ollama import Client
    source = latest_benchmark(ROOT / 'results') if args.latest else Path(args.source)
    print('Using saved benchmark:', source)
    recheck(source, args.output, Client(host=os.environ.get('OLLAMA_HOST', 'http://localhost:11434'), timeout=180.0), args.model)


if __name__ == '__main__':
    main()
