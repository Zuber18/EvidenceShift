"""Context-diagnostic control-flow tests; semantic effects are simulated."""
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
from evidence_api import context_audit_v131 as audit


class Client:
    def __init__(self, effect='already_addressed', objection=True, corrupt=None):
        self.effect, self.objection, self.corrupt = effect, objection, corrupt
        self.calls = []
    def list(self):
        return SimpleNamespace(model_dump=lambda **kwargs: {'models': [{'model': 'qwen3:8b'}]})
    def chat(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        prompt = kwargs['messages'][0]['content']
        payload = json.loads(kwargs['messages'][1]['content'])
        if prompt == audit.CRITIC_PROMPT:
            value = {'objections': ([{'kind': 'material_condition',
                     'source_handle': payload['paragraphs'][0]['handle'],
                     'reason': 'A condition might be missing.'}] if self.objection else [])}
            if self.corrupt == 'source':
                value['objections'][0]['source_handle'] = 'P999'
            elif self.corrupt == 'quote':
                value['objections'][0]['quote'] = 'A model invented quote.'
        elif prompt == audit.CONFIRM_PROMPT:
            value = {'effect': self.effect, 'reason': 'A simulated confirmation decision.'}
        else:
            raise AssertionError('Unexpected model call')
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value), thinking=None),
                               done_reason='stop', eval_count=20)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chunks = [{'id': 'policy', 'text': 'Domestic approval is optional.\n\nInternational approval is required.'}]
        self.candidate = 'Domestic approval is optional. [policy]'
    def run_case(self, client=None, chunks=None):
        return audit.audit('Is domestic approval required?', self.candidate,
                           self.chunks if chunks is None else chunks, client or Client(), 'qwen3:8b',
                           {'num_predict': 4096, 'num_ctx': 8192}, self.root,
                           {'expected_context_result': 'must not be included in model messages'})
    def test_empty_objections_can_clear(self):
        client = Client(objection=False)
        result, _ = self.run_case(client)
        self.assertEqual(result['status'], 'context_clear')
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(result['context_review_complete'])
        self.assertIsNone(result['delivery_answer'])
    def test_already_addressed_objection_does_not_veto(self):
        result, _ = self.run_case(Client(effect='already_addressed'))
        self.assertEqual(result['status'], 'context_clear')
        self.assertEqual(len(result['objection_reviews']), 1)
    def test_irrelevant_detail_does_not_veto(self):
        result, _ = self.run_case(Client(effect='outside_scope'))
        self.assertEqual(result['status'], 'context_clear')
    def test_unestablished_objection_does_not_veto(self):
        result, _ = self.run_case(Client(effect='not_established'))
        self.assertEqual(result['status'], 'context_clear')
    def test_confirmed_opposing_evidence_is_flagged(self):
        result, _ = self.run_case(Client(effect='invalidates'))
        self.assertEqual(result['status'], 'context_objection_confirmed')
        self.assertIsNone(result['delivery_answer'])
    def test_uncertainty_is_not_reported_clear(self):
        result, _ = self.run_case(Client(effect='uncertain'))
        self.assertEqual(result['status'], 'context_uncertain')
    def test_unknown_source_handle_is_rejected(self):
        result, _ = self.run_case(Client(corrupt='source'))
        self.assertEqual(result['status'], 'context_review_failed')
    def test_model_cannot_supply_its_own_quote(self):
        result, _ = self.run_case(Client(corrupt='quote'))
        self.assertEqual(result['status'], 'context_review_failed')
    def test_witness_is_code_copied_and_full_source_is_present(self):
        client = Client()
        result, _ = self.run_case(client)
        witness = result['objection_reviews'][0]['witness']['text']
        self.assertEqual(witness, 'Domestic approval is optional.')
        confirmation = next(call for call in client.calls if call['messages'][0]['content'] == audit.CONFIRM_PROMPT)
        payload = json.loads(confirmation['messages'][1]['content'])
        self.assertEqual(payload['passages'][0]['text'], self.chunks[0]['text'])
        self.assertNotIn('expected_context_result', json.dumps(client.calls))
    def test_original_candidate_is_saved_without_citation_rewriting(self):
        result, bundle = self.run_case()
        self.assertEqual(result['candidate_answer'], self.candidate)
        self.assertIn('[D1]', result['audit_candidate'])
        with zipfile.ZipFile(bundle) as archive:
            saved = json.loads(archive.read('source_result.json'))
            self.assertEqual(saved['candidate_answer'], self.candidate)
            self.assertEqual(json.loads(archive.read('result.json')), result)
    def test_every_paragraph_batch_is_reviewed(self):
        chunks = [{'id': str(i), 'text': f'Section {i}. ' + 'Document information. ' * 40} for i in range(7)]
        client = Client(objection=False)
        result, _ = self.run_case(client, chunks)
        self.assertEqual(result['status'], 'context_clear')
        expected = [p['handle'] for p in result['paragraph_catalog']]
        actual = [p for r in result['critic_reviews'] for p in r['paragraph_handles']]
        self.assertEqual(actual, expected)
        self.assertGreater(len(result['critic_reviews']), 1)
        self.assertTrue(all(s['input_bytes_with_schema'] <= 6000 for s in result['stages']))
    def test_failed_transport_saves_error_without_retry(self):
        class Broken(Client):
            def chat(self, **kwargs):
                self.calls.append(kwargs)
                raise TimeoutError('simulated failure')
        client = Broken()
        result, bundle = self.run_case(client)
        self.assertEqual(result['status'], 'context_review_failed')
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(bundle.exists())
    def test_saved_v13_runner_does_not_mutate_source(self):
        path = ROOT / 'evaluation/recheck_context_v131.py'
        spec = importlib.util.spec_from_file_location('context_runner', path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        source = self.root / 'benchmark_v13_20261016T000000Z'
        source.mkdir()
        setup = {'pipeline_version': '1.3.0', 'preserved_plan': {'options': {'num_predict': 4096}}}
        record = {'case_id': 'accepted_202', 'variant': 'retrieved', 'result': {
            'question': 'Is approval required?', 'candidate_answer': self.candidate,
            'structured_answer': {'claims': [{'text': 'Domestic approval is optional.'}]},
            'original_record': {'context': self.chunks}, 'run_id': 'old_run', 'status': 'blocked'}}
        (source / 'setup.json').write_text(json.dumps(setup))
        original = json.dumps({'complete': True, 'records': [record]})
        (source / 'results.json').write_text(original)
        rows, bundle = runner.recheck(source, self.root / 'out', Client(objection=False))
        self.assertEqual((source / 'results.json').read_text(), original)
        self.assertEqual(len(rows), 5)  # One saved candidate plus four negative controls.
        self.assertTrue(bundle.exists())
        self.assertEqual(runner.latest_benchmark(self.root), source)


if __name__ == '__main__':
    unittest.main()
