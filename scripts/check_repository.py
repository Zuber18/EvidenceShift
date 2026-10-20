"""Check frozen publication integrity without model calls or runtime imports."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / 'results/published/manifest.json').read_text())
    errors = []
    for group in ('files', 'frozen_source_files'):
        for name, expected in manifest[group].items():
            path = root / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                errors.append('Missing or changed: ' + name)
    for phase, expected_records in [('model_matrix', 66), ('direct_answer', 33), ('direct_confirmation', 17)]:
        folder = root / 'results/published/raw' / phase
        records = sorted(folder.glob('jobs/*/record.json'))
        if len(records) != expected_records:
            errors.append(f'{phase}: expected {expected_records} records, found {len(records)}')
    folder = root / 'results/published/raw/direct_confirmation'
    records = [json.loads(p.read_text()) for p in sorted(folder.glob('jobs/*/record.json'))]
    by_case = {}
    controls = 0
    for record in records:
        job = record['job']
        if job['order'] == 'no_context':
            controls += 1
            if record.get('model_calls') != 0 or record.get('context'):
                errors.append('Invalid no-context control: ' + job['job_id'])
            continue
        by_case.setdefault(job['case_id'], {})[job['order']] = record
        if not record.get('complete') or not record.get('checks', {}).get('completed'):
            errors.append('Incomplete confirmation record: ' + job['job_id'])
    if len(by_case) != 8 or controls != 1:
        errors.append('Confirmation requires eight case pairs and one code control')
    for case_id, pair in by_case.items():
        if set(pair) != {'retrieved', 'reversed'}:
            errors.append('Missing context order: ' + case_id)
        elif pair['retrieved']['context'] != list(reversed(pair['reversed']['context'])):
            errors.append('Contexts are not exact reversals: ' + case_id)
        elif pair['retrieved']['job']['question'] != pair['reversed']['job']['question']:
            errors.append('Question changed under reversal: ' + case_id)
    if errors:
        raise ValueError('Repository integrity failed:\n' + '\n'.join(errors))
    return len(manifest['files']), len(manifest['frozen_source_files'])

if __name__ == '__main__':
    files, sources = check()
    print(f'Integrity passed: {files} publication files, {sources} frozen source files.')
    print('Raw records: matrix 66, direct baseline 33, confirmation 17. Eight confirmation reversal pairs checked.')
    print('No semantic accuracy score or live-model test was performed.')
