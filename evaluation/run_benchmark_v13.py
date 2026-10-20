"""Run the preserved development cases through grounded v1.3 with local Ollama."""
import argparse
import copy
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
from evidence_api import grounded_v13 as grounded


def variants(case):
    if len(case['context']) > 1:
        return ['retrieved', 'reversed', 'no_context']
    return ['retrieved', 'no_context']


def checkpoint(folder, setup, rows, records, complete):
    payload = {'complete': complete, 'pipeline_version': grounded.VERSION,
               'setup': setup, 'rows': rows, 'records': records}
    temporary = folder / 'results.tmp'
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(folder / 'results.json')
    if rows:
        with (folder / 'results.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def run_benchmark(models, output, client, cases_path=None):
    plan_path = Path(cases_path or ROOT / 'evaluation/cases.json')
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw)
    if plan['pipeline_version'] != '1.2.1':
        raise ValueError('Expected the preserved v1.2.1 case plan; do not modify it for this comparison.')
    inventory = client.list().model_dump(mode='json')
    installed = {item['model'] for item in inventory.get('models', [])}
    missing = set(models) - installed
    if missing:
        raise ValueError('Install the exact model tags in Ollama first: ' + ', '.join(sorted(missing)))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]
    folder = Path(output) / ('benchmark_v13_' + stamp)
    folder.mkdir(parents=True)
    setup = {
        'pipeline_version': grounded.VERSION, 'source_plan_sha256': hashlib.sha256(plan_raw).hexdigest(),
        'preserved_plan': plan, 'requested_models': models, 'installed_models': inventory,
        'verifier_output_tokens': grounded.VERIFIER_OUTPUT_TOKENS,
        'scope': 'Development regression cases, not held-out evaluation. Original cases and labels unchanged.',
    }
    (folder / 'setup.json').write_text(json.dumps(setup, indent=2), encoding='utf-8')
    rows, records = [], []
    checkpoint(folder, setup, rows, records, False)
    for model in models:
        for case in plan['cases']:
            for variant in variants(case):
                print(f"{model} / {case['id']} / {variant}", flush=True)
                source_id = 'input_' + uuid4().hex[:12]
                source = folder / 'inputs' / source_id
                source.mkdir(parents=True)
                context = copy.deepcopy(case['context'])
                if variant == 'reversed':
                    context.reverse()
                elif variant == 'no_context':
                    context = []
                source_setup = {
                    'run_id': source_id, 'request': {'question': case['question']},
                    'model': model, 'options': plan['options'], 'think': plan['think'],
                    'input_only': True, 'source_run_id': case.get('source_run_id'),
                    'review_criteria': case['review_criteria'],
                }
                original = {'prompt_name': 'benchmark_input', 'variant': variant,
                            'context': context, 'user_prompt': json.dumps({'question': case['question'], 'evidence': context}),
                            'input_only': True}
                (source / 'setup.json').write_text(json.dumps(source_setup, indent=2), encoding='utf-8')
                (source / 'result.json').write_text(json.dumps({'run_id': source_id, 'records': [original]}), encoding='utf-8')
                row = {'model': model, 'case_id': case['id'], 'variant': variant,
                       'status': 'run_error', 'calls': 0, 'seconds': 0, 'tokens': 0,
                       'context_review_complete': False, 'claim_reviews': 0,
                       'candidate_answer': None, 'delivery_answer': None, 'error': None, 'bundle': None}
                record = {'model': model, 'case_id': case['id'], 'variant': variant,
                          'review_criteria': case['review_criteria']}
                try:
                    result, bundle = grounded.run(source, folder / 'runs', client,
                                                  prompt='benchmark_input', variant=variant, thinking_mode='off')
                    row.update(
                        status=result['status'],
                        calls=sum(stage['status'] != 'skipped_input' for stage in result['stages']),
                        seconds=round(sum(stage.get('seconds', 0) for stage in result['stages']), 2),
                        tokens=sum(stage.get('generated_tokens') or 0 for stage in result['stages']),
                        context_review_complete=result['context_review_complete'],
                        claim_reviews=len(result['claim_reviews']),
                        candidate_answer=result['candidate_answer'], delivery_answer=result['delivery_answer'],
                        error=result.get('error'), bundle=str(bundle.relative_to(folder)),
                    )
                    record.update(result=result, bundle=row['bundle'])
                except Exception as exc:
                    row['error'] = f'{type(exc).__name__}: {exc}'
                    record['error'] = row['error']
                rows.append(row)
                records.append(record)
                checkpoint(folder, setup, rows, records, False)
    checkpoint(folder, setup, rows, records, True)
    bundle = folder / 'benchmark_bundle.zip'
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob('*'):
            if path.is_file() and path != bundle and path.name != 'grounded_bundle.zip':
                archive.write(path, path.relative_to(folder))
    return rows, bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', default=['qwen3:8b'])
    parser.add_argument('--output', default=str(ROOT / 'results'))
    args = parser.parse_args()
    from ollama import Client
    client = Client(host=os.environ.get('OLLAMA_HOST', 'http://localhost:11434'), timeout=180.0)
    rows, bundle = run_benchmark(args.models, args.output, client)
    print('Pipeline inputs:', len(rows))
    print('Generation calls:', sum(row['calls'] for row in rows))
    print('Saved:', bundle.resolve())
    print('candidate_ready means structural/advisory checks passed, not factual certification.')


if __name__ == '__main__':
    main()
