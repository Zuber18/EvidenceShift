"""Small evidence-anchored arithmetic and restricted list-state tools.

--self-test runs offline controls. --audit-comparison reads saved responses and
checks only supported Python traces requested in the question. It never reads
benchmark gold, calls a model, changes answers or certifies free-text semantics.
Arithmetic requires explicit operand selections; source anchoring and arithmetic
can be checked, but selecting the right operands for a question remains separate.
"""
from __future__ import annotations
import argparse
import ast
import copy
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import io
import json
from pathlib import Path
import re
import unittest
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = 'evidence-reasoning-tools-0.1.0'


class NotChecked(ValueError):
    """The requested operation is outside the declared tool contract."""


def evidence_map(context):
    if len(context) > 40 or len({c['id'] for c in context}) != len(context):
        raise NotChecked('Too many or duplicate evidence IDs.')
    return {c['id']: c['text'] for c in context}


def operand(context, selection):
    sources = evidence_map(context)
    cid = selection['citation_id']; quote = selection['quote']
    if cid not in sources or not quote or len(quote) > 20000 or quote not in sources[cid]:
        raise NotChecked('Operand quotation is not an exact span in its cited passage.')
    value = str(selection['value']); unit = selection['unit']
    if not re.fullmatch(r'[-+]?\d+(?:\.\d+)?', value) or len(value) > 50:
        raise NotChecked('Expected a bounded ordinary decimal literal.')
    if not isinstance(unit, str) or not unit.strip() or len(unit) > 64:
        raise NotChecked('An explicit bounded source unit is required.')
    # The literal quantity and unit must be adjacent in the exact quoted text.
    pattern = r'(?<![\w.])' + re.escape(value) + r'\s+' + re.escape(unit) + r'(?![\w/-])'
    if not re.search(pattern, quote):
        raise NotChecked('Selected literal quantity/unit does not occur together in the quoted span.')
    return Decimal(value), ' '.join(unit.split()).casefold()


def calculate(context, operation, left, right):
    a, unit_a = operand(context, left); b, unit_b = operand(context, right)
    if unit_a != unit_b:
        raise NotChecked('Unit conversion is not supported; operands must use the same explicit unit.')
    with localcontext() as settings:
        settings.prec = 110
        if operation == 'difference': value, unit = a - b, unit_a
        elif operation == 'ratio':
            if b == 0: raise NotChecked('Division by zero.')
            value, unit = a / b, 'dimensionless'
        else: raise NotChecked('Supported operations are difference and ratio.')
    return {'operation': operation, 'value': format(value, 'f'), 'unit': unit,
            'evidence_ids': [left['citation_id'], right['citation_id']],
            'source_literal_anchors_checked': True, 'arithmetic_checked': True,
            'semantic_operand_selection_verified': False,
            'limits': 'Correctness is conditional on the selected operands and operation. Source occurrence does not prove that the operands answer the question. No implicit unit conversion or rounding.'}


def balanced(text, start, opening='(', closing=')'):
    if start >= len(text) or text[start] != opening: raise NotChecked('Missing opening delimiter.')
    depth = 0; quote = None; escaped = False
    for index in range(start, min(len(text), start + 2000)):
        char = text[index]
        if quote:
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == quote: quote = None
        elif char in ('"', "'"): quote = char
        elif char == opening: depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0: return text[start:index + 1], index + 1
    raise NotChecked('Unbalanced or oversized expression.')


def print_calls(text):
    found = []
    for match in re.finditer(r'\bprint\s*\(', text):
        parentheses, end = balanced(text, text.index('(', match.start()))
        source = 'print' + parentheses
        try: node = ast.parse(source, mode='eval').body
        except SyntaxError as exc: raise NotChecked('Unparseable print call.') from exc
        if node.keywords or len(node.args) != 1 or not isinstance(node.args[0], ast.Call):
            raise NotChecked('Expected print of a single explicit function call.')
        call = node.args[0]
        if not isinstance(call.func, ast.Name) or call.keywords or not 1 <= len(call.args) <= 2:
            raise NotChecked('Only simple positional calls are supported.')
        found.append({'call': call, 'source': source, 'start': match.start(), 'end': end})
    return found


def primitive(node):
    if sum(1 for _ in ast.walk(node)) > 50: raise NotChecked('Argument expression is too large.')
    try: value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError) as exc: raise NotChecked('Arguments must be literal values, not expressions.') from exc
    if type(value) in (int, float, str, bool, type(None)):
        if isinstance(value, str) and len(value) > 200: raise NotChecked('String argument too long.')
        return value
    if isinstance(value, list) and len(value) <= 30 and all(type(x) in (int, float, str, bool, type(None)) for x in value):
        return value
    raise NotChecked('Unsupported literal type.')


def function_contract(source):
    if len(source) > 4000: raise NotChecked('Function source too long.')
    try: tree = ast.parse(source)
    except SyntaxError as exc: raise NotChecked('Function source is not parseable.') from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise NotChecked('Expected exactly one ordinary function definition.')
    fn = tree.body[0]; args = fn.args
    if fn.decorator_list or fn.returns or args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs or len(args.args) != 2 or len(args.defaults) != 1:
        raise NotChecked('Unsupported function signature.')
    if any(a.annotation is not None for a in args.args): raise NotChecked('Annotated signatures are outside this tool contract.')
    item, bag = (a.arg for a in args.args)
    if item == bag: raise NotChecked('Duplicate parameter names are invalid.')
    default = args.defaults[0]
    mode = 'list' if isinstance(default, ast.List) and not default.elts else 'none' if isinstance(default, ast.Constant) and default.value is None else None
    if mode is None: raise NotChecked('Default must be [] or None.')
    body = fn.body; guarded = False
    if mode == 'none':
        if len(body) != 3 or not isinstance(body[0], ast.If): raise NotChecked('Expected an explicit None-to-new-list guard.')
        guard = body[0]; test = guard.test
        if not (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == bag and len(test.ops) == 1 and isinstance(test.ops[0], ast.Is) and len(test.comparators) == 1 and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None and not guard.orelse and len(guard.body) == 1):
            raise NotChecked('Unsupported None guard.')
        assignment = guard.body[0]
        if not (isinstance(assignment, ast.Assign) and len(assignment.targets) == 1 and isinstance(assignment.targets[0], ast.Name) and assignment.targets[0].id == bag and isinstance(assignment.value, ast.List) and not assignment.value.elts):
            raise NotChecked('Guard must create a fresh empty list.')
        body = body[1:]; guarded = True
    if len(body) != 2 or not isinstance(body[0], ast.Expr) or not isinstance(body[0].value, ast.Call):
        raise NotChecked('Only one append followed by return is supported.')
    append = body[0].value; ret = body[1]
    if not (isinstance(append.func, ast.Attribute) and isinstance(append.func.value, ast.Name) and append.func.value.id == bag and append.func.attr == 'append' and len(append.args) == 1 and isinstance(append.args[0], ast.Name) and append.args[0].id == item and not append.keywords and isinstance(ret, ast.Return) and isinstance(ret.value, ast.Name) and ret.value.id == bag):
        raise NotChecked('Function body differs from supported append/return semantics.')
    return fn.name, mode, guarded


def trace(question, context, citation_id, function_source):
    sources = evidence_map(context)
    if citation_id not in sources or function_source not in sources[citation_id]:
        raise NotChecked('Function source is not an exact quoted evidence span.')
    if not re.search(r'\bfresh\s+(?:function\s+)?definition\b', question, re.I):
        raise NotChecked('Fresh-definition starting state is not explicit in the question.')
    name, mode, guarded = function_contract(function_source)
    calls = print_calls(question)
    if not calls or len(calls) > 20: raise NotChecked('Expected 1–20 explicit print calls.')
    default_list = []; outputs = []; steps = []
    for entry in calls:
        call = entry['call']
        if call.func.id != name: raise NotChecked('Question calls a different function.')
        item = primitive(call.args[0]); explicit = len(call.args) == 2
        target = primitive(call.args[1]) if explicit else default_list if mode == 'list' else None
        if target is None and guarded: target = []
        if not isinstance(target, list): raise NotChecked('This call would not reach supported list append semantics.')
        before = copy.deepcopy(target); target.append(item)
        outputs.append(copy.deepcopy(target))
        steps.append({'call': entry['source'], 'explicit_second_argument': explicit,
                      'uses_shared_default_list': target is default_list,
                      'before_append': before, 'printed_list': copy.deepcopy(target)})
    return {'outputs': outputs, 'steps': steps, 'citation_id': citation_id,
            'function_source_exactly_anchored': True, 'execution_method': 'Restricted AST interpretation; no eval or exec.',
            'limits': 'Only this explicit append/return subset under the stated fresh-definition assumption. This does not validate unrelated Python or the surrounding free-text explanation.'}


def trace_for_question(question, context):
    calls = print_calls(question)
    if not calls: raise NotChecked('No explicit print-call task in question.')
    name = calls[0]['call'].func.id
    signature = re.search(r'\b' + re.escape(name) + r'\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*=\s*(\[\s*\]|None)\s*\)', question)
    requested_mode = ('none' if signature.group(3) == 'None' else 'list') if signature else None
    matches = []
    for passage in context:
        pattern = r'^def\s+' + re.escape(name) + r'\([^\n]*\):[^\n]*(?:\n[ \t]+[^\n]+)+'
        for match in re.finditer(pattern, passage['text'], flags=re.M):
            source = match.group(0)
            try:
                _, mode, _ = function_contract(source)
                if requested_mode is not None:
                    fn = ast.parse(source).body[0]
                    if mode != requested_mode or [a.arg for a in fn.args.args] != [signature.group(1), signature.group(2)]: continue
            except NotChecked: continue
            if all(source != prior[1] for prior in matches): matches.append((passage['id'], source))
    if len(matches) != 1: raise NotChecked('Exactly one unambiguous supported function definition is required.')
    return trace(question, context, *matches[0])


def declared_outputs(answer, question):
    expected_calls = print_calls(question); actual_calls = print_calls(answer)
    if len(actual_calls) != len(expected_calls): raise NotChecked('Answer does not declare exactly the requested print calls.')
    outputs = []
    for expected, actual in zip(expected_calls, actual_calls):
        if ast.dump(expected['call']) != ast.dump(actual['call']): raise NotChecked('Answer changes a requested call.')
        suffix = answer[actual['end']:actual['end'] + 250]
        prefix = re.match(r'\s*`?\s*(?:(?:will\s+)?(?:outputs?|prints?)|->|→)\s*`?\s*', suffix, flags=re.I)
        if not prefix: raise NotChecked('Cannot locate an unambiguous declared output after a print call.')
        start = prefix.end()
        literal, _ = balanced(suffix, start, '[', ']')
        value = primitive(ast.parse(literal, mode='eval').body)
        if not isinstance(value, list): raise NotChecked('Declared output is not a supported list.')
        outputs.append(value)
    return outputs


def audit_saved(folder, output):
    summary = json.loads((folder / 'summary.json').read_text()); plan = json.loads((folder / 'plan.json').read_text())
    if summary.get('comparison_version') != 'rerank-generation-comparison-1.0.0': raise NotChecked('Expected the saved 32-attempt retrieval comparison.')
    for name, expected in plan['prepared_files'].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise NotChecked('Frozen comparison input changed.')
    rows = []
    for job in summary['records']:
        record_path = folder / 'jobs' / job['id'] / 'record.json'
        if not record_path.exists(): continue
        record = json.loads(record_path.read_text()); question = record['job']['question']
        result = {'job_id': job['id'], 'case_id': job['case_id'], 'arm': job['arm'], 'order': job['order'],
                  'original_record_sha256': hashlib.sha256(record_path.read_bytes()).hexdigest(),
                  'answer_modified': False, 'semantic_correctness_certified': False}
        try:
            control = trace_for_question(question, record['context'])
            result['derived_trace'] = control
            claimed = declared_outputs(record['answer'], question)
            result.update(status='trace_matches' if claimed == control['outputs'] else 'trace_mismatch', declared_outputs=claimed)
        except (NotChecked, SyntaxError) as exc:
            result.update(status='not_checked', reason=str(exc))
        rows.append(result)
    report = {'version': VERSION, 'generation_calls': 0, 'benchmark_gold_read': False,
              'limits': 'This automatic audit checks only the supported explicit Python print-trace subset. Not-checked means unknown, never pass. Arithmetic helpers require explicit evidence selections and are not automatically applied to these free-text answers. No full factual or contradiction certification.',
              'records': rows}
    (output / 'reasoning_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    from collections import Counter
    print('Audit status counts:', dict(Counter(r['status'] for r in rows)))
    return report


class Tests(unittest.TestCase):
    def context(self): return [{'id': 's', 'text': 'Group A mean was 20.75 hours/week; Group B mean was 8.25 hours/week.'}]
    def selections(self):
        quote = self.context()[0]['text']
        return ({'citation_id': 's', 'quote': quote, 'value': '20.75', 'unit': 'hours/week'},
                {'citation_id': 's', 'quote': quote, 'value': '8.25', 'unit': 'hours/week'})
    def trace_fixture(self, mode='list'):
        source = 'def collect(value, bag=[]):\n    bag.append(value)\n    return bag' if mode == 'list' else 'def collect(value, bag=None):\n    if bag is None:\n        bag = []\n    bag.append(value)\n    return bag'
        question = 'Use a fresh function definition. Execute print(collect(4)), print(collect(9, [])), print(collect(7)).'
        return question, [{'id': 'code', 'text': source}], source
    def test_decimal_difference(self):
        result = calculate(self.context(), 'difference', *self.selections()); self.assertEqual(result['value'], '12.50')
        self.assertFalse(result['semantic_operand_selection_verified'])
    def test_direction_preserved(self):
        a,b = self.selections(); self.assertEqual(calculate(self.context(), 'difference', b,a)['value'], '-12.50')
    def test_ratio_unit(self):
        self.assertEqual(calculate(self.context(), 'ratio', *self.selections())['unit'], 'dimensionless')
    def test_unknown_citation_refused(self):
        a,b=self.selections(); a['citation_id']='missing'
        with self.assertRaises(NotChecked): calculate(self.context(), 'difference', a,b)
    def test_fabricated_quote_refused(self):
        a,b=self.selections(); a['quote']='A different source says 20.75 hours/week.'
        with self.assertRaises(NotChecked): calculate(self.context(), 'difference', a,b)
    def test_fabricated_number_refused(self):
        a,b=self.selections(); a['value']='20.7'
        with self.assertRaises(NotChecked): calculate(self.context(), 'difference', a,b)
    def test_unit_mismatch_refused(self):
        context=[{'id':'s','text':'A: 3 hours. B: 2 days.'}]
        a={'citation_id':'s','quote':context[0]['text'],'value':'3','unit':'hours'}
        b={'citation_id':'s','quote':context[0]['text'],'value':'2','unit':'days'}
        with self.assertRaises(NotChecked): calculate(context, 'difference', a,b)
    def test_rate_unit_cannot_be_shortened_to_its_numerator(self):
        a,b=self.selections();a['unit']='hours'
        with self.assertRaises(NotChecked): calculate(self.context(),'difference',a,b)
    def test_zero_ratio_refused(self):
        context=[{'id':'s','text':'3 hours and 0 hours'}]
        a={'citation_id':'s','quote':context[0]['text'],'value':'3','unit':'hours'};b=dict(a,value='0')
        with self.assertRaises(NotChecked): calculate(context, 'ratio', a,b)
    def test_shared_default_and_explicit_list(self):
        q,c,s=self.trace_fixture();self.assertEqual(trace(q,c,'code',s)['outputs'],[[4],[9],[4,7]])
    def test_none_default_uses_fresh_list(self):
        q,c,s=self.trace_fixture('none');self.assertEqual(trace(q,c,'code',s)['outputs'],[[4],[9],[7]])
    def test_nonempty_explicit_list_does_not_modify_default(self):
        q,c,s=self.trace_fixture();q=q.replace('9, []','9, [2]')
        self.assertEqual(trace(q,c,'code',s)['outputs'],[[4],[2,9],[4,7]])
    def test_trace_snapshots_do_not_mutate_earlier_prints(self):
        q,c,s=self.trace_fixture();result=trace(q,c,'code',s);self.assertEqual(result['steps'][0]['printed_list'],[4])
    def test_function_must_be_exact_source(self):
        q,c,s=self.trace_fixture()
        with self.assertRaises(NotChecked): trace(q,c,'code',s.replace('append','extend'))
    def test_unknown_initial_state_refused(self):
        q,c,s=self.trace_fixture()
        with self.assertRaises(NotChecked): trace(q.replace('fresh function definition','function'),c,'code',s)
    def test_other_function_call_refused(self):
        q,c,s=self.trace_fixture()
        with self.assertRaises(NotChecked): trace(q.replace('collect(4)','other(4)'),c,'code',s)
    def test_arbitrary_code_shape_refused(self):
        with self.assertRaises(NotChecked): function_contract('def collect(x, bag=[]):\n    import os\n    return bag')
    def test_duplicate_parameters_refused(self):
        with self.assertRaises(NotChecked): function_contract('def collect(bag, bag=[]):\n    bag.append(bag)\n    return bag')
    def test_expression_argument_refused(self):
        q,c,s=self.trace_fixture()
        with self.assertRaises(NotChecked): trace(q.replace('collect(4)','collect(2+2)'),c,'code',s)
    def test_automatic_source_discovery(self):
        q,c,_=self.trace_fixture();self.assertEqual(trace_for_question(q,c)['outputs'],[[4],[9],[4,7]])
    def test_conflicting_supported_definitions_refused(self):
        q,c,_=self.trace_fixture();_,other,_=self.trace_fixture('none')
        with self.assertRaises(NotChecked): trace_for_question(q,c+[{**other[0],'id':'other'}])
    def test_explicit_question_signature_selects_requested_version(self):
        q,c,_=self.trace_fixture();_,other,_=self.trace_fixture('none')
        both=c+[{**other[0],'id':'other'}]
        question='Use collect(value, bag=[]) from a fresh function definition. '+q
        self.assertEqual(trace_for_question(question,both)['outputs'],[[4],[9],[4,7]])
        question=question.replace('bag=[]','bag=None')
        self.assertEqual(trace_for_question(question,both)['outputs'],[[4],[9],[7]])
    def test_declared_list_outputs(self):
        q,_,_=self.trace_fixture();a='print(collect(4)) outputs [4], print(collect(9, [])) outputs [9], print(collect(7)) outputs [4, 9, 7].'
        self.assertEqual(declared_outputs(a,q),[[4],[9],[4,9,7]])
    def test_altered_print_call_is_not_guessed(self):
        q,_,_=self.trace_fixture();a='print(collect(4)) outputs [4], print(collect(9)) outputs [4,9], print(collect(7)) outputs [4,9,7].'
        with self.assertRaises(NotChecked): declared_outputs(a,q)
    def test_quoted_parentheses_in_call(self):
        self.assertEqual(len(print_calls('print(collect("a(b)"))')),1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--self-test',action='store_true')
    modes.add_argument('--audit-comparison',nargs='?',const='auto',type=str)
    modes.add_argument('--check',type=Path,help='JSON object with context and an explicit arithmetic or trace action')
    args=parser.parse_args()
    if not (ROOT/'pyproject.toml').exists():parser.error('Save this file in the existing project root.')
    folder=ROOT/'results'/('reasoning_tools_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]);folder.mkdir(parents=True)
    status=1
    try:
        if args.self_test:
            output=io.StringIO();result=unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
            report={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'generation_calls':0,'log':output.getvalue()}
            (folder/'selftest.json').write_text(json.dumps(report,indent=2)+'\n');print(output.getvalue());status=0 if result.wasSuccessful() else 1
        elif args.audit_comparison:
            if args.audit_comparison=='auto':
                plan=json.loads((ROOT/'config/rerank_generation_comparison_v1.json').read_text());path=(ROOT/plan['folder']).resolve()
                if not path.is_relative_to((ROOT/'results').resolve()):raise NotChecked('Unsafe comparison folder.')
            else:path=Path(args.audit_comparison).resolve()
            audit_saved(path,folder);status=0
        else:
            data=json.loads(args.check.read_text());action=data['action']
            if action['type']=='arithmetic':result=calculate(data['context'],action['operation'],action['left'],action['right'])
            elif action['type']=='trace':result=trace(data['question'],data['context'],action['citation_id'],action['function_source'])
            else:raise NotChecked('Unknown tool action.')
            (folder/'tool_result.json').write_text(json.dumps(result,indent=2)+'\n');status=0
    except Exception as exc:
        (folder/'error.json').write_text(json.dumps({'error':f'{type(exc).__name__}: {exc}','generation_calls':0},indent=2)+'\n');print(type(exc).__name__+': '+str(exc))
    finally:
        with zipfile.ZipFile(folder/'reasoning_tools_bundle.zip','x',zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(folder.iterdir()):
                if p.is_file() and p.name!='reasoning_tools_bundle.zip':archive.write(p,p.name)
        print('Saved:',folder/'reasoning_tools_bundle.zip')
    return status


if __name__=='__main__':raise SystemExit(main())
