import copy
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

import evidence_api.grounded as m

CHUNKS=[{'id':'full_id_202','text':'Processing has not been completed. The request might never be acted upon.'},
        {'id':'full_id_100','text':'A server sends an interim 100 Continue response.'}]
SELECTION={'answerability':'supported','evidence_handles':['S1']}
ANSWER={'response_type':'supported','claims':[{'text':'Processing has not completed and the request might never be acted upon.',
          'evidence':['E1']}]}
VERDICT={'answers_question':True,'coverage_reason':'Both parts addressed.','abstention':'not_applicable',
         'claims':[{'claim_index':0,'verdict':'supported','reason':'Source states both qualifications.'}]}

class Client:
    def __init__(self,outputs=None,reason='stop'):
        self.outputs=outputs or [SELECTION,ANSWER,VERDICT];self.calls=[];self.reason=reason
    def list(self):return SimpleNamespace(model_dump=lambda **kw:{'models':[]})
    def chat(self,**kwargs):
        self.calls.append(copy.deepcopy(kwargs));value=self.outputs[len(self.calls)-1]
        if isinstance(value,Exception):raise value
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value)),done_reason=self.reason,eval_count=12)

class Tests(unittest.TestCase):
    def source(self,root,chunks=None):
        folder=Path(root)/'source';folder.mkdir()
        setup={'run_id':'s1','model':'test','options':{'num_predict':4096},'think':True,
               'request':{'question':'Has processing completed or is eventual action guaranteed?',
                          'expected_answer':'SECRET_LABEL','gold_evidence_ids':['SECRET_GOLD']}}
        original={'prompt_name':'original','variant':'reversed','context':CHUNKS if chunks is None else chunks,
                  'user_prompt':'Question: Has processing completed or is eventual action guaranteed?\nEvidence: '+json.dumps(CHUNKS if chunks is None else chunks),
                  'answer':'old raw answer','done_reason':'stop'}
        (folder/'setup.json').write_text(json.dumps(setup));(folder/'result.json').write_text(json.dumps({'run_id':'s1','records':[original]}))
        return folder
    def test_full_pipeline_provenance_and_only_advisory_pass(self):
        with tempfile.TemporaryDirectory() as d:
            src=self.source(d);raw=(src/'result.json').read_bytes();c=Client()
            result,bundle=m.run(src,Path(d)/'out',c)
            self.assertEqual(len(c.calls),3)
            self.assertEqual(result['status'],'needs_factual_review')
            self.assertTrue(result['delivery_answer'].endswith('[full_id_202]'))
            self.assertEqual(result['factual_correctness'],'not_automatically_certified')
            self.assertNotIn('SECRET',json.dumps(c.calls))
            self.assertEqual((src/'result.json').read_bytes(),raw)
            with zipfile.ZipFile(bundle) as z:
                self.assertEqual(z.read('source_result.json'),raw)
                self.assertEqual(json.loads(z.read('result.json')),result)
                events=[json.loads(x) for x in z.read('stages.jsonl').splitlines()]
                self.assertEqual(len(events),6)
            self.assertIn('format',c.calls[0])
    def test_model_quote_text_disallowed(self):
        with tempfile.TemporaryDirectory() as d:
            selection={'answerability':'supported','quotes':[{'quote':'The request will definitely succeed.'}]}
            c=Client([selection]);r,_=m.run(self.source(d),Path(d)/'out',c)
            self.assertEqual(len(c.calls),1);self.assertEqual(r['status'],'blocked');self.assertIsNone(r['delivery_answer'])
    def test_code_copies_exact_original_paragraph(self):
        evidence=m.validate_quotes(SELECTION,CHUNKS)
        self.assertEqual(evidence[0]['quote'],CHUNKS[0]['text'])
        self.assertEqual(evidence[0]['passage_ids'],['full_id_202'])
    def test_unknown_selection_handle_rejected(self):
        s=copy.deepcopy(SELECTION);s['evidence_handles']=['S999']
        with self.assertRaises(ValueError):m.validate_quotes(s,CHUNKS)
    def test_model_passage_ids_no_longer_allowed(self):
        s=copy.deepcopy(SELECTION);s['passage_id']='fake'
        with self.assertRaises(ValueError):m.validate_quotes(s,CHUNKS)
    def test_duplicate_selection_handles_rejected(self):
        s=copy.deepcopy(SELECTION);s['evidence_handles']=['S1','S1']
        with self.assertRaises(ValueError):m.validate_quotes(s,CHUNKS)
    def test_duplicate_passage_text_maps_to_all_sources(self):
        chunks=CHUNKS+[{'id':'duplicate_source','text':CHUNKS[0]['text']}]
        e=m.validate_quotes(SELECTION,chunks)
        self.assertEqual(e[0]['passage_ids'],['full_id_202','duplicate_source'])
        self.assertEqual(len(m.evidence_catalog(chunks)),2)
        text=m.validate_claims(ANSWER,SELECTION,e)
        self.assertIn('[duplicate_source]',text)
    def test_unknown_claim_handle_rejected(self):
        a=copy.deepcopy(ANSWER);a['claims'][0]['evidence']=['E9']
        with self.assertRaises(ValueError):m.validate_claims(a,SELECTION,m.validate_quotes(SELECTION,CHUNKS))
    def test_model_citations_and_mixed_abstention_rejected(self):
        for text in ['A claim [short]',m.ABSTENTION+' But the answer is no.']:
            a=copy.deepcopy(ANSWER);a['claims'][0]['text']=text
            with self.assertRaises(ValueError):m.validate_claims(a,SELECTION,m.validate_quotes(SELECTION,CHUNKS))
    def test_semantic_rejection_blocks_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            verdict=copy.deepcopy(VERDICT);verdict['claims'][0]['verdict']='insufficient'
            c=Client([SELECTION,ANSWER,verdict]);r,_=m.run(self.source(d),Path(d)/'out',c)
            self.assertIsNotNone(r['candidate_answer']);self.assertIsNone(r['delivery_answer']);self.assertEqual(r['status'],'blocked')
    def test_checker_must_review_each_claim_and_derive_support(self):
        v=copy.deepcopy(VERDICT);v['claims']=[]
        with self.assertRaises(ValueError):m.check_verdict(v,ANSWER)
        v=copy.deepcopy(VERDICT);v['claims'][0]['verdict']='contradicted'
        self.assertFalse(m.check_verdict(v,ANSWER))
        self.assertTrue(m.check_verdict(VERDICT,ANSWER))
    def test_false_abstention_checked_against_all_passages(self):
        with tempfile.TemporaryDirectory() as d:
            selection=copy.deepcopy(SELECTION);selection['answerability']='insufficient';selection['evidence_handles']=[]
            verdict={'answers_question':False,'coverage_reason':'Evidence answers it.','abstention':'unjustified','claims':[]}
            c=Client([selection,verdict]);r,_=m.run(self.source(d),Path(d)/'out',c)
            self.assertEqual(len(c.calls),2);self.assertEqual(r['candidate_answer'],m.ABSTENTION);self.assertEqual(r['status'],'blocked')
            payload=json.loads(c.calls[1]['messages'][1]['content'])
            self.assertEqual(len(payload['passages']),2)
    def test_no_context_no_model_call(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client();r,_=m.run(self.source(d,[]),Path(d)/'out',c)
            self.assertEqual(c.calls,[]);self.assertEqual(r['delivery_answer'],m.ABSTENTION)
    def test_incomplete_generation_preserved_without_retry(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client(reason='length');r,_=m.run(self.source(d),Path(d)/'out',c)
            self.assertEqual(len(c.calls),1);self.assertEqual(r['status'],'blocked')
            self.assertEqual(r['stages'][0]['done_reason'],'length')
    def test_budget_failure_no_call(self):
        with tempfile.TemporaryDirectory() as d:
            src=self.source(d);p=src/'result.json';r=json.loads(p.read_text());r['records'][0]['context'][0]['text']='x'*6000;p.write_text(json.dumps(r))
            c=Client();r,_=m.run(src,Path(d)/'out',c)
            self.assertEqual(c.calls,[]);self.assertEqual(r['stages'][0]['status'],'skipped_input')
    def test_timeout_saved(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client([TimeoutError('test')]);r,b=m.run(self.source(d),Path(d)/'out',c)
            self.assertEqual(r['status'],'blocked');self.assertIn('TimeoutError',r['error']);self.assertTrue(b.exists())
    def test_selector_only_off_changes_one_setting_and_no_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client();r,b=m.run(self.source(d),Path(d)/'out',c,thinking_mode='off',select_only=True)
            self.assertEqual(len(c.calls),1)
            self.assertIs(c.calls[0]['think'],False)
            self.assertEqual(c.calls[0]['options'],{'num_predict':4096})
            self.assertEqual(r['status'],'evidence_selected_needs_review')
            self.assertIsNone(r['delivery_answer'])
            with zipfile.ZipFile(b) as z:
                setup=json.loads(z.read('setup.json'))
                self.assertIs(setup['source_think'],True)
                self.assertIs(setup['think'],False)
                self.assertEqual(setup['experiment_mode'],'selection_only')
    def test_default_thinking_still_matches_source(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client();m.run(self.source(d),Path(d)/'out',c,select_only=True)
            self.assertIs(c.calls[0]['think'],True)

    def test_verifier_only_reuses_candidate_and_calls_once(self):
        with tempfile.TemporaryDirectory() as d:
            source=self.source(d);r,b=m.run(source,Path(d)/'out',Client())
            before=b.read_bytes();client=Client([VERDICT])
            updated,bundle=m.verify_saved(b,Path(d)/'out',client)
            self.assertEqual(len(client.calls),1)
            self.assertEqual(updated['candidate_answer'],r['candidate_answer'])
            self.assertEqual(updated['status'],'needs_factual_review')
            self.assertEqual(b.read_bytes(),before)
            with zipfile.ZipFile(bundle) as z:
                self.assertEqual(json.loads(z.read('previous_grounded_result.json')),r)
    def test_redundant_model_summary_field_rejected(self):
        v=copy.deepcopy(VERDICT);v['answer_supported']=False
        with self.assertRaises(ValueError):m.check_verdict(v,ANSWER)
    def test_justified_abstention_and_partial_coverage(self):
        v={'answers_question':True,'coverage_reason':'No evidence.','abstention':'justified','claims':[]}
        self.assertTrue(m.check_verdict(v,{'response_type':'insufficient','claims':[]}))
        v=copy.deepcopy(VERDICT);v['answers_question']=False
        self.assertFalse(m.check_verdict(v,ANSWER))

    def test_schema_rejects_extra_fields_wrong_types(self):
        a=copy.deepcopy(ANSWER);a['invented']='bad'
        with self.assertRaises(ValueError):m.validate(a,m.ANSWER_SCHEMA)
        v=copy.deepcopy(VERDICT);v['answers_question']='true'
        with self.assertRaises(ValueError):m.validate(v,m.VERIFY_SCHEMA)

if __name__=='__main__':unittest.main()
