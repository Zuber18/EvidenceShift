"""Actual parser/fixture tests plus controlled API orchestration; no embedding/model claims."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from evidence_api import document_e2e as suite,e2e_fixtures as fixtures,grounded as base
from evidence_api.ingestion import parse_document


class Response:
    def __init__(self,value):self.value=value
    def raise_for_status(self):pass
    def json(self):return copy.deepcopy(self.value)


class Api:
    def __init__(self):self.docs={};self.rows={};self.requests=[]
    def post(self,path,files=None,json=None):
        self.requests.append((path,copy.deepcopy(json)))
        if path=='/documents':
            filename,raw,_=files['file'];parsed=parse_document(filename,raw);doc=parsed['document_id'];old=doc in self.docs
            rows=[{'id':f"{doc}_p{p['page']}_c0",'text':p['text'],'document_id':doc,'page':p['page'],'chunk':0,
                   'source':filename,'sha256':parsed['sha256']} for p in parsed['pages']]
            self.rows[doc]=rows
            self.docs[doc]={'document_id':doc,'source':filename,'sha256':parsed['sha256'],'chunks':len(rows),'deduplicated':old}
            return Response(self.docs[doc])
        assert path=='/search';assert set(json)=={'question','top_k'}
        rows=[{**p,'distance':0.1} for values in self.rows.values() for p in values]
        return Response({'passages':rows[:json['top_k']]})
    def get(self,path,params=None):
        if path=='/documents':return Response(list(self.docs.values()))
        return Response(self.rows[path.split('/')[2]])


class Client:
    def __init__(self):self.calls=[]
    def list(self):return SimpleNamespace(model_dump=lambda **kwargs:{'models':[{'model':'qwen3:8b'}]})
    def chat(self,**kwargs):
        self.calls.append(copy.deepcopy(kwargs));payload=json.loads(kwargs['messages'][1]['content'])
        if kwargs['messages'][0]['content']==base.SELECT_PROMPT:
            value={'answerability':'supported','evidence_handles':[payload['paragraphs'][-1]['handle']]}
        else:
            assert kwargs['messages'][0]['content']==base.GENERATE_PROMPT
            value={'response_type':'supported','claims':[{'text':'A controlled test candidate.','evidence':['E1']}]}
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value),thinking=None),done_reason='stop',eval_count=10)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.plan=json.loads((ROOT/'evaluation/fresh_baseline_cases.json').read_text())
    def backend(self,capture,broken=False):
        @contextmanager
        def factory(path):
            api=Api();capture.append(api)
            profile={'embedding_model':'tfidf' if broken else 'sentence-transformers/all-MiniLM-L6-v2','chunk_tokens':180,'overlap_tokens':30,'splitter':'recursive-huggingface-token-v1'}
            yield SimpleNamespace(api=api,profile=profile)
        return factory
    def test_pdf_has_two_real_pages_with_body_on_second(self):
        from pypdf import PdfReader
        text=self.plan['cases'][0]['context'][0]['text'];raw=fixtures.pdf_bytes(text);reader=PdfReader(BytesIO(raw))
        self.assertEqual(len(reader.pages),2)
        self.assertIn(suite.normalize(text.strip().split('\n\n',1)[1]),suite.normalize(reader.pages[1].extract_text()))
        parsed=parse_document('test.pdf',raw);self.assertEqual([p['page'] for p in parsed['pages']],[1,2])
    def test_docx_parser_preserves_body_and_unpaginated_metadata(self):
        text=self.plan['cases'][0]['context'][0]['text'];raw=fixtures.docx_bytes(text)
        parsed=parse_document('test.docx',raw);self.assertEqual(parsed['pages'][0]['page'],0)
        self.assertEqual(suite.normalize(parsed['pages'][0]['text']),suite.normalize(text))
        self.assertEqual(raw,fixtures.docx_bytes(text))
    def test_fixture_inventory_contains_all_three_formats(self):
        records=fixtures.make_files(self.plan,self.root);self.assertEqual(len(records),48)
        self.assertEqual({r['format'] for r in records},{'txt','pdf','docx'})
    def test_coverage_requires_source_identity_and_operative_text(self):
        f={'expected_text':'Heading\n\nThe condition is required.'};docs={'gold':{'document_id':'d1'}}
        c=suite.evidence_coverage(['gold'],{'gold':f},docs,[{'id':'x','document_id':'d2','text':'The condition is required.'}]);self.assertFalse(c['all_required_units_found'])
        c=suite.evidence_coverage(['gold'],{'gold':f},docs,[{'id':'x','document_id':'d1','text':'The condition\nis required.'}]);self.assertTrue(c['all_required_units_found'])
    def test_no_positive_gold_evidence_has_undefined_recall(self):
        c=suite.evidence_coverage([],{}, {},[]);self.assertIsNone(c['recall']);self.assertIsNone(c['all_required_units_found'])
    def test_metadata_checks_reject_invented_page_numbers(self):
        f=fixtures.make_files(self.plan,self.root)[0];parsed=parse_document(f['filename'],f['path'].read_bytes());doc=parsed['document_id']
        chunk={'id':doc+'_p1_c0','document_id':doc,'source':f['filename'],'sha256':parsed['sha256'],'page':1,'chunk':0,'text':f['expected_text']}
        check=suite.check_document(f,{'document_id':doc},[chunk]);self.assertFalse(check['page_metadata_valid']);self.assertFalse(check['operative_body_extracted_on_expected_page'])
    def test_orchestration_uses_full_corpus_search_and_saves_every_answer(self):
        captures=[];client=Client();r,b=suite.run_suite(ROOT,self.root,client,self.backend(captures))
        self.assertTrue(r['complete']);self.assertTrue(r['all_expected_answer_records_present']);self.assertEqual(len(r['records']),24)
        self.assertEqual(len(r['document_checks']),48);self.assertTrue(all(x['passed'] for x in r['document_checks']))
        self.assertEqual(len(captures),3);self.assertTrue(all(len(a.docs)==16 for a in captures))
        searches=[payload for api in captures for path,payload in api.requests if path=='/search']
        self.assertEqual(len(searches),24);self.assertTrue(all(set(p)=={'question','top_k'} for p in searches))
        self.assertTrue(all(rec['result']['delivery_answer'] is None for rec in r['records']))
        self.assertTrue(all(row['factual_correctness']=='not_automatically_scored' for row in r['rows']))
        self.assertNotIn('required_fixture_ids',json.dumps(client.calls));self.assertNotIn('source_review_criteria',json.dumps(client.calls))
        self.assertTrue(any(row['all_required_evidence_found'] is False for row in r['rows']))
        with zipfile.ZipFile(b) as z:
            self.assertIn('report.md',z.namelist());self.assertTrue(any(p.startswith('fixtures/pdf/') for p in z.namelist()))
            self.assertFalse(any('indexes' in Path(p).parts for p in z.namelist()))
    def test_different_embedding_profile_is_preserved_as_format_failure(self):
        captures=[];client=Client();r,b=suite.run_suite(ROOT,self.root,client,self.backend(captures,True))
        self.assertEqual(len(r['format_errors']),3);self.assertEqual(client.calls,[]);self.assertFalse(r['all_expected_answer_records_present']);self.assertTrue(b.exists())
    def test_source_plan_edit_refused_before_calls(self):
        project=self.root/'project';(project/'evaluation').mkdir(parents=True)
        text=(ROOT/'evaluation/fresh_baseline_cases.json').read_text();(project/'evaluation/fresh_baseline_cases.json').write_text(text+' ')
        (project/'evaluation/document_e2e_requirements.json').write_bytes((ROOT/'evaluation/document_e2e_requirements.json').read_bytes())
        client=Client()
        with self.assertRaisesRegex(ValueError,'plan changed'):suite.run_suite(project,self.root/'output',client,self.backend([]))
        self.assertEqual(client.calls,[])
    def test_backend_failure_still_produces_bundle(self):
        @contextmanager
        def broken(root):raise RuntimeError('Controlled startup failure');yield
        client=Client();r,b=suite.run_suite(ROOT,self.root,client,broken)
        self.assertEqual(len(r['format_errors']),3);self.assertTrue(b.exists());self.assertEqual(client.calls,[])

if __name__=='__main__':unittest.main()
