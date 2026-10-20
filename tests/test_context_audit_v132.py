"""Contract and provenance tests using controlled model responses, not semantic scores."""
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
from evidence_api import context_audit_v132 as audit


class Client:
    def __init__(self, verdict='objection_not_demonstrated', objection=True, kind='missing_qualification', handles=None, corrupt=None):
        self.verdict, self.objection, self.kind = verdict, objection, kind
        self.handles, self.corrupt, self.calls = handles, corrupt, []
    def list(self):
        return SimpleNamespace(model_dump=lambda **kwargs: {'models': [{'model': 'qwen3:8b'}]})
    def chat(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        payload = json.loads(kwargs['messages'][1]['content'])
        if kwargs['messages'][0]['content'] == audit.CRITIC_PROMPT:
            ob = {'claim_handle': 'C1', 'source_handles': self.handles or [payload['paragraphs'][0]['handle']],
                  'kind': self.kind, 'reason': 'Controlled test objection.'}
            if self.corrupt == 'claim': ob['claim_handle'] = 'C999'
            if self.corrupt == 'source': ob['source_handles'] = ['P999']
            if self.corrupt == 'quote': ob['claim_text'] = 'Invented positive claim.'
            value = {'objections': [ob] if self.objection else []}
        else:
            self_outer = kwargs['messages'][0]['content']
            assert self_outer == audit.CONFIRM_PROMPT
            value = {'verdict': self.verdict, 'reason': 'Controlled test verdict.'}
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value), thinking=None), done_reason='stop', eval_count=20)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chunks = [{'id': 'policy', 'text': 'Domestic approval is optional.'}]
        self.candidate = 'Domestic approval is not required. [policy]'
    def run_case(self, client=None, chunks=None, candidate=None):
        return audit.audit('Is approval mandatory?', self.candidate if candidate is None else candidate,
                           self.chunks if chunks is None else chunks, client or Client(), 'qwen3:8b',
                           {'num_ctx': 8192, 'num_predict': 4096}, self.root,
                           {'expected_context_result': 'PRIVATE_EXPECTATION'})
    def test_no_error_is_advisory_and_never_delivered(self):
        r,_ = self.run_case(Client(objection=False));self.assertEqual(r['status'],'advisory_no_error_reported')
        self.assertIsNone(r['delivery_answer']);self.assertTrue(r['advisory_only']);self.assertEqual(r['factual_correctness'],'not_automatically_certified')
    def test_exact_target_preserves_negation_and_original_citation(self):
        c=Client();r,_=self.run_case(c)
        self.assertEqual(r['objection_reviews'][0]['target']['text'],self.candidate)
        message=json.loads(c.calls[1]['messages'][1]['content']);self.assertEqual(message['target']['text'],'Domestic approval is not required. [D1]')
        self.assertNotIn('PRIVATE_EXPECTATION',json.dumps(c.calls))
    def test_lines_are_not_model_rewritten(self):
        text=' Conflict remains.\n\nA is possible, not certain. [a]'
        self.assertEqual(audit.candidate_units(text),[{'handle':'C1','text':' Conflict remains.'},{'handle':'C2','text':'A is possible, not certain. [a]'}])
    def test_unknown_claim_rejected(self):
        r,_=self.run_case(Client(corrupt='claim'));self.assertEqual(r['status'],'audit_failed')
    def test_unknown_source_rejected(self):
        r,_=self.run_case(Client(corrupt='source'));self.assertEqual(r['status'],'audit_failed')
    def test_model_replacement_target_rejected(self):
        r,_=self.run_case(Client(corrupt='quote'));self.assertEqual(r['status'],'audit_failed')
    def test_legacy_ambiguous_verdict_rejected(self):
        r,_=self.run_case(Client(verdict='invalidates'));self.assertEqual(r['status'],'audit_failed')
    def test_explicit_candidate_error_recorded_advisory(self):
        r,_=self.run_case(Client(verdict='candidate_has_material_error'));self.assertEqual(r['status'],'advisory_error_reported');self.assertIsNone(r['delivery_answer'])
    def test_objection_not_demonstrated_does_not_report_error(self):
        r,_=self.run_case();self.assertEqual(r['status'],'advisory_no_error_reported')
    def test_uncertain_confirmation_keeps_uncertainty(self):
        r,_=self.run_case(Client(verdict='insufficient_evidence'));self.assertEqual(r['status'],'advisory_inconclusive')
    def test_conflict_with_one_witness_cannot_be_confirmed(self):
        c=Client(kind='cross_source_conflict');r,_=self.run_case(c)
        self.assertEqual(r['status'],'advisory_inconclusive');self.assertEqual(len(c.calls),1)
        self.assertEqual(r['objection_reviews'][0]['confirmation']['origin'],'code_preflight')
    def test_two_paragraphs_of_same_passage_do_not_establish_cross_source_set(self):
        c=Client(kind='cross_source_conflict',handles=['P1','P2'])
        r,_=self.run_case(c,[{'id':'a','text':'First paragraph.\n\nSecond paragraph.'}]);self.assertEqual(r['status'],'advisory_inconclusive')
    def test_both_opposing_parent_passages_are_present_in_one_confirmation(self):
        chunks=[{'id':'a','text':'Deadline 4 May.\n\nNo precedence.'},{'id':'b','text':'Deadline 9 May.\n\nNo precedence.'}]
        aliases,catalog=audit.previous.make_catalog(chunks)
        handles=[p['handle'] for p in catalog if p['text'].startswith('Deadline')]
        c=Client(kind='cross_source_conflict',handles=handles,verdict='candidate_has_material_error')
        r,_=self.run_case(c,chunks)
        self.assertEqual(r['status'],'advisory_error_reported')
        payload=json.loads(c.calls[1]['messages'][1]['content']);self.assertEqual([x['text'] for x in payload['passages']],[x['text'] for x in chunks])
        self.assertEqual(r['objection_reviews'][0]['required_passage_ids'],['a','b'])
    def test_repeated_witness_is_rejected(self):
        r,_=self.run_case(Client(handles=['P1','P1']));self.assertEqual(r['status'],'audit_failed')
    def test_oversize_parent_evidence_set_remains_uncertain_without_truncation(self):
        chunks=[{'id':'policy','text':'A'*2500+'\n\n'+'B'*2500}];c=Client();r,_=self.run_case(c,chunks)
        self.assertEqual(r['status'],'advisory_inconclusive')
        self.assertTrue(all(x['messages'][0]['content']==audit.CRITIC_PROMPT for x in c.calls))
        self.assertEqual(r['original_context'],chunks)
    def test_all_batches_reviewed_and_cross_batch_limit_visible(self):
        chunks=[{'id':str(i),'text':str(i)+' '+'information '*80} for i in range(8)]
        r,_=self.run_case(Client(objection=False),chunks)
        self.assertTrue(r['context_review_complete']);self.assertEqual(r['cross_batch_conflict_coverage'],'not_established')
        self.assertEqual([h for b in r['critic_reviews'] for h in b['paragraph_handles']],[p['handle'] for p in r['paragraph_catalog']])
    def test_transport_failure_saved_once(self):
        class Broken(Client):
            def chat(self,**kwargs): self.calls.append(kwargs);raise TimeoutError('Controlled failure')
        c=Broken();r,bundle=self.run_case(c);self.assertEqual(r['status'],'audit_failed');self.assertEqual(len(c.calls),1);self.assertTrue(bundle.exists())
    def test_bundle_preserves_source_and_result(self):
        r,bundle=self.run_case()
        with zipfile.ZipFile(bundle) as z:
            self.assertEqual(json.loads(z.read('source_result.json'))['candidate_answer'],self.candidate)
            self.assertEqual(json.loads(z.read('result.json')),r)
    def test_runner_saves_report_and_all_regression_controls(self):
        spec=importlib.util.spec_from_file_location('runner_v132',ROOT/'evaluation/recheck_context_v132.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        source=self.root/'benchmark_v13_20261016T000000Z';source.mkdir()
        (source/'setup.json').write_text(json.dumps({'pipeline_version':'1.3.0','preserved_plan':{'options':{'num_ctx':8192}}}))
        value={'complete':True,'records':[{'case_id':'accepted_202','variant':'retrieved','result':{'question':'Is approval mandatory?','candidate_answer':self.candidate,'structured_answer':{'claims':[{'text':'A'}]},'original_record':{'context':self.chunks},'run_id':'source','status':'blocked'}}]}
        text=json.dumps(value);(source/'results.json').write_text(text)
        rows,bundle=runner.recheck(source,self.root/'out',Client(objection=False))
        self.assertEqual(len(rows),13);self.assertEqual((source/'results.json').read_text(),text)
        self.assertTrue(all(row['expected_context_result'] == 'advisory_error_reported' for row in rows if row['kind'] in ['saved_negative_control','synthetic_negative_control']))
        self.assertEqual(sum(row['expected_context_result'] == 'advisory_no_error_reported' for row in rows),5)
        with zipfile.ZipFile(bundle) as z:
            self.assertIn('README.md',z.namelist());self.assertTrue(json.loads(z.read('results.json'))['complete'])

if __name__=='__main__':unittest.main()
