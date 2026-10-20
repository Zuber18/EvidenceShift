"""Regression checks for failure handling and provenance; model judgments are simulated."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from evidence_api import grounded_v13 as v


def passage(identifier, text):
    return {'id': identifier, 'source': identifier + '.txt', 'page': 0, 'text': text}


class Client:
    def __init__(self, selection=None, answer=None, hook=None):
        self.selection = selection
        self.answer = answer or {'response_type': 'supported', 'claims': [
            {'text': 'Domestic approval is optional.', 'evidence': ['E1']},
        ]}
        self.hook = hook
        self.calls = []

    def list(self):
        return SimpleNamespace(model_dump=lambda **kwargs: {'models': [{'model': 'qwen3:8b'}]})

    def chat(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        prompt = kwargs['messages'][0]['content']
        payload = json.loads(kwargs['messages'][1]['content'])
        if prompt == v.base.SELECT_PROMPT:
            value = self.selection or {'answerability': 'supported', 'evidence_handles': ['S1']}
        elif prompt == v.GENERATE_PROMPT:
            value = self.answer
        elif prompt == v.SUPPORT_PROMPT:
            value = {'verdict': 'supported', 'reason': 'The complete claim is supported.'}
        elif prompt == v.CONTEXT_PROMPT:
            value = {'issue': 'none', 'reason': 'No material evidence omission in this batch.'}
        elif prompt == v.COVERAGE_PROMPT:
            value = {'coverage': 'complete', 'reason': 'All question parts addressed.'}
        elif prompt == v.ABSTENTION_PROMPT:
            value = {'answerability': 'not_answerable', 'reason': 'No requested information is supplied.'}
        else:
            raise AssertionError('Unexpected stage')
        if self.hook:
            value = self.hook(prompt, payload, value)
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value), thinking=None),
                               done_reason='stop', eval_count=20)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chunks = [passage('policy', 'Domestic approval is optional.')]

    def run_case(self, client=None, chunks=None, question='Is domestic approval mandatory?'):
        chunks = self.chunks if chunks is None else chunks
        source = self.root / ('source_' + str(len(list(self.root.iterdir()))))
        source.mkdir()
        setup = {'run_id': source.name, 'model': 'qwen3:8b', 'think': False,
                 'options': {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 4096},
                 'request': {'question': question}}
        result = {'run_id': source.name, 'records': [{'prompt_name': 'test', 'variant': 'retrieved',
                  'context': chunks, 'user_prompt': 'Source test input'}]}
        (source / 'setup.json').write_text(json.dumps(setup))
        (source / 'result.json').write_text(json.dumps(result))
        return v.run(source, self.root / 'runs', client or Client(), prompt='test', variant='retrieved')

    def test_supported_answer_and_checkpoint(self):
        client = Client()
        result, bundle = self.run_case(client)
        self.assertEqual(result['status'], 'candidate_ready')
        self.assertTrue(result['context_review_complete'])
        with zipfile.ZipFile(bundle) as archive:
            self.assertEqual(json.loads(archive.read('result.json')), result)
            self.assertEqual(json.loads(archive.read('source_result.json'))['records'][0], result['original_record'])
            events = [json.loads(row) for row in archive.read('stages.jsonl').decode().splitlines()]
            self.assertEqual(sum(e['event'] == 'completed' for e in events), len(client.calls))

    def test_empty_context_uses_no_model_calls(self):
        client = Client()
        result, _ = self.run_case(client, chunks=[])
        self.assertEqual(result['delivery_answer'], v.base.ABSTENTION)
        self.assertEqual(client.calls, [])

    def test_uncited_opposing_source_is_checked_and_blocks(self):
        chunks = [passage('handbook', 'The deadline is 15 June 2027.'),
                  passage('memo', 'The deadline is 30 June 2027. Neither document has precedence.')]
        answer = {'response_type': 'supported', 'claims': [
            {'text': 'The deadline is 15 June 2027.', 'evidence': ['E1']},
        ]}
        seen = []
        def hook(prompt, payload, value):
            if prompt == v.CONTEXT_PROMPT:
                seen.extend(p['id'] for p in payload['passages'])
                if any(p['id'] == 'memo' for p in payload['passages']):
                    return {'issue': 'omitted_conflict', 'reason': 'Opposing memo deadline is omitted.'}
            return value
        result, _ = self.run_case(Client(answer=answer, hook=hook), chunks, 'What is the deadline?')
        self.assertIn('memo', seen)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['delivery_answer'])

    def test_conflict_label_is_rendered_explicitly(self):
        chunks = [passage('handbook', 'The deadline is 15 June 2027.'),
                  passage('memo', 'The deadline is 30 June 2027.')]
        answer = {'response_type': 'conflict', 'claims': [
            {'text': 'The handbook states 15 June 2027.', 'evidence': ['E1']},
            {'text': 'The memo states 30 June 2027.', 'evidence': ['E2']},
        ]}
        result, _ = self.run_case(Client(selection={'answerability': 'conflict', 'evidence_handles': ['S1', 'S2']},
                                         answer=answer), chunks, 'What is the deadline?')
        self.assertEqual(result['status'], 'candidate_ready')
        self.assertTrue(result['delivery_answer'].startswith(v.CONFLICT_PREFIX))
        self.assertIn('[handbook]', result['delivery_answer'])
        self.assertIn('[memo]', result['delivery_answer'])

    def test_claim_ids_are_owned_by_code(self):
        answer = {'response_type': 'supported', 'claims': [
            {'text': 'Domestic approval is optional.', 'evidence': ['E1']},
            {'text': 'Domestic approval is not mandatory.', 'evidence': ['E1']},
        ]}
        client = Client(answer=answer)
        result, _ = self.run_case(client)
        self.assertEqual([r['claim_index'] for r in result['claim_reviews']], [0, 1])
        checks = [c for c in client.calls if c['messages'][0]['content'] == v.SUPPORT_PROMPT]
        self.assertEqual(len(checks), 2)
        self.assertEqual([json.loads(c['messages'][1]['content'])['claim'] for c in checks],
                         [claim['text'] for claim in answer['claims']])
        for call in checks:
            self.assertNotIn('claim_index', call['format']['properties'])

    def test_model_cannot_add_or_renumber_claims(self):
        def hook(prompt, payload, value):
            if prompt == v.SUPPORT_PROMPT:
                return {**value, 'claim_index': 1}
            return value
        result, _ = self.run_case(Client(hook=hook))
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('unexpected or missing fields', result['error'])

    def test_unknown_selection_handle_in_answer_is_rejected(self):
        answer = {'response_type': 'supported', 'claims': [
            {'text': 'Domestic approval is optional.', 'evidence': ['S1']},
        ]}
        client = Client(answer=answer)
        result, _ = self.run_case(client)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['candidate_answer'])
        generation = next(c for c in client.calls if c['messages'][0]['content'] == v.GENERATE_PROMPT)
        items = generation['format']['properties']['claims']['items']['properties']['evidence']['items']
        self.assertEqual(items['enum'], ['E1'])

    def test_justified_abstention_has_separate_contract(self):
        selection = {'answerability': 'insufficient', 'evidence_handles': []}
        client = Client(selection=selection)
        result, _ = self.run_case(client, question='What is the production password?')
        self.assertEqual(result['status'], 'candidate_ready')
        self.assertEqual(result['delivery_answer'], v.base.ABSTENTION)
        self.assertEqual(result['claim_reviews'], [])
        self.assertTrue(result['context_review_complete'])
        prompts = [c['messages'][0]['content'] for c in client.calls]
        self.assertNotIn(v.GENERATE_PROMPT, prompts)
        self.assertNotIn(v.COVERAGE_PROMPT, prompts)
        self.assertIn(v.ABSTENTION_PROMPT, prompts)

    def test_answerable_evidence_blocks_abstention(self):
        def hook(prompt, payload, value):
            if prompt == v.ABSTENTION_PROMPT:
                return {'answerability': 'answerable', 'reason': 'Domestic approval is explicitly addressed.'}
            return value
        result, _ = self.run_case(Client(selection={'answerability': 'insufficient', 'evidence_handles': []}, hook=hook))
        self.assertEqual(result['status'], 'blocked')

    def test_uncertain_abstention_is_not_approved(self):
        def hook(prompt, payload, value):
            if prompt == v.ABSTENTION_PROMPT:
                return {'answerability': 'uncertain', 'reason': 'The evidence is ambiguous.'}
            return value
        result, _ = self.run_case(Client(selection={'answerability': 'insufficient', 'evidence_handles': []}, hook=hook))
        self.assertEqual(result['status'], 'blocked')

    def test_hallucinated_time_is_withheld_when_support_check_rejects(self):
        answer = {'response_type': 'supported', 'claims': [
            {'text': 'The deadline is 15 June at 2:00 PM.', 'evidence': ['E1']},
        ]}
        def hook(prompt, payload, value):
            if prompt == v.SUPPORT_PROMPT:
                return {'verdict': 'insufficient', 'reason': 'The source provides no time.'}
            return value
        result, _ = self.run_case(Client(answer=answer, hook=hook),
                                  [passage('handbook', 'The deadline is 15 June 2027.')], 'What is the deadline?')
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['context_review_complete'])

    def test_likely_does_not_automatically_pass_as_definite(self):
        def hook(prompt, payload, value):
            if prompt == v.SUPPORT_PROMPT:
                return {'verdict': 'contradicted', 'reason': 'Likely is not definite.'}
            return value
        client = Client(answer={'response_type': 'supported', 'claims': [
            {'text': 'The condition is definitely permanent.', 'evidence': ['E1']},
        ]}, hook=hook)
        result, _ = self.run_case(client, [passage('resource', 'The condition is likely permanent.')])
        self.assertEqual(result['status'], 'blocked')

    def test_omitted_qualification_blocks(self):
        def hook(prompt, payload, value):
            if prompt == v.CONTEXT_PROMPT:
                return {'issue': 'omitted_condition', 'reason': 'International approval requirement omitted.'}
            return value
        result, _ = self.run_case(Client(hook=hook))
        self.assertEqual(result['status'], 'blocked')
        self.assertTrue(result['context_review_complete'])

    def test_question_coverage_is_separate(self):
        def hook(prompt, payload, value):
            if prompt == v.COVERAGE_PROMPT:
                return {'coverage': 'incomplete', 'reason': 'Second question part is not addressed.'}
            return value
        result, _ = self.run_case(Client(hook=hook))
        self.assertEqual(result['status'], 'blocked')

    def test_full_source_passage_not_just_selected_quote(self):
        chunks = [passage('policy', 'Domestic approval is optional.\n\nInternational approval is required.')]
        client = Client()
        self.run_case(client, chunks)
        call = next(c for c in client.calls if c['messages'][0]['content'] == v.SUPPORT_PROMPT)
        self.assertEqual(json.loads(call['messages'][1]['content'])['passages'][0]['text'], chunks[0]['text'])

    def test_verifier_output_budget_and_logged_inputs(self):
        client = Client()
        result, _ = self.run_case(client)
        for entry in result['stages']:
            self.assertLessEqual(entry['input_bytes_with_schema'], 6000)
            if entry['stage'] not in ('select', 'generate'):
                self.assertEqual(entry['options']['num_predict'], 512)
            else:
                self.assertEqual(entry['options']['num_predict'], 4096)

    def test_all_original_batches_are_checked(self):
        chunks = [passage(str(i), f'Paragraph {i}. ' + 'Detailed source text. ' * 45) for i in range(4)]
        answer = {'response_type': 'supported', 'claims': [
            {'text': f'Statement {i}. ' + 'A detailed candidate statement. ' * 12, 'evidence': ['E1']}
            for i in range(3)
        ]}
        client = Client(answer=answer)
        result, _ = self.run_case(client, chunks)
        self.assertEqual(result['status'], 'candidate_ready')
        ids = [p for review in result['context_reviews'] for p in review['passage_ids']]
        self.assertEqual(ids, [p['id'] for p in chunks])
        self.assertGreater(len(result['context_reviews']), 1)

    def test_single_oversized_passage_is_explicitly_uncheckable(self):
        with self.assertRaisesRegex(ValueError, 'Whole source passage'):
            v.evidence_batches([passage('large', 'x' * 7000)], {'claim': 'A claim.'},
                               v.SUPPORT_PROMPT, v.SUPPORT_SCHEMA)

    def test_duplicate_original_passage_ids_block_before_generation(self):
        client = Client()
        result, _ = self.run_case(client, self.chunks * 2)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(client.calls, [])

    def test_returned_index_for_abstention_is_rejected(self):
        def hook(prompt, payload, value):
            if prompt == v.ABSTENTION_PROMPT:
                return {**value, 'claims': [{'claim_index': 1}]}
            return value
        result, _ = self.run_case(Client(selection={'answerability': 'insufficient', 'evidence_handles': []}, hook=hook))
        self.assertEqual(result['status'], 'blocked')

    def test_transport_failure_saves_raw_run_without_retry(self):
        class Broken(Client):
            def chat(self, **kwargs):
                self.calls.append(kwargs)
                raise TimeoutError('simulated transport failure')
        client = Broken()
        result, bundle = self.run_case(client)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(len(client.calls), 1)
        with zipfile.ZipFile(bundle) as archive:
            self.assertIn('simulated transport failure', archive.read('result.json').decode())


class SavedBudgetRegressionTests(unittest.TestCase):
    def test_previously_over_budget_authentication_inputs_fit_without_dropping_sources(self):
        fixtures = json.loads((ROOT / 'tests/fixtures/v13_authentication_inputs.json').read_text())
        for result in fixtures:
            with self.subTest(variant=result['source_variant']):
                chunks = result['original_record']['context']
                evidence = result['validated_evidence']
                answer = result['structured_answer']
                candidate = v.render_answer(answer, result['selection'], evidence)
                fixed = {'question': result['question'], 'candidate': candidate,
                         'response_type': answer['response_type']}
                batches = v.evidence_batches(chunks, fixed, v.CONTEXT_PROMPT, v.CONTEXT_SCHEMA)
                self.assertEqual([p['id'] for batch in batches for p in batch], [p['id'] for p in chunks])
                for batch in batches:
                    self.assertLessEqual(v.input_size(v.CONTEXT_PROMPT, {**fixed, 'passages': batch},
                                                     v.CONTEXT_SCHEMA), 6000)
                for claim in answer['claims']:
                    cited = {p for e in evidence if e['handle'] in claim['evidence'] for p in e['passage_ids']}
                    passages = [p for p in chunks if p['id'] in cited]
                    fixed = {'question': result['question'], 'claim': claim['text']}
                    batches = v.evidence_batches(passages, fixed, v.SUPPORT_PROMPT, v.SUPPORT_SCHEMA)
                    self.assertEqual([p['id'] for batch in batches for p in batch], [p['id'] for p in passages])
                    for batch in batches:
                        self.assertLessEqual(v.input_size(v.SUPPORT_PROMPT, {**fixed, 'passages': batch},
                                                         v.SUPPORT_SCHEMA), 6000)


class BenchmarkTests(unittest.TestCase):
    def test_runner_preserves_plan_and_saves_bundle(self):
        runner_path = ROOT / 'evaluation/run_benchmark_v13.py'
        spec = importlib.util.spec_from_file_location('v13_runner', runner_path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / 'cases.json'
            plan = {'pipeline_version': '1.2.1', 'options': {'num_predict': 4096, 'num_ctx': 8192},
                    'think': False, 'cases': [{'id': 'test', 'question': 'Is approval mandatory?',
                    'context': [passage('policy', 'Domestic approval is optional.')],
                    'review_criteria': ['A label that must not enter model messages.']}]}
            raw = json.dumps(plan)
            plan_path.write_text(raw)
            client = Client()
            rows, bundle = runner.run_benchmark(['qwen3:8b'], root / 'results', client, plan_path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(plan_path.read_text(), raw)
            self.assertEqual(rows[1]['calls'], 0)
            for call in client.calls:
                self.assertNotIn('A label that must not enter', json.dumps(call['messages']))
            with zipfile.ZipFile(bundle) as archive:
                result = json.loads(archive.read('results.json'))
                self.assertTrue(result['complete'])
                self.assertEqual(result['pipeline_version'], '1.3.0')
                self.assertEqual(result['rows'], rows)


if __name__ == '__main__':
    unittest.main()
