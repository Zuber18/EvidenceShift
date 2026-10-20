"""Regression contracts with saved real passages and controlled model responses."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from evidence_api import source_first as engine
from evidence_api.local_upload_v2 import Workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT/'evaluation/local_upload_regression.json').read_text())


class Client:
    def __init__(self, answer=None, done='stop'):
        self.answer = answer; self.calls = []; self.done = done

    def chat(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.answer)),
            done_reason=self.done, eval_count=30, prompt_eval_count=100)

    def list(self):
        return SimpleNamespace(model_dump=lambda **kwargs: {'models': [{'model':'qwen3:8b','digest':'controlled'}]})


def response(quote, handle='S1'):
    return {'response_type': 'supported', 'excerpts': [{'handle': handle, 'quote': quote}],
            'unanswered_parts': []}


class Tests(unittest.TestCase):
    def setUp(self):
        self.passage = {'id': 'doc_p1_c0', 'document_id': 'doc', 'page': 1, 'chunk': 0,
                        'source': 'story.txt', 'text': 'Jim sold his watch to buy the combs.'}

    def test_rejects_wrong_gift_invention(self):
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            engine.validate_excerpts(response('Jim bought a gold watch as a gift for Della.'), [self.passage])

    def test_rejects_removed_negation(self):
        self.passage['text'] = 'A receipt does not prove that execution started.'
        with self.assertRaises(ValueError):
            engine.validate_excerpts(response('A receipt proves that execution started.'), [self.passage])

    def test_rejects_swapped_actor(self):
        self.passage['text'] = 'Della bought a gift for Jim.'
        with self.assertRaises(ValueError):
            engine.validate_excerpts(response('Jim bought a gift for Della.'), [self.passage])

    def test_rejects_quote_from_different_handle(self):
        other = {**self.passage, 'id': 'other', 'text': 'Della sold her hair.'}
        with self.assertRaises(ValueError):
            engine.validate_excerpts(response(self.passage['text'], 'S2'), [self.passage, other])

    def test_rejects_unknown_handle(self):
        with self.assertRaises(ValueError):
            engine.validate_excerpts(response(self.passage['text'], 'S99'), [self.passage])

    def test_returns_original_whitespace_and_offsets(self):
        self.passage['text'] = 'Jim sold his\n watch to buy the combs.'
        record = engine.validate_excerpts(response('Jim sold his watch to buy the combs.'), [self.passage])[0]
        self.assertEqual(record['claim_text'], self.passage['text'])
        self.assertEqual(record['claim_text'], self.passage['text'][record['span_start']:record['span_end']])

    def test_rejects_duplicate_excerpts(self):
        answer = response(self.passage['text']); answer['excerpts'] *= 2
        with self.assertRaises(ValueError):
            engine.validate_excerpts(answer, [self.passage])

    def test_insufficient_has_no_excerpts(self):
        answer = response(self.passage['text']); answer['response_type'] = 'insufficient'
        with self.assertRaises(ValueError):
            engine.validate_excerpts(answer, [self.passage])

    def test_complete_answer_requires_nonempty_excerpts(self):
        answer = response(self.passage['text']); answer['excerpts'] = []
        with self.assertRaises(ValueError):
            engine.validate_excerpts(answer, [self.passage])

    def test_6070_bytes_no_longer_arbitrary_failure(self):
        measured = engine.budget([{'role':'user', 'content':'x'*6070}], engine.SCHEMA)
        self.assertGreaterEqual(measured['num_ctx'], 16384)
        self.assertLessEqual(measured['input_bytes_with_schema'] + engine.OUTPUT_TOKENS + engine.TEMPLATE_MARGIN,
                             measured['num_ctx'])

    def test_oversize_fails_without_trimming(self):
        with self.assertRaisesRegex(ValueError, 'no evidence was trimmed'):
            engine.budget([{'role':'user', 'content':'x'*40000}], engine.SCHEMA)

    def test_unicode_counted_as_bytes(self):
        a=engine.budget([{'content':'a'*100}], engine.SCHEMA)
        b=engine.budget([{'content':'界'*100}], engine.SCHEMA)
        self.assertGreater(b['input_bytes_with_schema'],a['input_bytes_with_schema'])

    def run_engine(self, client, context=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        return engine.run('What did Jim buy?', [self.passage] if context is None else context,
                          client,'qwen3:8b',{'temperature':0,'seed':42},Path(temp.name))[0]

    def test_empty_context_zero_calls(self):
        client=Client(); result=self.run_engine(client,[])
        self.assertEqual(client.calls,[])
        self.assertEqual(result['status'],'empty_context_control')

    def test_invalid_semantic_rewrite_saved_as_failure(self):
        result=self.run_engine(Client(response('Jim bought a gold watch.')))
        self.assertEqual(result['status'],'mechanical_failure')
        self.assertIsNone(result['candidate_answer'])
        self.assertIn('gold watch',result['stages'][0]['raw_output'])

    def test_valid_source_copy_is_not_certified(self):
        result=self.run_engine(Client(response(self.passage['text'])))
        self.assertEqual(result['status'],'candidate_recorded')
        self.assertIsNone(result['delivery_answer'])
        self.assertFalse(result['mechanical_checks']['semantic_relevance_verified'])

    def test_truncated_response_rejected(self):
        result=self.run_engine(Client(response(self.passage['text']),done='length'))
        self.assertEqual(result['status'],'mechanical_failure')

    def workspace(self, rows):
        workspace=Workspace.__new__(Workspace)
        workspace.closed=False; workspace.all_passages=rows
        workspace.documents=[{'document_id':id} for id in dict.fromkeys(p['document_id'] for p in rows)]
        workspace.manifest={'retrieval_policy':'test-v2'}
        workspace.store=SimpleNamespace(search=lambda question,count,ids:copy.deepcopy(rows[:count]))
        return workspace

    def test_saved_gift_failure_gets_combs_in_context(self):
        case=next(c for c in FIXTURE['cases'] if c['id'].endswith('1f939d31'))
        by_id={p['id']:p for p in FIXTURE['passages']}
        rows=[by_id[id] for id in case['original_context_ids']]
        self.assertFalse(any('combs' in p['text'].lower() for p in rows))
        rows += [p for p in FIXTURE['passages'] if p['id'] not in case['original_context_ids']]
        workspace=self.workspace(rows)
        hits=workspace.search(case['question'])
        self.assertTrue(any('combs' in p['text'].lower() for p in hits))
        self.assertEqual(len(hits),len(rows))
        self.assertTrue(workspace.last_retrieval['complete_corpus_coverage'])

    def test_large_corpus_adds_neighbor_without_crossing_documents(self):
        rows=[{**self.passage,'id':f'a{i}','document_id':'a','chunk':i,'text':'x'*500} for i in range(50)]
        rows += [{**self.passage,'id':'b0','document_id':'b'}]
        workspace=self.workspace(rows)
        workspace.store=SimpleNamespace(search=lambda *args: [rows[49]])
        hits=workspace.search('question')
        self.assertEqual({p['id'] for p in hits},{'a49','a48'})
        self.assertFalse(workspace.last_retrieval['complete_corpus_coverage'])

    def test_missing_full_corpus_hit_rejected(self):
        workspace=self.workspace([self.passage])
        workspace.store=SimpleNamespace(search=lambda *args: [])
        with self.assertRaisesRegex(ValueError,'omitted passages'):
            workspace.search('question')

    def actual_workspace(self):
        # Reuse the controlled store from the preserved service contract suite.
        from test_local_upload import Store
        class ListingStore(Store):
            def chunks(self, document_id, limit=50, offset=0):
                return copy.deepcopy([p for p in self.rows if p['document_id']==document_id][offset:offset+limit])
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root=Path(temp.name);(root/'evaluation').mkdir()
        (root/'evaluation/fresh_baseline_cases.json').write_bytes((ROOT/'evaluation/fresh_baseline_cases.json').read_bytes())
        workspace=Workspace(root,[('a.txt',b'Jim sold his watch to buy the combs.'),
                                  ('b.txt',b'Della sold her hair.')],store_factory=ListingStore)
        self.addCleanup(workspace.close)
        return workspace

    def test_service_saves_exact_excerpt_and_export(self):
        import zipfile
        workspace=self.actual_workspace()
        run=workspace.ask('What did Jim sell?',client=Client(response('Jim sold his watch to buy the combs.')))
        self.assertEqual(run['status'],'candidate_recorded')
        self.assertTrue(run['retrieval_plan']['complete_corpus_coverage'])
        with zipfile.ZipFile(workspace.export()) as archive:
            self.assertIn('runs/'+run['run_id']+'/run.json',archive.namelist())
            session=json.loads(archive.read('session.json'))
            self.assertEqual(session['generation_version'],engine.VERSION)
            self.assertIn('source_first.py',session['source_module_sha256'])

    def test_service_matched_orders_are_exact_reversals(self):
        workspace=self.actual_workspace()
        a=workspace.ask('What did Jim sell?',client=Client(response('Jim sold his watch to buy the combs.')))
        b=workspace.ask('What did Jim sell?','reversed',client=Client(response('Della sold her hair.')))
        self.assertEqual(a['used_context'],list(reversed(b['used_context'])))

    def test_service_empty_context_no_calls_and_clear_preserves_results(self):
        workspace=self.actual_workspace(); client=Client()
        run=workspace.ask('Who is Della?','no_context',client=client)
        self.assertEqual(run['status'],'empty_context_control')
        self.assertEqual(client.calls,[])
        workspace.close()
        self.assertTrue((workspace.folder/'runs'/run['run_id']/'run.json').is_file())


if __name__ == '__main__':
    unittest.main()
