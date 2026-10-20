"""Replay eight saved questions in both orders; save all outputs inside the project.

Run: python evaluation/run_handle_replay.py
Optional: --bundle results/path/local_upload_smoke_bundle.zip
This measures the evidence-ID selection revision; source support needs separate assessment.
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'src'))
from evidence_api.local_upload_v21 import Workspace

PDF_SHA256 = 'cd4206e9dfc52aabb655b27e3935da81b18f244209e30f8304b249f9156b96c9'
CASE_SUFFIXES = ['1f939d31', '7f2d1848', '55b47cfd', '5c1223d8',
                 '2d84d462', 'e9abdb27', 'ae8d2dc4', 'c403395f']


def source_document(bundle=None):
    if bundle:
        with zipfile.ZipFile(bundle) as archive:
            session = json.loads(archive.read('session.json'))
            for doc in session['documents']:
                if doc['sha256'] == PDF_SHA256:
                    return doc['source'], archive.read(doc['archive_path'])
        raise ValueError('Bundle does not contain the original Gift of the Magi PDF')
    for path in sorted((ROOT/'results').glob('local_upload_session_*/session.json'), reverse=True):
        session = json.loads(path.read_text())
        for doc in session['documents']:
            if doc['sha256'] == PDF_SHA256:
                source = (path.parent/doc['archive_path']).resolve()
                if not source.is_relative_to(path.parent.resolve()):
                    raise ValueError('Archived source path escapes session directory')
                if source.is_file():
                    return doc['source'], source.read_bytes()
    raise ValueError('Saved PDF not found under results/. Use --bundle with a saved session ZIP.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    name, raw = source_document(args.bundle)
    if hashlib.sha256(raw).hexdigest() != PDF_SHA256:
        raise ValueError('Archived PDF bytes do not match the saved baseline')
    fixture = json.loads((ROOT/'evaluation/local_upload_regression.json').read_text())
    cases = [next(c for c in fixture['cases'] if c['id'].endswith(s)) for s in CASE_SUFFIXES]
    workspace = Workspace(ROOT, [(name, raw)])
    try:
        (workspace.folder/'replay_plan.json').write_text(json.dumps({
            'scope': 'Matched questions and evidence orders; same retrieval policy as 2.0.0; ID-selection schema/output revision',
            'questions': [{'baseline_run_id': c['id'], 'question': c['question']} for c in cases],
            'variants': ['retrieved', 'reversed'], 'code_controls': 2,
            'expected_answers_sent_to_model': False,
            'automatic_semantic_accuracy_scoring': False}, indent=2), encoding='utf-8')
        total = len(cases)*2+2
        index = 0
        for case in cases:
            for variant in ('retrieved', 'reversed'):
                index += 1
                print(f'[{index}/{total}] {variant}: {case["question"]}', flush=True)
                run = workspace.ask(case['question'], variant)
                workspace.export()  # Persist a usable complete export after every attempt.
                print('  '+run['status'], flush=True)
        for case in cases[:2]:
            index += 1
            print(f'[{index}/{total}] no_context code control', flush=True)
            workspace.ask(case['question'], 'no_context')
            workspace.export()
        summary = workspace.folder/'replay_report.md'
        summary.write_text('# Source-first replay\n\n18 attempts: eight matched question pairs and two code controls.\n\n'
            'Mechanical statuses and exact quotations are in runs.csv and each run trace. '
            'They are not automatic semantic accuracy scores. Retrieval coverage matches version 2.0.0. The change combines '
            'context budgeting, prompt and output-mode changes; it is not a single-factor experiment.\n', encoding='utf-8')
        bundle = workspace.export()
        print('Saved:', bundle, flush=True)
        print('Upload this ZIP for source-based assessment. No separate Word report is needed.', flush=True)
    finally:
        workspace.close()


if __name__ == '__main__':
    main()
