"""Prepare exact source-quantity choices from a saved v2 pilot; no model calls.

This is a deliberately narrow literal extractor for ordinary decimals followed
by declared units. It never infers labels, role, operation, source section or
correctness. It preserves all occurrences, including duplicate values. No gold
annotations or expected answers are read. Existing outputs remain unchanged.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import unittest
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = 'quantity-candidates-1.0.0'
# A small, explicit grammar avoids pretending to support arbitrary unit syntax.
UNITS = r'(?:hours?|minutes?|seconds?|days?|weeks?|months?|years?|credits?|kits?|kg|km|cm|mm|mg|g|m|s|%)'
PATTERN = re.compile(r'(?<![\w.,+−–-])(?P<value>[-+]?\d+(?:\.\d+)?)(?P<gap>\s+)(?P<unit>' + UNITS + r'(?:\s*/\s*(?:week|day|month|year)|\s+per\s+(?:week|day|month|year))?)(?![\w/-])', re.I)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def normalized_unit(unit):
    return re.sub(r'\s*/\s*', '/', ' '.join(unit.casefold().split()).replace(' per ', '/'))


def extract(context):
    """Return exact offsets and stable IDs, without picking semantic operands."""
    seen = set(); result = []
    for passage in context:
        cid, text = passage['id'], passage['text']
        if cid in seen:raise ValueError('Duplicate passage ID.')
        seen.add(cid)
        for match in PATTERN.finditer(text):
            start, end = match.span()
            # Refuse plausible comma/grouped/scientific continuations rather than
            # accepting a misleading suffix or partial quantity.
            value = match.group('value')
            if len(value) > 50:continue
            literal = text[start:end]
            result.append({'candidate_id':'q_' + digest([cid,start,end,literal])[:20],
                           'citation_id':cid, 'start':start, 'end':end,
                           'quote':literal, 'value':value, 'unit':match.group('unit'),
                           'normalized_unit':normalized_unit(match.group('unit')),
                           'surrounding_text':text[max(0,start-180):min(len(text),end+180)]})
    return result


def scope_filter(question, candidates):
    """Apply only an explicit temporal qualifier, never infer requested roles."""
    requested=[]
    for period, adjective in [('week','weekly'),('day','daily'),('month','monthly'),('year','yearly')]:
        if re.search(r'\b'+adjective+r'\b|\bper\s+'+period+r'\b|/\s*'+period+r'\b',question,re.I):requested.append(period)
    if len(requested)>1:raise ValueError('Multiple temporal scopes require a richer unit contract.')
    selected=[c for c in candidates if not requested or c['normalized_unit'].endswith('/'+requested[0])]
    return selected, requested


def resolve_selection(context, candidates, selection):
    """Resolve IDs through trusted extraction, rejecting model-typed quantities."""
    if set(selection)!={'operation','left_id','right_id'}:raise ValueError('Select operation and two IDs only.')
    if selection['operation'] not in ('difference','ratio'):raise ValueError('Unsupported operation.')
    by_id={c['candidate_id']:c for c in candidates}
    if len(by_id)!=len(candidates):raise ValueError('Candidate IDs are not unique.')
    fresh={c['candidate_id']:c for c in extract(context)}
    resolved=[]
    for field in ('left_id','right_id'):
        cid=selection[field]
        if cid not in by_id or fresh.get(cid)!=by_id[cid]:raise ValueError('Unknown or changed quantity candidate.')
        c=by_id[cid]
        resolved.append({k:c[k] for k in ('citation_id','quote','value','unit')})
    if selection['left_id']==selection['right_id']:raise ValueError('Distinct quantity occurrences are required.')
    return {'task':'arithmetic','operation':selection['operation'],'left':resolved[0],'right':resolved[1]}


def inspect_bundle(path):
    with zipfile.ZipFile(path) as archive:
        summary=json.loads(archive.read('summary.json'))
        if summary['version']!='tool-assisted-pilot-0.2.0':raise ValueError('Expected a v2 pilot bundle.')
        plan=json.loads(archive.read('plan.json'))
        for name,expected in plan['prepared_files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=expected:raise ValueError('Frozen input hash mismatch: '+name)
        prepared=json.loads(archive.read('prepared.json'))
        # Use declared arithmetic routes from the frozen run, not case IDs/gold.
        cases={r['case_id'] for r in summary['records'] if r.get('route')=='arithmetic'}
        rows=[]
        for case in prepared['inputs']:
            if case['id'] not in cases:continue
            context=prepared['contexts'][case['id']]
            original=extract(context); candidates, scopes=scope_filter(case['question'],original)
            reverse, reverse_scopes=scope_filter(case['question'],extract(list(reversed(context))))
            if {c['candidate_id']:c for c in candidates}!={c['candidate_id']:c for c in reverse}:raise ValueError('Candidate set changed with order.')
            rows.append({'case_id':case['id'],'question':case['question'],
                         'all_literal_quantities':original,'eligible_quantities':candidates,
                         'excluded_quantity_ids':[c['candidate_id'] for c in original if c not in candidates],
                         'explicit_temporal_scopes':scopes,'order_invariant_candidate_set':True,
                         'canonical_candidate_order':[c['candidate_id'] for c in candidates],
                         'reversed_candidate_order':[c['candidate_id'] for c in reverse],
                         'semantic_operand_selection_verified':False})
        if not rows:raise ValueError('No declared arithmetic routes found.')
    return {'version':VERSION,'source_bundle_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'generation_calls':0,'gold_annotations_read':False,'source_hashes_valid':True,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'cases':rows,'limits':'Exact ordinary decimal/unit extraction only. No role, direction, section or semantic entailment certification; no conversion or inferred units. Same candidate set under reversal does not prove order-invariant model selection. Candidate eligibility does not establish a correct answer.'}


class Tests(unittest.TestCase):
    def context(self,text):return [{'id':'s','text':text}]
    def test_source_offsets(self):
        ctx=self.context('Measure A 12.75 hours/week; measure B 4.20 hours/week.')
        for c in extract(ctx):self.assertEqual(ctx[0]['text'][c['start']:c['end']],c['quote'])
    def test_weekly_filter(self):
        cs=extract(self.context('A 12.75 hours/week. B 4.20 hours/week. C 7 hours.'))
        eligible,_=scope_filter('What is the weekly difference?',cs)
        self.assertEqual([c['value'] for c in eligible],['12.75','4.20'])
    def test_no_implicit_unit(self):self.assertEqual(extract(self.context('Mean 12.75; duration was weekly.')),[])
    def test_no_comma_or_scientific_partial(self):
        self.assertEqual(extract(self.context('1,234 hours; 1e3 hours; .25 hours; 1.2e-3 hours.')),[])
    def test_duplicate_occurrences_kept(self):
        cs=extract(self.context('A 4 hours. B 4 hours.'));self.assertEqual(len(cs),2);self.assertNotEqual(cs[0]['candidate_id'],cs[1]['candidate_id'])
    def test_order_invariant_ids(self):
        ctx=[{'id':'a','text':'4 hours/week.'},{'id':'b','text':'2 hours/week.'}]
        self.assertEqual(set(c['candidate_id'] for c in extract(ctx)),set(c['candidate_id'] for c in extract(ctx[::-1])))
    def test_unknown_id_refused(self):
        ctx=self.context('4 hours. 2 hours.');cs=extract(ctx)
        with self.assertRaises(ValueError):resolve_selection(ctx,cs,{'operation':'difference','left_id':'invented','right_id':cs[1]['candidate_id']})
    def test_model_typed_value_refused(self):
        ctx=self.context('4 hours. 2 hours.');cs=extract(ctx)
        with self.assertRaises(ValueError):resolve_selection(ctx,cs,{'operation':'difference','left_id':cs[0]['candidate_id'],'right_id':cs[1]['candidate_id'],'value':'9'})
    def test_changed_source_refused(self):
        cs=extract(self.context('4 hours. 2 hours.'))
        with self.assertRaises(ValueError):resolve_selection(self.context('5 hours. 2 hours.'),cs,{'operation':'difference','left_id':cs[0]['candidate_id'],'right_id':cs[1]['candidate_id']})
    def test_resolved_operands_use_existing_arithmetic_guard(self):
        spec=importlib.util.spec_from_file_location('quantity_tools',ROOT/'evidence_reasoning_tools.py');tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(tools)
        ctx=self.context('12.75 hours/week and 4.20 hours/week');cs=extract(ctx)
        sel=resolve_selection(ctx,cs,{'operation':'difference','left_id':cs[0]['candidate_id'],'right_id':cs[1]['candidate_id']})
        result=tools.calculate(ctx,sel['operation'],sel['left'],sel['right'])
        self.assertEqual(Decimal(result['value']),Decimal('8.55'));self.assertFalse(result['semantic_operand_selection_verified'])
    def test_roles_not_silently_inferred(self):
        cs=extract(self.context('Control 8 hours/week. Treatment 12 hours/week.'))
        self.assertEqual(len(cs),2);self.assertTrue(all('role' not in c for c in cs))
    def test_distinct_occurrences_required(self):
        ctx=self.context('4 hours.');cs=extract(ctx);cid=cs[0]['candidate_id']
        with self.assertRaises(ValueError):resolve_selection(ctx,cs,{'operation':'difference','left_id':cid,'right_id':cid})
    def test_multiple_scopes_refused(self):
        with self.assertRaises(ValueError):scope_filter('Compare weekly and monthly values.',[])
    def test_signs_and_per_units(self):
        cs=extract(self.context('A -2.5 hours per week. B +1 hours/week.'))
        self.assertEqual([c['value'] for c in cs],['-2.5','+1']);self.assertEqual(cs[0]['normalized_unit'],'hours/week')


def main():
    parser=argparse.ArgumentParser(description=__doc__);g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--self-test',action='store_true');g.add_argument('--latest',action='store_true');g.add_argument('--bundle',type=Path)
    args=parser.parse_args()
    if args.self_test:
        stream=io.StringIO()
        result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        out=ROOT/'results'/('quantity_candidate_selftest_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]);out.mkdir(parents=True)
        (out/'selftest.json').write_text(json.dumps({'version':VERSION,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'model_calls':0,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'log':stream.getvalue()},indent=2)+'\n')
        print(stream.getvalue());print('Saved:',out/'selftest.json')
        return 0 if result.wasSuccessful() else 1
    source=args.bundle
    if args.latest:
        paths=list((ROOT/'results').glob('tool_assisted_pilot_v2_*/tool_assisted_bundle.zip'))
        if not paths:parser.error('No saved v2 bundle found. Use --bundle PATH.')
        source=max(paths,key=lambda p:p.stat().st_mtime_ns)
    report=inspect_bundle(source)
    out=ROOT/'results'/('quantity_candidates_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]);out.mkdir(parents=True)
    (out/'candidates.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    lines=['# Source quantity candidates','',report['limits'],'']
    for c in report['cases']:
        lines += ['## '+c['case_id'],'',c['question'],'','| ID | Value | Source unit | Passage |','|---|---|---|---|']
        lines += [f"| {q['candidate_id']} | {q['value']} | {q['unit']} | {q['citation_id']} |" for q in c['eligible_quantities']]
        lines += ['',f"Eligible candidates: {len(c['eligible_quantities'])}; order-invariant set: {c['order_invariant_candidate_set']}.",'']
    (out/'CANDIDATES.md').write_text('\n'.join(lines))
    with zipfile.ZipFile(out/'quantity_candidates_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('candidates.json','CANDIDATES.md'):z.write(out/name,name)
        z.write(Path(__file__),'code_snapshot/prepare_quantity_candidates.py')
    for c in report['cases']:print(c['case_id']+':',len(c['eligible_quantities']),'eligible literal quantities; order-invariant set:',c['order_invariant_candidate_set'])
    print('Model calls: 0');print('Saved:',out/'quantity_candidates_bundle.zip');return 0


if __name__=='__main__':raise SystemExit(main())
