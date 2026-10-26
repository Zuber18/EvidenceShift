"""Verify the additive development release without models or network access."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def check(root=ROOT):
    root=Path(root);manifest=json.loads((root/'results/development_20261026/manifest.json').read_text());errors=[]
    for name,expected in manifest['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:errors.append(name)
    if errors:raise ValueError('Development release integrity failed: '+', '.join(errors))
    data=json.loads((root/'website/data/development_regression_20261026.json').read_text())
    if len(data['records'])!=18 or len(data['models'])!=3 or sum(r['answer'] is not None for r in data['records'])!=17:raise ValueError('Regression counts differ.')
    if any(len([r for r in data['records'] if r['model']==model])!=6 for model in data['models']):raise ValueError('Unbalanced model counts.')
    return len(manifest['files'])
if __name__=='__main__':
    count=check();print('Development release integrity passed:',count,'files.');print('18 completed generations; 17 rendered answers; 1 blocked response. No semantic accuracy score or model calls.')
