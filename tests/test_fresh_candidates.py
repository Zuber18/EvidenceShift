"""Preserved generation contract and automatic evidence report tests."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from evidence_api import grounded as base,fresh_candidates as experiment


class Client:
    def __init__(self,mode=None):self.calls=[];self.mode=mode
    def list(self):return SimpleNamespace(model_dump=lambda **kw:{'models':[{'model':'qwen3:8b'}]})
    def chat(self,**kwargs):
        self.calls.append(copy.deepcopy(kwargs));payload=json.loads(kwargs['messages'][1]['content'])
        prompt=kwargs['messages'][0]['content']
        if prompt==base.SELECT_PROMPT:
            value={'answerability':'insufficient' if self.mode=='abstain' else 'supported',
                   'evidence_handles':[] if self.mode=='abstain' else [payload['paragraphs'][-1]['handle']]}
            if self.mode=='unknown_source':value['evidence_handles']=['S999']
        elif prompt==base.GENERATE_PROMPT:
            value={'response_type':'supported','claims':[{'text':'A controlled test claim.','evidence':['E1']}]}
            if self.mode=='unsupported_claim':value['claims'][0]['text']='A plausible but unsupported factual assertion.'
            if self.mode=='unknown_evidence':value['claims'][0]['evidence']=['E9']
            if self.mode=='mixed':value['claims'][0]['text']=base.ABSTENTION
            if self.mode=='markup':value['claims'][0]['text']='Claim [invented]'
        else:raise AssertionError('A verifier must not be called')
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value),thinking=None),done_reason='length' if self.mode=='truncated' else 'stop',eval_count=10)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.context=[{'id':'policy','source':'policy.txt','page':0,'text':'The first rule.\n\nThe second rule.'}]
    def run_case(self,client=None,context=None):
        return experiment.run('What is the rule?',self.context if context is None else context,client or Client(),
                              'qwen3:8b',{'temperature':0,'seed':42,'num_ctx':8192,'num_predict':4096},self.root,
                              {'case_id':'test','variant':'supplied'})
    def test_baseline_prompts_schemas_and_options_are_preserved(self):
        c=Client();r,_=self.run_case(c);self.assertEqual(len(c.calls),2)
        self.assertEqual([x['messages'][0]['content'] for x in c.calls],[base.SELECT_PROMPT,base.GENERATE_PROMPT])
        self.assertEqual(c.calls[0]['format'],base.selection_schema(self.context));self.assertEqual(c.calls[1]['format'],base.ANSWER_SCHEMA)
        self.assertTrue(all(x['options']['num_predict']==4096 and x['think'] is False for x in c.calls))
        self.assertEqual(r['status'],'candidate_recorded');self.assertIsNone(r['delivery_answer']);self.assertFalse(r['model_verifier_used'])
    def test_quote_and_original_source_saved_for_each_claim(self):
        r,_=self.run_case();link=r['claim_source_records'][0]
        self.assertEqual(link['selected_quotations'],['The second rule.']);self.assertEqual(link['original_cited_passages'],self.context)
        self.assertEqual(r['candidate_answer'],'A controlled test claim. [policy]')
    def test_empty_context_is_a_zero_call_code_control(self):
        c=Client();r,_=self.run_case(c,[]);self.assertEqual(c.calls,[]);self.assertEqual(r['status'],'empty_context_control');self.assertEqual(r['candidate_answer'],base.ABSTENTION)
    def test_evidence_insufficiency_is_recorded_without_a_verifier(self):
        c=Client('abstain');r,_=self.run_case(c);self.assertEqual(len(c.calls),1);self.assertEqual(r['candidate_answer'],base.ABSTENTION)
    def test_unverified_semantics_are_never_auto_approved(self):
        r,_=self.run_case(Client('unsupported_claim'));self.assertEqual(r['status'],'candidate_recorded')
        self.assertEqual(r['claim_source_records'][0]['semantic_citation_support'],'not_automatically_scored');self.assertIsNone(r['delivery_answer'])
    def test_unknown_selected_handle_is_a_mechanical_failure(self):
        r,_=self.run_case(Client('unknown_source'));self.assertEqual(r['status'],'mechanical_failure');self.assertIsNone(r['candidate_answer'])
    def test_unknown_claim_handle_is_a_mechanical_failure(self):
        r,_=self.run_case(Client('unknown_evidence'));self.assertEqual(r['status'],'mechanical_failure')
    def test_mixed_abstention_is_rejected(self):
        r,_=self.run_case(Client('mixed'));self.assertEqual(r['status'],'mechanical_failure')
    def test_model_cannot_insert_its_own_citation(self):
        r,_=self.run_case(Client('markup'));self.assertEqual(r['status'],'mechanical_failure')
    def test_truncation_is_saved_without_retry(self):
        c=Client('truncated');r,b=self.run_case(c);self.assertEqual(len(c.calls),1);self.assertEqual(r['status'],'mechanical_failure');self.assertTrue(b.exists())
    def test_input_budget_failure_makes_no_model_call(self):
        c=Client();r,_=self.run_case(c,[{'id':'large','source':'x.txt','text':'x'*7000}]);self.assertEqual(c.calls,[]);self.assertEqual(r['status'],'mechanical_failure')
    def test_bundle_has_raw_stages_and_original_context(self):
        r,b=self.run_case()
        with zipfile.ZipFile(b) as z:
            self.assertIn('stages.jsonl',z.namelist());self.assertEqual(json.loads(z.read('source_result.json'))['context'],self.context);self.assertEqual(json.loads(z.read('result.json')),r)
    def test_runner_saves_all_variants_without_exposing_assessment_labels(self):
        spec=importlib.util.spec_from_file_location('fresh_runner',ROOT/'evaluation/run_fresh_baseline.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        plan,raw=runner.load_plan();plan=copy.deepcopy(plan);plan['cases']=plan['cases'][:1]
        plan['cases'][0]['source_review_criteria']=['PRIVATE_CRITERION']
        runner.load_plan=lambda:(plan,raw)
        c=Client();rows,b=runner.run_benchmark(self.root,c)
        self.assertEqual(len(rows),3);self.assertEqual([row['variant'] for row in rows],['supplied','reversed','no_context'])
        self.assertEqual(len(c.calls),4);self.assertNotIn('PRIVATE_CRITERION',json.dumps(c.calls))
        with zipfile.ZipFile(b) as z:
            d=json.loads(z.read('results.json'));self.assertTrue(d['complete']);self.assertIn('report.md',z.namelist())
            self.assertEqual(d['records'][0]['result']['original_context'],list(reversed(d['records'][1]['result']['original_context'])))
            self.assertFalse(d['production_delivery'])

if __name__=='__main__':unittest.main()
