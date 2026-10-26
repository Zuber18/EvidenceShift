"""Inspect saved pilot retrieval against accepted annotations; no model calls.

Run --self-test, then --pilot PATH_TO_PILOT_FOLDER_OR_ZIP from the project root.
Exact annotation overlap is a diagnostic, not semantic recall or accuracy:
other passages can support the same fact and annotations can include surplus text.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
BENCHMARK = ROOT / 'evaluation/benchmarks/real_documents_v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def norm(text):
    return re.sub(r'\s+', ' ', text).strip()


def intervals(body, text):
    """Return every occurrence; repeated text is explicitly ambiguous."""
    result = []; start = 0
    while text:
        found = body.find(text, start)
        if found < 0:
            break
        result.append((found, found + len(text)))
        start = found + 1
    return result


def covered(start, end, regions):
    clipped = sorted((max(start, a), min(end, b)) for a, b in regions if a < end and b > start)
    total = 0; right = start
    for a, b in clipped:
        total += max(0, b - max(a, right)); right = max(right, b)
    return total


class SavedPilot:
    def __init__(self, path):
        self.path = Path(path)
        self.archive = zipfile.ZipFile(path) if self.path.is_file() else None

    def raw(self, name):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe pilot member path.')
        return self.archive.read(name) if self.archive else (self.path / name).read_bytes()

    def json(self, name):
        return json.loads(self.raw(name))


def audit(pilot, benchmark):
    plan = pilot.json('plan.json')
    if sha((benchmark / 'freeze_manifest.json').read_bytes()) != plan['benchmark_freeze_sha256']:
        raise ValueError('Local benchmark freeze differs from the pilot freeze.')
    manifest = json.loads((benchmark / 'freeze_manifest.json').read_text())
    for name, expected in plan['prepared_files'].items():
        if sha(pilot.raw(name)) != expected:
            raise ValueError('Prepared file changed: ' + name)
    cases_bytes = (benchmark / 'cases.json').read_bytes()
    if sha(cases_bytes) != manifest['files']['cases.json']:
        raise ValueError('Accepted cases changed after the benchmark freeze.')
    prepared = pilot.json('prepared.json'); chunks = pilot.json('chunks.json')
    inventory = json.loads(cases_bytes)
    byid = {c['id']: c for c in inventory['cases']}
    selected = plan['question_ids']
    if len(selected) != 8 or len(set(selected)) != 8:
        raise ValueError('Expected the eight-question pilot.')
    results = []
    for cid in selected:
        case = byid[cid]
        if case['split'] != 'development' or case['annotation_status'] != 'accepted_gold':
            raise ValueError('Expected accepted development annotations only.')
        source_bodies = {}
        for sid in case['source_ids']:
            raw = pilot.raw('source_texts/' + sid + '.txt')
            expected = (benchmark / 'source_snapshots' / sid / 'body.txt').read_bytes()
            source_key = 'source_snapshots/' + sid + '/body.txt'
            if sha(expected) != manifest['files'][source_key]:
                raise ValueError('Source changed after the benchmark freeze: ' + sid)
            if raw != expected:
                raise ValueError('Local source differs from frozen pilot: ' + sid)
            source_bodies[sid] = raw.decode('utf-8')
        retrieved_ids = [c['id'] for c in prepared['contexts'][cid]]
        spans = []
        for unit in case['required_response_units']:
            for alternative_index, alternative in enumerate(unit.get('evidence_alternatives', [])):
                for span in alternative['all_required_spans']:
                    sid = span['source_id']; body = source_bodies[sid]
                    start, end = span['start_char'], span['end_char_exclusive']
                    if body[start:end] != span['exact_text']:
                        raise ValueError('Gold offset/text disagreement: ' + cid)
                    # Preserve one separator at boundaries by locating normalized
                    # span relative to the normalized prefix and full source.
                    normalized_body = norm(body)
                    prefix = norm(body[:start])
                    span_text = norm(span['exact_text'])
                    offset = normalized_body.find(span_text, max(0, len(prefix) - 1))
                    if offset < 0:
                        raise ValueError('Cannot map normalized annotation: ' + cid)
                    stop = offset + len(span_text)
                    candidates = []; selected_regions = []
                    for chunk in chunks[sid]:
                        matches = intervals(normalized_body, norm(chunk['text']))
                        overlaps = [(a, b) for a, b in matches if a < stop and b > offset]
                        if overlaps:
                            rank = retrieved_ids.index(chunk['id']) + 1 if chunk['id'] in retrieved_ids else None
                            candidates.append({'id': chunk['id'], 'retrieved_rank': rank,
                                               'ambiguous_text_locations': len(matches) > 1})
                            if rank is not None:
                                selected_regions.extend(overlaps)
                    spans.append({'unit_id': unit['id'], 'alternative_index': alternative_index,
                                  'source_id': sid, 'section': span.get('section'),
                                  'annotation_normalized_characters': len(span_text),
                                  'retrieved_annotation_characters': covered(offset, stop, selected_regions),
                                  'overlapping_index_chunks': candidates})
        results.append({'case_id': cid, 'question': case['question'],
                        'answerability': case['answerability'], 'retrieved_ids': retrieved_ids,
                        'annotation_spans': spans})
    return {'generation_calls': 0, 'questions_audited': len(results),
            'pilot_path': str(pilot.path), 'cases_sha256': sha(cases_bytes),
            'benchmark_freeze_sha256': plan['benchmark_freeze_sha256'],
            'prepared_file_hashes_valid': True,
            'interpretation': 'Normalized text overlap with annotated spans, not semantic evidence recall. Zero annotated overlap can coexist with equivalent supporting evidence elsewhere. Full overlap does not establish model correctness. Repeated chunk text is flagged as ambiguous.',
            'cases': results}


class Tests(unittest.TestCase):
    def test_whitespace_normalization(self):
        self.assertEqual(norm(' a\n  b '), 'a b')
    def test_overlap_does_not_double_count(self):
        self.assertEqual(covered(0, 10, [(0, 6), (4, 10)]), 10)
    def test_overlap_clips_to_annotation(self):
        self.assertEqual(covered(3, 7, [(0, 5), (6, 12)]), 3)
    def test_absent_text_has_no_locations(self):
        self.assertEqual(intervals('abc', 'xyz'), [])
    def test_repeated_text_is_preserved(self):
        self.assertEqual(intervals('ab ab', 'ab'), [(0, 2), (3, 5)])
    def test_unsafe_member_path_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): SavedPilot(directory).raw('../outside')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-test', action='store_true')
    modes.add_argument('--pilot', type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
    folder = ROOT / 'results' / ('retrieval_audit_' + stamp)
    folder.mkdir(parents=True)
    if args.self_test:
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        (folder / 'selftest.json').write_text(json.dumps({'tests': result.testsRun,
            'failures': len(result.failures), 'errors': len(result.errors),
            'generation_calls': 0, 'log': output.getvalue()}, indent=2) + '\n')
        print(output.getvalue()); print('Saved:', folder / 'selftest.json')
        return 0 if result.wasSuccessful() else 1
    try:
        report = audit(SavedPilot(args.pilot), BENCHMARK)
        (folder / 'audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        lines = ['# Saved pilot retrieval audit', '', report['interpretation'], '',
                 'Generation calls: 0. Questions audited: 8.', '']
        for case in report['cases']:
            lines += ['## ' + case['case_id'], '', case['question'], '',
                      '| Unit | Section | Annotated characters retrieved | Overlapping indexed chunks (retrieved rank) |',
                      '|---|---|---:|---|']
            for span in case['annotation_spans']:
                candidates = ', '.join(c['id'] + ' (' + str(c['retrieved_rank'] or 'not selected') + ')' for c in span['overlapping_index_chunks'])
                lines.append('| {} | {} | {}/{} | {} |'.format(span['unit_id'],
                    str(span['section']).replace('|', '/'), span['retrieved_annotation_characters'],
                    span['annotation_normalized_characters'], candidates))
            if not case['annotation_spans']:
                lines.append('| — | No positive evidence span; review absence against the declared source scope. | — | — |')
            lines.append('')
        (folder / 'AUDIT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print('Audited:', report['questions_audited'], 'development questions; generation calls: 0')
        print('Saved:', folder / 'audit.json'); print('Saved:', folder / 'AUDIT.md')
        return 0
    except Exception as exc:
        (folder / 'error.json').write_text(json.dumps({'error': f'{type(exc).__name__}: {exc}', 'generation_calls': 0}, indent=2) + '\n')
        print(type(exc).__name__ + ': ' + str(exc)); print('Saved:', folder / 'error.json')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
