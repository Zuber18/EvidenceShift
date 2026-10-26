"""Audit a completed v2 bundle without model calls or changes to saved outputs.

Accept a comma after a quoted print call when reading its declared output.
This checks printed lists only; prose and citation entailment require review.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = 'tool-pilot-offline-audit-1.0.0'


def tools_module(root):
    spec = importlib.util.spec_from_file_location('saved_trace_tools', root / 'evidence_reasoning_tools.py')
    tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools)
    return tools


def declared_outputs(tools, answer, question):
    """Normalize only punctuation between a print call and its output verb."""
    normalized = answer
    for call in reversed(tools.print_calls(answer)):
        tail = normalized[call['end']:]
        match = re.match(r'(\s*`?\s*),\s*(?=(?:outputs?|prints?)\b)', tail, re.I)
        if match:
            normalized = normalized[:call['end']] + match.group(1) + ' ' + tail[match.end():]
    return tools.declared_outputs(normalized, question)


def inspect_bundle(path, root=ROOT):
    tools = tools_module(root)
    with zipfile.ZipFile(path) as archive:
        summary = json.loads(archive.read('summary.json'))
        plan = json.loads(archive.read('plan.json'))
        if summary['version'] != 'tool-assisted-pilot-0.2.0':
            raise ValueError('Expected a completed v2 pilot bundle.')
        for name, expected in plan['prepared_files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('Frozen file hash mismatch: ' + name)
        prepared = json.loads(archive.read('prepared.json'))
        questions = {c['id']: c['question'] for c in prepared['inputs']}
        rows = []
        stage_records = []
        for name in archive.namelist():
            if re.fullmatch(r'jobs/[^/]+/(planner|answer)/record.json', name):
                record = json.loads(archive.read(name)); stage_records.append(record)
                raw_name = name.removesuffix('record.json') + 'stream.ndjson'
                if raw_name in archive.namelist():
                    chunks = [json.loads(line) for line in archive.read(raw_name).splitlines() if line.strip()]
                    raw_answer = ''.join(c.get('message', {}).get('content', '') for c in chunks)
                    if raw_answer != record['answer']:raise ValueError('Saved content differs from raw stream: ' + name)
        for row in summary['records']:
            result = {'case_id':row['case_id'], 'order':row['order'],
                      'original_pipeline_status':row['pipeline_status'],
                      'trace_audit':'not_applicable', 'whole_answer_verified':False}
            if (row.get('tool') or {}).get('task') == 'trace':
                try:
                    observed = declared_outputs(tools, row['candidate_answer'], questions[row['case_id']])
                    expected = row['tool']['result']['outputs']
                    result.update(trace_audit='matches' if observed == expected else 'mismatch',
                                  declared_outputs=observed, source_derived_outputs=expected)
                except (ValueError, SyntaxError) as exc:
                    result.update(trace_audit='not_checkable', reason=str(exc))
            if row['pipeline_status'] == 'tool_selection_failed_preserved':
                state = json.loads(archive.read('jobs/' + row['id'] + '/state.json'))
                result['preserved_selection_error'] = state.get('error')
            rows.append(result)
        if len(stage_records) != summary['reserved_attempt_slots']:raise ValueError('Attempt counts differ.')
        return {'version':VERSION, 'source_bundle':str(path.resolve()),
                'source_bundle_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'frozen_file_hashes_valid':True, 'raw_stream_content_matches':True,
                'recorded_generation_attempts':len(stage_records), 'audit_generation_calls':0,
                'stage_status_counts':dict(Counter(r['status'] for r in stage_records)),
                'trace_audit_counts':dict(Counter(r['trace_audit'] for r in rows)),
                'records':rows, 'semantic_accuracy':None,
                'limits':'Offline printed-list comparison only. Original statuses and outputs remain unchanged. No semantic certification or rerun.'}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tools = tools_module(ROOT)
        self.q = 'Use a fresh function definition. print(g(1)), print(g(2, [])), print(g(3)).'
        self.answer = '`print(g(1))`, outputs `[1]`. `print(g(2, []))`, outputs `[2]`. `print(g(3))`, outputs `[1, 3]`.'
    def test_comma_wrapped_calls(self):self.assertEqual(declared_outputs(self.tools,self.answer,self.q),[[1],[2],[1,3]])
    def test_original_format(self):self.assertEqual(declared_outputs(self.tools,self.answer.replace('`, outputs','` outputs'),self.q),[[1],[2],[1,3]])
    def test_wrong_values_retained(self):self.assertEqual(declared_outputs(self.tools,self.answer.replace('[1, 3]','[1, 2, 3]'),self.q)[-1],[1,2,3])
    def test_negation_refused(self):
        with self.assertRaises(ValueError):declared_outputs(self.tools,self.answer.replace('outputs','does not output'),self.q)
    def test_missing_call_refused(self):
        with self.assertRaises(ValueError):declared_outputs(self.tools,self.answer.split('. ')[0],self.q)
    def test_reordered_call_refused(self):
        with self.assertRaises(ValueError):declared_outputs(self.tools,self.answer.replace('g(1)','g(9)'),self.q)
    def test_extra_call_refused(self):
        with self.assertRaises(ValueError):declared_outputs(self.tools,self.answer+' print(g(4)) outputs [4].',self.q)
    def test_no_mutation(self):
        original=self.answer;declared_outputs(self.tools,self.answer,self.q);self.assertEqual(self.answer,original)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--bundle',type=Path);group.add_argument('--latest',action='store_true');group.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        return 0 if result.wasSuccessful() else 1
    path=args.bundle
    if args.latest:
        candidates=list((ROOT/'results').glob('tool_assisted_pilot_v2_*/tool_assisted_bundle.zip'))
        if not candidates:parser.error('No v2 result bundle found under project results; use --bundle PATH.')
        path=max(candidates,key=lambda p:p.stat().st_mtime_ns)
    report=inspect_bundle(path)
    out=ROOT/'results'/('tool_pilot_v2_offline_audit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8])
    out.mkdir(parents=True)
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    text=['# Offline v2 trace audit','',report['limits'],'',f"Model calls: 0. Original recorded attempts: {report['recorded_generation_attempts']}.",'']
    for r in report['records']:text.append(f"- {r['case_id']} / {r['order']}: {r['trace_audit']} (saved status: {r['original_pipeline_status']})")
    (out/'AUDIT.md').write_text('\n'.join(text)+'\n')
    print('Source:',path);print('Trace audit:',report['trace_audit_counts']);print('Model calls: 0');print('Saved:',out)
    return 0


if __name__=='__main__':raise SystemExit(main())
